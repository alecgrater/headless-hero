"""Recording session API — upload takes, manage sessions, export with alignment."""

import json
import logging
import subprocess
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session

from api._helpers import update_scene, find_scene_in_content
from config import DATA_DIR
from database import get_session
from models.script import Script, ScriptContent
from pipeline.audio_alignment import align_audio
from pipeline.voiceover import compute_phrase_timestamps

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/recording", tags=["recording"])


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


class ExportResponse(BaseModel):
    scenes_exported: int
    total_duration_seconds: float


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

    filename = f"{scene_id}_take{take_number}.webm"
    filepath = takes_dir / filename
    content = await audio.read()
    filepath.write_bytes(content)

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
    filepath = _takes_dir(script_id) / f"{scene_id}_take{take_number}.webm"
    if filepath.exists():
        filepath.unlink()
        logger.info("Deleted take %s/%s take %d", script_id, scene_id, take_number)
        return {"deleted": True}
    raise HTTPException(404, "Take not found")


@router.post("/import-take", response_model=ImportTakeResponse)
async def import_take(
    script_id: str = Form(...),
    scene_id: str = Form(...),
    audio: UploadFile = File(...),
):
    takes_dir = _takes_dir(script_id)
    takes_dir.mkdir(parents=True, exist_ok=True)

    existing = list(takes_dir.glob(f"{scene_id}_take*.webm")) + list(takes_dir.glob(f"{scene_id}_take*.mp3")) + list(takes_dir.glob(f"{scene_id}_take*.wav")) + list(takes_dir.glob(f"{scene_id}_take*.m4a"))
    take_number = len(existing) + 1

    ext = Path(audio.filename or "audio.webm").suffix or ".webm"
    filename = f"{scene_id}_take{take_number}{ext}"
    filepath = takes_dir / filename
    content = await audio.read()
    filepath.write_bytes(content)

    duration = _audio_duration(filepath)
    logger.info("Imported take %s/%s take %d (%.2fs)", script_id, scene_id, take_number, duration)
    return ImportTakeResponse(filename=filename, take_number=take_number, duration_seconds=duration)


@router.post("/export/{script_id}", response_model=ExportResponse)
async def export_recording(script_id: str, db: Session = Depends(get_session)):
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

    for scene_id, take_number in session_data.selected_takes.items():
        takes_dir = _takes_dir(script_id)
        take_file = takes_dir / f"{scene_id}_take{take_number}.webm"
        if not take_file.exists():
            patterns = list(takes_dir.glob(f"{scene_id}_take{take_number}.*"))
            if patterns:
                take_file = patterns[0]
            else:
                logger.warning("Take file not found for %s take %d, skipping", scene_id, take_number)
                continue

        trim_end = session_data.trim_points.get(scene_id)
        output_mp3 = audio_dir / f"{scene_id}.mp3"

        ffmpeg_cmd = ["ffmpeg", "-y", "-i", str(take_file)]
        if trim_end is not None and trim_end > 0:
            ffmpeg_cmd += ["-t", str(trim_end)]
        ffmpeg_cmd += ["-c:a", "libmp3lame", "-b:a", "192k", str(output_mp3)]

        try:
            subprocess.run(ffmpeg_cmd, capture_output=True, timeout=60, check=True)
        except subprocess.CalledProcessError as e:
            logger.error("FFmpeg conversion failed for %s: %s", scene_id, e.stderr[:500] if e.stderr else "")
            continue

        duration = _audio_duration(output_mp3)

        scene = find_scene_in_content(content, scene_id)
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

    return ExportResponse(scenes_exported=scenes_exported, total_duration_seconds=round(total_duration, 3))
