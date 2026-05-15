"""Recording session API — upload takes, manage sessions, export with alignment."""

import json
import logging
import os
import re
import subprocess
import threading
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session

from api._helpers import update_scene, find_scene_in_content
from config import DATA_DIR
from database import get_session
from models.script import Script, ScriptContent
from pipeline.audio_alignment import align_audio
from pipeline.script_deviation import compute_deviation
from pipeline.voiceover import compute_phrase_timestamps

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/recording", tags=["recording"])


def _build_audio_filters() -> str | None:
    """Build FFmpeg audio filter chain from settings. Returns None if no filters enabled."""
    filters = []
    if os.environ.get("AUDIO_FILTER_HIGHPASS", "true").lower() == "true":
        filters.append("highpass=f=80")
    if os.environ.get("AUDIO_FILTER_NOISE_REDUCTION", "true").lower() == "true":
        filters.append("afftdn=nf=-20:tn=1")
    if os.environ.get("AUDIO_FILTER_DEESSER", "false").lower() == "true":
        filters.append("equalizer=f=6500:t=h:w=3000:g=-4")
    if os.environ.get("AUDIO_FILTER_COMPRESSOR", "true").lower() == "true":
        filters.append("acompressor=threshold=-20dB:ratio=3:attack=5:release=150")
    if os.environ.get("AUDIO_FILTER_LOWPASS", "false").lower() == "true":
        filters.append("lowpass=f=18000")
    return ",".join(filters) if filters else None


def _takes_dir(script_id: str) -> Path:
    return DATA_DIR / "projects" / script_id / "recording" / "takes"


def _session_path(script_id: str) -> Path:
    return DATA_DIR / "projects" / script_id / "recording" / "session.json"


def _audio_duration(path: Path) -> float:
    """Get audio duration via ffprobe."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
            capture_output=True, text=True, timeout=10,
        )
        return round(float(result.stdout.strip()), 3)
    except Exception:
        return 0.0


def _normalize_loudness(path: Path, target_lufs: float = -16.0) -> None:
    """Two-pass EBU R128 loudness normalization using ffmpeg loudnorm filter."""
    try:
        # First pass: measure
        measure_cmd = [
            "ffmpeg", "-i", str(path), "-af",
            f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11:print_format=json",
            "-f", "null", "-",
        ]
        result = subprocess.run(measure_cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            logger.warning("Loudness measurement failed (rc=%d) for %s", result.returncode, path.name)
            return
        stderr = result.stderr

        # Parse measured values from the last JSON block in stderr
        json_start = stderr.rfind("{")
        json_end = stderr.rfind("}") + 1
        if json_start < 0 or json_end <= json_start:
            logger.warning("Loudness measurement parse failed for %s", path.name)
            return

        measured = json.loads(stderr[json_start:json_end])

        # Second pass: apply with linear mode
        temp_path = path.with_suffix(".norm.mp3")
        normalize_cmd = [
            "ffmpeg", "-y", "-i", str(path), "-af",
            f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11"
            f":measured_I={measured['input_i']}"
            f":measured_TP={measured['input_tp']}"
            f":measured_LRA={measured['input_lra']}"
            f":measured_thresh={measured['input_thresh']}"
            f":offset={measured['target_offset']}"
            f":linear=true",
            "-c:a", "libmp3lame", "-b:a", "192k", str(temp_path),
        ]
        subprocess.run(normalize_cmd, capture_output=True, timeout=30, check=True)

        # Replace original with normalized
        temp_path.replace(path)
        logger.info("Normalized loudness for %s to %.1f LUFS", path.name, target_lufs)
    except Exception as exc:
        logger.warning("Loudness normalization failed for %s: %s", path.name, exc)


# --- Schemas ---

class UploadTakeResponse(BaseModel):
    filename: str
    duration_seconds: float


class SessionData(BaseModel):
    selected_takes: dict[str, int] = {}
    flagged_scenes: list[str] = []
    trim_points: dict[str, float] = {}
    settings: dict = {}


class ImportTakeResponse(BaseModel):
    filename: str
    take_number: int
    duration_seconds: float


class AlignTakeRequest(BaseModel):
    script_id: str
    scene_id: str
    take_number: int
    persist: bool = False


class AlignTakeResponse(BaseModel):
    word_timestamps: list[dict]
    phrase_timestamps: list[dict]
    duration_seconds: float
    transcript: str
    deviation: dict | None = None


class AnnotateDeliveryRequest(BaseModel):
    script_id: str
    scene_id: str


class ScoreTakeRequest(BaseModel):
    script_id: str
    scene_id: str
    take_number: int


class DimensionScore(BaseModel):
    score: int  # 1-10
    note: str


class TakeScoreResponse(BaseModel):
    overall: int  # 1-10
    dimensions: dict[str, DimensionScore]
    recommendation: str


class ScoreAllRequest(BaseModel):
    script_id: str


class ExportResponse(BaseModel):
    scenes_exported: int
    total_duration_seconds: float
    duration_changed_scenes: list[dict] = []


# --- Endpoints ---

@router.post("/upload-take", response_model=UploadTakeResponse)
async def upload_take(
    script_id: str = Form(...),
    scene_id: str = Form(...),
    take_number: int = Form(...),
    audio: UploadFile = File(...),
):
    takes_dir = _takes_dir(script_id)
    takes_dir.mkdir(parents=True, exist_ok=True)

    # Save raw WebM temporarily, then convert to MP3 for reliable duration/playback
    temp_webm = takes_dir / f"{scene_id}_take{take_number}_raw.webm"
    content = await audio.read()
    temp_webm.write_bytes(content)

    filename = f"{scene_id}_take{take_number}.mp3"
    filepath = takes_dir / filename

    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(temp_webm), "-c:a", "libmp3lame", "-b:a", "192k", str(filepath)],
            capture_output=True, text=True, timeout=30, check=True,
        )
    except subprocess.CalledProcessError as e:
        logger.error("WebM→MP3 conversion failed for %s: %s", scene_id, e.stderr[:300] if e.stderr else "")
        raise HTTPException(422, "Recording file appears corrupt — try recording again")
    finally:
        temp_webm.unlink(missing_ok=True)

    duration = _audio_duration(filepath)
    logger.info("Saved take %s/%s take %d (%.2fs)", script_id, scene_id, take_number, duration)
    return UploadTakeResponse(filename=filename, duration_seconds=duration)


@router.get("/session/{script_id}", response_model=SessionData)
async def get_session_data(script_id: str):
    path = _session_path(script_id)
    if path.exists():
        data = json.loads(path.read_text())
        return SessionData(**data)
    return SessionData()


@router.put("/session/{script_id}", response_model=SessionData)
async def put_session_data(script_id: str, data: SessionData):
    path = _session_path(script_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data.model_dump_json(indent=2))
    return data


@router.delete("/take/{script_id}/{scene_id}/{take_number}")
async def delete_take(script_id: str, scene_id: str, take_number: int):
    takes_dir = _takes_dir(script_id)
    matches = list(takes_dir.glob(f"{scene_id}_take{take_number}.*"))
    if matches:
        for f in matches:
            f.unlink()
        logger.info("Deleted take %s/%s take %d", script_id, scene_id, take_number)
        return {"deleted": True}
    raise HTTPException(404, "Take not found")


@router.get("/takes/{script_id}")
def list_takes(script_id: str):
    """List all takes for a script with filenames and durations."""
    takes_dir = _takes_dir(script_id)
    if not takes_dir.exists():
        return {"takes": []}

    takes: list[dict] = []
    for f in sorted(takes_dir.iterdir()):
        m = re.match(r"(.+)_take(\d+)\.(mp3|webm|wav|m4a|ogg)$", f.name)
        if not m or "_raw" in f.name or "_punch_temp" in f.name:
            continue
        scene_id = m.group(1)
        take_number = int(m.group(2))
        duration = _audio_duration(f)
        takes.append({
            "filename": f.name,
            "sceneId": scene_id,
            "takeNumber": take_number,
            "durationSeconds": duration,
        })

    return {"takes": takes}


@router.post("/align-take", response_model=AlignTakeResponse)
def align_take(req: AlignTakeRequest, db: Session = Depends(get_session)):
    """Run alignment on a take without full export — gives instant feedback on take swap."""
    takes_dir = _takes_dir(req.script_id)
    patterns = list(takes_dir.glob(f"{req.scene_id}_take{req.take_number}.*"))
    if not patterns:
        raise HTTPException(404, "Take not found")
    take_file = patterns[0]

    record = db.get(Script, req.script_id)
    if not record:
        raise HTTPException(404, "Script not found")

    content = ScriptContent.model_validate(json.loads(record.script_json))
    try:
        scene = find_scene_in_content(content, req.scene_id)
    except RuntimeError:
        raise HTTPException(404, "Scene not found")
    narration = scene.narration or ""

    duration = _audio_duration(take_file)
    word_timestamps = align_audio(take_file, narration)
    phrase_timestamps = compute_phrase_timestamps(word_timestamps)

    transcribed_words = [wt["word"] for wt in word_timestamps]
    deviation_result = compute_deviation(transcribed_words, narration)
    deviation_data = {
        "match_ratio": deviation_result.match_ratio,
        "deviations": [d.model_dump() for d in deviation_result.deviations],
    }

    if req.persist:
        web_path = f"/static/projects/{req.script_id}/audio/{req.scene_id}.mp3"
        update_scene(
            db, req.script_id, req.scene_id,
            audio_url=web_path,
            audio_duration_seconds=duration,
            word_timestamps=word_timestamps,
            phrase_timestamps=phrase_timestamps,
        )

    return AlignTakeResponse(
        word_timestamps=word_timestamps,
        phrase_timestamps=phrase_timestamps,
        duration_seconds=duration,
        transcript=deviation_result.transcript,
        deviation=deviation_data,
    )


@router.post("/import-take", response_model=ImportTakeResponse)
async def import_take(
    script_id: str = Form(...),
    scene_id: str = Form(...),
    audio: UploadFile = File(...),
):
    takes_dir = _takes_dir(script_id)
    takes_dir.mkdir(parents=True, exist_ok=True)

    existing = list(takes_dir.glob(f"{scene_id}_take*.*"))
    existing_numbers = []
    for f in existing:
        m = re.search(r"_take(\d+)", f.stem)
        if m:
            existing_numbers.append(int(m.group(1)))
    take_number = max(existing_numbers, default=0) + 1

    # Save original, then convert to MP3
    ext = Path(audio.filename or "audio.webm").suffix or ".webm"
    temp_file = takes_dir / f"{scene_id}_take{take_number}_import{ext}"
    content = await audio.read()
    temp_file.write_bytes(content)

    filename = f"{scene_id}_take{take_number}.mp3"
    filepath = takes_dir / filename

    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(temp_file), "-c:a", "libmp3lame", "-b:a", "192k", str(filepath)],
            capture_output=True, text=True, timeout=30, check=True,
        )
    except subprocess.CalledProcessError as e:
        logger.error("Import conversion failed for %s: %s", scene_id, e.stderr[:300] if e.stderr else "")
        raise HTTPException(422, "Audio file could not be converted")
    finally:
        temp_file.unlink(missing_ok=True)

    duration = _audio_duration(filepath)
    logger.info("Imported take %s/%s take %d (%.2fs)", script_id, scene_id, take_number, duration)
    return ImportTakeResponse(filename=filename, take_number=take_number, duration_seconds=duration)


@router.post("/export/{script_id}", response_model=ExportResponse)
def export_recording(script_id: str, db: Session = Depends(get_session)):
    record = db.get(Script, script_id)
    if not record:
        raise HTTPException(404, "Script not found")

    session_path = _session_path(script_id)
    if not session_path.exists():
        raise HTTPException(400, "No recording session found")

    session_data = SessionData(**json.loads(session_path.read_text()))
    content = ScriptContent.model_validate(json.loads(record.script_json))

    audio_dir = DATA_DIR / "projects" / script_id / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    scenes_exported = 0
    total_duration = 0.0
    duration_changed_scenes: list[dict] = []

    for scene_id, take_number in session_data.selected_takes.items():
        takes_dir = _takes_dir(script_id)
        patterns = list(takes_dir.glob(f"{scene_id}_take{take_number}.*"))
        if not patterns:
            logger.warning("Take file not found for %s take %d, skipping", scene_id, take_number)
            continue
        take_file = patterns[0]

        trim_end = session_data.trim_points.get(scene_id)
        output_mp3 = audio_dir / f"{scene_id}.mp3"

        # Check for loudness normalization setting
        normalize_loudness = session_data.settings.get("normalize_loudness", True)

        ffmpeg_cmd = ["ffmpeg", "-y", "-i", str(take_file)]
        if trim_end is not None and trim_end > 0:
            ffmpeg_cmd += ["-t", str(trim_end)]
        audio_filters = _build_audio_filters()
        if audio_filters:
            ffmpeg_cmd += ["-af", audio_filters]
        ffmpeg_cmd += ["-c:a", "libmp3lame", "-b:a", "192k", str(output_mp3)]

        try:
            subprocess.run(ffmpeg_cmd, capture_output=True, timeout=60, check=True)
        except subprocess.CalledProcessError as e:
            logger.error("FFmpeg conversion failed for %s: %s", scene_id, e.stderr[:500] if e.stderr else "")
            continue

        # Apply loudness normalization (two-pass)
        if normalize_loudness:
            _normalize_loudness(output_mp3)

        duration = _audio_duration(output_mp3)

        # Track duration changes for micro-timeline rescaling
        scene = find_scene_in_content(content, scene_id)
        old_duration = scene.audio_duration_seconds
        if old_duration and abs(duration - old_duration) > 0.1:
            duration_changed_scenes.append({
                "scene_id": scene_id,
                "old_duration": old_duration,
                "new_duration": duration,
            })

        narration = scene.narration or ""

        word_timestamps = align_audio(output_mp3, narration)
        phrase_timestamps = compute_phrase_timestamps(word_timestamps)

        web_path = f"/static/projects/{script_id}/audio/{scene_id}.mp3"
        update_scene(
            db, script_id, scene_id,
            audio_url=web_path,
            audio_duration_seconds=duration,
            word_timestamps=word_timestamps,
            phrase_timestamps=phrase_timestamps,
        )

        scenes_exported += 1
        total_duration += duration
        logger.info("Exported scene %s: %.2fs, %d words aligned", scene_id, duration, len(word_timestamps))

    return ExportResponse(
        scenes_exported=scenes_exported,
        total_duration_seconds=round(total_duration, 3),
        duration_changed_scenes=duration_changed_scenes,
    )


@router.get("/rhythm/{script_id}/{scene_id}/{take_number}")
def get_rhythm_analysis(script_id: str, scene_id: str, take_number: int, db: Session = Depends(get_session)):
    """Analyze pacing rhythm of an aligned take."""
    takes_dir = _takes_dir(script_id)
    patterns = list(takes_dir.glob(f"{scene_id}_take{take_number}.*"))
    if not patterns:
        raise HTTPException(404, "Take not found")

    record = db.get(Script, script_id)
    if not record:
        raise HTTPException(404, "Script not found")

    content = ScriptContent.model_validate(json.loads(record.script_json))
    try:
        scene = find_scene_in_content(content, scene_id)
    except RuntimeError:
        raise HTTPException(404, "Scene not found")
    narration = scene.narration or ""

    take_file = patterns[0]
    word_timestamps = align_audio(take_file, narration)

    if len(word_timestamps) < 2:
        return {"avg_wpm": 0, "pace_variance": 0, "gaps": [], "fastest_5s_wpm": 0, "slowest_5s_wpm": 0}

    total_ms = word_timestamps[-1]["end_ms"] - word_timestamps[0]["start_ms"]
    avg_wpm = round((len(word_timestamps) / (total_ms / 60000)) if total_ms > 0 else 0, 1)

    # Find gaps (silence between words > 300ms)
    gaps = []
    for i in range(1, len(word_timestamps)):
        gap_ms = word_timestamps[i]["start_ms"] - word_timestamps[i - 1]["end_ms"]
        if gap_ms > 300:
            gaps.append({
                "start_ms": word_timestamps[i - 1]["end_ms"],
                "end_ms": word_timestamps[i]["start_ms"],
                "duration_ms": gap_ms,
            })

    # Rolling 5-second WPM windows
    window_ms = 5000
    window_wpms = []
    for wt in word_timestamps:
        window_start = wt["start_ms"]
        window_end = window_start + window_ms
        words_in_window = [w for w in word_timestamps if w["start_ms"] >= window_start and w["end_ms"] <= window_end]
        if len(words_in_window) > 1:
            window_wpms.append(len(words_in_window) / (window_ms / 60000))

    fastest_5s = round(max(window_wpms), 1) if window_wpms else avg_wpm
    slowest_5s = round(min(window_wpms), 1) if window_wpms else avg_wpm

    # Pace variance: standard deviation of per-word durations
    word_durations = [wt["end_ms"] - wt["start_ms"] for wt in word_timestamps]
    mean_dur = sum(word_durations) / len(word_durations)
    variance = sum((d - mean_dur) ** 2 for d in word_durations) / len(word_durations)
    pace_variance = round(variance ** 0.5, 1)

    return {
        "avg_wpm": avg_wpm,
        "pace_variance": pace_variance,
        "gaps": gaps,
        "fastest_5s_wpm": fastest_5s,
        "slowest_5s_wpm": slowest_5s,
    }


def _compute_take_score(word_timestamps: list[dict], narration: str, deviation_ratio: float) -> TakeScoreResponse:
    """Compute algorithmic metrics + Claude qualitative score for a take."""
    if len(word_timestamps) < 3:
        return TakeScoreResponse(
            overall=5,
            dimensions={"data": DimensionScore(score=5, note="Not enough data to score")},
            recommendation="Record a longer take for meaningful scoring.",
        )

    # --- Algorithmic metrics ---
    total_ms = word_timestamps[-1]["end_ms"] - word_timestamps[0]["start_ms"]
    wpm = (len(word_timestamps) / (total_ms / 60000)) if total_ms > 0 else 0

    # Pacing consistency: coefficient of variation of word durations
    word_durations = [wt["end_ms"] - wt["start_ms"] for wt in word_timestamps]
    mean_dur = sum(word_durations) / len(word_durations)
    std_dur = (sum((d - mean_dur) ** 2 for d in word_durations) / len(word_durations)) ** 0.5
    cv = std_dur / mean_dur if mean_dur > 0 else 0

    # Gap analysis
    gaps = []
    for i in range(1, len(word_timestamps)):
        gap_ms = word_timestamps[i]["start_ms"] - word_timestamps[i - 1]["end_ms"]
        if gap_ms > 300:
            gaps.append(gap_ms)
    long_gaps = [g for g in gaps if g > 1500]

    # Pacing score: target 130-160 WPM, penalize extremes
    if 130 <= wpm <= 160:
        pacing_score = 9
    elif 110 <= wpm <= 180:
        pacing_score = 7
    elif 90 <= wpm <= 200:
        pacing_score = 5
    else:
        pacing_score = 3

    # Rhythm/consistency score: lower CV = more consistent (but some variation is good)
    if 0.3 <= cv <= 0.6:
        rhythm_score = 9
    elif 0.2 <= cv <= 0.8:
        rhythm_score = 7
    elif cv < 0.2:
        rhythm_score = 5  # too robotic
    else:
        rhythm_score = 4  # too erratic

    # Penalize for long unnatural pauses
    if long_gaps:
        rhythm_score = max(3, rhythm_score - len(long_gaps))

    # Script accuracy score from deviation
    if deviation_ratio >= 0.98:
        accuracy_score = 10
    elif deviation_ratio >= 0.95:
        accuracy_score = 8
    elif deviation_ratio >= 0.85:
        accuracy_score = 6
    elif deviation_ratio >= 0.70:
        accuracy_score = 4
    else:
        accuracy_score = 2

    # --- Claude qualitative assessment ---
    engagement_score = 7
    emphasis_score = 7
    claude_note = ""

    try:
        from integrations.claude_client import chat

        # Build a compact timing summary for Claude
        timing_summary = f"WPM: {wpm:.0f}, CV: {cv:.2f}, gaps>1.5s: {len(long_gaps)}, accuracy: {deviation_ratio:.0%}"

        # Sample word timings (every 5th word) to show pacing pattern
        sample_words = []
        for i in range(0, len(word_timestamps), max(1, len(word_timestamps) // 15)):
            wt = word_timestamps[i]
            sample_words.append(f"{wt['word']}({wt['end_ms'] - wt['start_ms']}ms)")
        pacing_pattern = " ".join(sample_words[:15])

        prompt = f"""Score this voiceover take's delivery quality. The narrator recorded this text:

"{narration[:500]}"

Timing data: {timing_summary}
Pacing sample (word + duration): {pacing_pattern}

Score two dimensions (1-10 each):
1. "emphasis" — Are word durations varied enough to suggest natural stress patterns? (Monotone=3, natural variation=7, dramatic=9)
2. "engagement" — Based on pacing and rhythm, does this sound like an engaged narrator or someone reading flat? (Flat=3, conversational=7, compelling=9)

Also give a one-sentence "recommendation" for improvement (or "Sounds great" if scores are 8+).

Return ONLY JSON: {{"emphasis": 7, "emphasis_note": "brief reason", "engagement": 8, "engagement_note": "brief reason", "recommendation": "one sentence"}}"""

        text = chat(
            system="",
            user_message=prompt,
            max_tokens=300,
            json_mode=True,
            task="analysis",
        ).strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        result = json.loads(text)
        emphasis_score = max(1, min(10, result.get("emphasis", 7)))
        engagement_score = max(1, min(10, result.get("engagement", 7)))
        claude_note = result.get("recommendation", "")
    except Exception as exc:
        logger.warning("Claude scoring failed, using algorithmic fallback: %s", exc)
        claude_note = "AI scoring unavailable — using rhythm metrics only."

    # Overall: weighted average
    overall = round(
        pacing_score * 0.2 +
        rhythm_score * 0.2 +
        accuracy_score * 0.2 +
        emphasis_score * 0.2 +
        engagement_score * 0.2
    )

    dimensions = {
        "pacing": DimensionScore(score=pacing_score, note=f"{wpm:.0f} WPM"),
        "rhythm": DimensionScore(score=rhythm_score, note=f"CV={cv:.2f}, {len(long_gaps)} long pauses"),
        "accuracy": DimensionScore(score=accuracy_score, note=f"{deviation_ratio:.0%} match"),
        "emphasis": DimensionScore(score=emphasis_score, note="Natural word stress variation"),
        "engagement": DimensionScore(score=engagement_score, note="Energy and delivery presence"),
    }

    recommendation = claude_note or ("Sounds great — ready to export." if overall >= 8 else "Consider re-recording for better delivery.")

    return TakeScoreResponse(overall=overall, dimensions=dimensions, recommendation=recommendation)


@router.post("/score-take", response_model=TakeScoreResponse)
def score_take(req: ScoreTakeRequest, db: Session = Depends(get_session)):
    """Score a single take on delivery quality dimensions."""
    takes_dir = _takes_dir(req.script_id)
    patterns = list(takes_dir.glob(f"{req.scene_id}_take{req.take_number}.*"))
    if not patterns:
        raise HTTPException(404, "Take not found")
    take_file = patterns[0]

    record = db.get(Script, req.script_id)
    if not record:
        raise HTTPException(404, "Script not found")

    content = ScriptContent.model_validate(json.loads(record.script_json))
    try:
        scene = find_scene_in_content(content, req.scene_id)
    except RuntimeError:
        raise HTTPException(404, "Scene not found")
    narration = scene.narration or ""

    word_timestamps = align_audio(take_file, narration)

    transcribed_words = [wt["word"] for wt in word_timestamps]
    deviation_result = compute_deviation(transcribed_words, narration)

    return _compute_take_score(word_timestamps, narration, deviation_result.match_ratio)


# --- Score-all background job ---

_score_jobs: dict[str, dict] = {}


def _run_score_all(job_id: str, script_id: str, script_json: str, session_data: SessionData):
    """Background worker that scores all selected takes."""
    try:
        content = ScriptContent.model_validate(json.loads(script_json))
        takes_dir = _takes_dir(script_id)
        scenes_to_score = list(session_data.selected_takes.items())
        total = len(scenes_to_score)
        scores: dict[str, dict] = {}

        for i, (scene_id, take_number) in enumerate(scenes_to_score):
            patterns = list(takes_dir.glob(f"{scene_id}_take{take_number}.*"))
            if not patterns:
                continue
            take_file = patterns[0]

            try:
                scene = find_scene_in_content(content, scene_id)
            except RuntimeError:
                continue
            narration = scene.narration or ""

            word_timestamps = align_audio(take_file, narration)
            transcribed_words = [wt["word"] for wt in word_timestamps]
            deviation_result = compute_deviation(transcribed_words, narration)

            result = _compute_take_score(word_timestamps, narration, deviation_result.match_ratio)
            scores[scene_id] = result.model_dump()

            _score_jobs[job_id]["progress"] = round((i + 1) / total * 100)
            _score_jobs[job_id]["scores"] = scores

        _score_jobs[job_id]["status"] = "completed"
        _score_jobs[job_id]["scores"] = scores
    except Exception as exc:
        logger.error("Score-all job %s failed: %s", job_id, exc)
        _score_jobs[job_id]["status"] = "failed"
        _score_jobs[job_id]["error"] = str(exc)


@router.post("/score-all")
def score_all_takes(req: ScoreAllRequest, db: Session = Depends(get_session)):
    """Start background scoring of all selected takes."""
    record = db.get(Script, req.script_id)
    if not record:
        raise HTTPException(404, "Script not found")

    session_path = _session_path(req.script_id)
    if not session_path.exists():
        raise HTTPException(400, "No recording session")

    session_data = SessionData(**json.loads(session_path.read_text()))
    if not session_data.selected_takes:
        raise HTTPException(400, "No takes selected")

    job_id = str(uuid.uuid4())
    _score_jobs[job_id] = {"status": "running", "progress": 0, "scores": {}, "error": None}

    thread = threading.Thread(
        target=_run_score_all,
        args=(job_id, req.script_id, record.script_json, session_data),
        daemon=True,
    )
    thread.start()

    return {"job_id": job_id}


@router.get("/score-status/{job_id}")
def get_score_status(job_id: str):
    """Poll scoring job progress."""
    job = _score_jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@router.post("/annotate-delivery")
def annotate_delivery(req: AnnotateDeliveryRequest, db: Session = Depends(get_session)):
    """Generate delivery annotations (emphasis, energy zones) for a scene via Claude."""
    record = db.get(Script, req.script_id)
    if not record:
        raise HTTPException(404, "Script not found")

    content = ScriptContent.model_validate(json.loads(record.script_json))
    try:
        scene = find_scene_in_content(content, req.scene_id)
    except RuntimeError:
        raise HTTPException(404, "Scene not found")
    narration = scene.narration or ""

    if not narration:
        raise HTTPException(400, "Scene has no narration")

    words = narration.split()

    try:
        from integrations.claude_client import chat

        prompt = f"""Analyze this narration for vocal delivery coaching. The narration has {len(words)} words (0-indexed).

Narration: "{narration}"

Return a JSON object with:
- "emphasis_words": array of word indices (0-based) that should be stressed for impact
- "question_ranges": array of [start_idx, end_idx] pairs for question sentences
- "energy_zones": array of objects with "start" (word index), "end" (word index), "level" (one of: "calm", "building", "peak", "reflective")

Keep emphasis_words to 3-5 key words. Energy zones should cover all words with no gaps. Return ONLY valid JSON, no markdown."""

        text = chat(
            system="",
            user_message=prompt,
            max_tokens=1024,
            json_mode=True,
            task="analysis",
        ).strip()
        # Strip markdown fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        annotations = json.loads(text)
        return annotations
    except Exception as exc:
        logger.error("Delivery annotation failed: %s", exc)
        raise HTTPException(500, f"Annotation generation failed: {exc}")


@router.post("/punch-in")
async def punch_in(
    script_id: str = Form(...),
    scene_id: str = Form(...),
    base_take_number: int = Form(...),
    punch_in_ms: int = Form(...),
    punch_out_ms: int = Form(...),
    audio: UploadFile = File(...),
    db: Session = Depends(get_session),
):
    """Splice a punch-in recording into an existing take at the specified time range."""
    takes_dir = _takes_dir(script_id)
    takes_dir.mkdir(parents=True, exist_ok=True)

    base_patterns = list(takes_dir.glob(f"{scene_id}_take{base_take_number}.*"))
    if not base_patterns:
        raise HTTPException(404, "Base take not found")
    base_file = base_patterns[0]

    # Save punch-in audio to temp file, convert WebM→MP3 first
    punch_webm = takes_dir / f"{scene_id}_punch_temp.webm"
    content = await audio.read()
    punch_webm.write_bytes(content)

    punch_audio = takes_dir / f"{scene_id}_punch_temp.mp3"
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(punch_webm), "-c:a", "libmp3lame", "-b:a", "192k", str(punch_audio)],
            capture_output=True, text=True, timeout=30, check=True,
        )
    except subprocess.CalledProcessError:
        raise HTTPException(422, "Punch-in recording appears corrupt")
    finally:
        punch_webm.unlink(missing_ok=True)

    # Determine next take number
    existing = list(takes_dir.glob(f"{scene_id}_take*.*"))
    existing_numbers = []
    for f in existing:
        m = re.search(r"_take(\d+)", f.stem)
        if m:
            existing_numbers.append(int(m.group(1)))
    new_take_number = max(existing_numbers, default=0) + 1

    output_file = takes_dir / f"{scene_id}_take{new_take_number}.mp3"

    # FFmpeg splice: [base[0:punch_in] + replacement + base[punch_out:]]
    punch_in_s = punch_in_ms / 1000.0
    punch_out_s = punch_out_ms / 1000.0

    filter_complex = (
        f"[0:a]atrim=0:{punch_in_s},asetpts=PTS-STARTPTS[pre];"
        f"[1:a]asetpts=PTS-STARTPTS[mid];"
        f"[0:a]atrim={punch_out_s},asetpts=PTS-STARTPTS[post];"
        f"[pre][mid][post]concat=n=3:v=0:a=1[out]"
    )

    splice_cmd = [
        "ffmpeg", "-y",
        "-i", str(base_file),
        "-i", str(punch_audio),
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-c:a", "libmp3lame", "-b:a", "192k", str(output_file),
    ]

    try:
        subprocess.run(splice_cmd, capture_output=True, timeout=30, check=True)
    except subprocess.CalledProcessError as e:
        punch_audio.unlink(missing_ok=True)
        logger.error("Punch-in splice failed: %s", e.stderr[:500] if e.stderr else "")
        raise HTTPException(500, "Audio splice failed")

    punch_audio.unlink(missing_ok=True)
    duration = _audio_duration(output_file)

    # Run quick alignment
    record = db.get(Script, script_id)
    narration = ""
    if record:
        script_content = ScriptContent.model_validate(json.loads(record.script_json))
        try:
            scene = find_scene_in_content(script_content, scene_id)
            narration = scene.narration or ""
        except RuntimeError:
            pass

    word_timestamps = align_audio(output_file, narration)
    phrase_timestamps = compute_phrase_timestamps(word_timestamps)

    return {
        "filename": output_file.name,
        "take_number": new_take_number,
        "duration_seconds": duration,
        "word_timestamps": word_timestamps,
        "phrase_timestamps": phrase_timestamps,
    }
