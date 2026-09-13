"""Endpoints for TTS voiceover generation via ElevenLabs."""

import json
import logging
import time
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session

from database import get_session
from api._helpers import update_scene
from integrations.elevenlabs_client import (
    add_library_voice,
    clone_voice,
    list_voices,
    search_library_voices,
)
from models.generation_duration import GenerationDuration
from models.script import Script, ScriptContent
from pipeline.voiceover import (
    active_voice_engine,
    generate_batch_audio,
    generate_scene_audio,
    prepare_tts_text,
    resolve_tts_model_and_settings,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice", tags=["voice"])

# --- Request / Response schemas ---

class GenerateAudioRequest(BaseModel):
    script_id: str
    scene_id: str
    narration: str
    voice_id: str
    model_id: str | None = None
    voice_settings: dict | None = None

class GenerateAudioResponse(BaseModel):
    audio_url: str
    duration_seconds: float
    word_timestamps: list[dict] = []

class BatchAudioScene(BaseModel):
    scene_id: str
    narration: str

class GenerateBatchAudioRequest(BaseModel):
    script_id: str
    scenes: list[BatchAudioScene]
    voice_id: str
    model_id: str | None = None
    voice_settings: dict | None = None

class BatchAudioResultItem(BaseModel):
    scene_id: str
    audio_url: str | None = None
    duration_seconds: float | None = None
    word_timestamps: list[dict] = []
    error: str | None = None

class GenerateBatchAudioResponse(BaseModel):
    results: list[BatchAudioResultItem]

class VoiceInfo(BaseModel):
    voice_id: str
    name: str
    category: str

class VoiceListResponse(BaseModel):
    voices: list[VoiceInfo]

class CloneVoiceResponse(BaseModel):
    voice_id: str

class LibrarySearchRequest(BaseModel):
    search: str
    page_size: int = 20

class LibraryVoiceInfo(BaseModel):
    voice_id: str
    name: str
    public_owner_id: str
    accent: str = ""
    gender: str = ""
    age: str = ""
    description: str = ""
    preview_url: str = ""
    category: str = ""
    use_case: str = ""

class LibrarySearchResponse(BaseModel):
    voices: list[LibraryVoiceInfo]

class AddLibraryVoiceRequest(BaseModel):
    public_owner_id: str
    voice_id: str
    name: str

class AddLibraryVoiceResponse(BaseModel):
    voice_id: str

# --- Endpoints ---

@router.post("/generate", response_model=GenerateAudioResponse)
def generate_audio(body: GenerateAudioRequest, session: Session = Depends(get_session)):
    """Generate TTS audio for a single scene."""
    t0 = time.monotonic()
    record = session.get(Script, body.script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    logger.info("Generating audio for scene %s in script %s", body.scene_id, body.script_id)
    model_id, voice_settings = resolve_tts_model_and_settings(body.model_id, body.voice_settings)
    content = ScriptContent.model_validate(json.loads(record.script_json))
    found_scene = None
    found_seg_idx = None
    for seg_idx, seg in enumerate(content.segments):
        for sc in seg.scenes:
            if sc.id == body.scene_id:
                found_scene = sc
                found_seg_idx = seg_idx
                break
        if found_scene:
            break
    tts_text = prepare_tts_text(
        body.narration,
        model_id=model_id,
        is_title_card=bool(found_scene and found_scene.is_title_card),
        level_number=(found_seg_idx or 0) + 1 if found_scene and found_scene.is_title_card else None,
    )
    if tts_text != body.narration:
        logger.info("Prepared hidden TTS text for scene %s", body.scene_id)
    audio_url, duration, word_timestamps, phrase_timestamps = generate_scene_audio(
        scene_id=body.scene_id,
        narration=tts_text,
        voice_id=body.voice_id,
        script_id=body.script_id,
        model_id=model_id,
        voice_settings=voice_settings,
    )

    fields: dict = {
        "audio_url": audio_url,
        "audio_duration_seconds": duration,
        "voice_engine": active_voice_engine(),
    }
    if word_timestamps is not None:
        fields["word_timestamps"] = word_timestamps
    if phrase_timestamps is not None:
        fields["phrase_timestamps"] = phrase_timestamps
    update_scene(session, body.script_id, body.scene_id, **fields)

    logger.info("Audio generated for scene %s: %.1fs duration", body.scene_id, duration)

    session.add(GenerationDuration(operation_type="single_audio_generation", duration_seconds=time.monotonic() - t0))
    session.commit()

    return GenerateAudioResponse(audio_url=audio_url, duration_seconds=duration, word_timestamps=word_timestamps)

@router.post("/generate-batch", response_model=GenerateBatchAudioResponse)
def generate_audio_batch(
    body: GenerateBatchAudioRequest, session: Session = Depends(get_session)
):
    """Generate TTS audio for multiple scenes sequentially."""
    record = session.get(Script, body.script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    logger.info("Starting batch audio generation for script %s (%d scenes)", body.script_id, len(body.scenes))
    model_id, voice_settings = resolve_tts_model_and_settings(body.model_id, body.voice_settings)
    content_for_framing = ScriptContent.model_validate(json.loads(record.script_json))
    scene_lookup = {sc.id: sc for seg in content_for_framing.segments for sc in seg.scenes}

    # Build scene_id -> level_number map for title-card framing.
    title_card_map: dict[str, int] = {}
    for seg_idx, seg in enumerate(content_for_framing.segments):
        for sc in seg.scenes:
            if sc.is_title_card:
                title_card_map[sc.id] = seg_idx + 1

    scenes = []
    for s in body.scenes:
        sc = scene_lookup.get(s.scene_id)
        narration = s.narration
        if s.scene_id in title_card_map:
            # Use DB narration as canonical title text; body may be stale.
            narration = sc.narration if sc else s.narration
        narration = prepare_tts_text(
            narration,
            model_id=model_id,
            is_title_card=s.scene_id in title_card_map,
            level_number=title_card_map.get(s.scene_id),
        )
        scenes.append({"scene_id": s.scene_id, "narration": narration})

    # Captured before the batch so every scene records the engine that ran,
    # even if a setting changes while the batch is in flight.
    engine_used = active_voice_engine()
    results = generate_batch_audio(
        scenes=scenes,
        voice_id=body.voice_id,
        script_id=body.script_id,
        model_id=model_id,
        voice_settings=voice_settings,
    )

    # Persist all successful results in a single DB write
    content = ScriptContent.model_validate(json.loads(record.script_json))
    scene_map = {sc.id: sc for seg in content.segments for sc in seg.scenes}
    for r in results:
        if not r["audio_url"]:
            continue
        sc = scene_map.get(r["scene_id"])
        if not sc:
            continue
        sc.audio_url = r["audio_url"]
        sc.audio_duration_seconds = float(r["duration_seconds"])
        sc.voice_engine = engine_used
        if r.get("word_timestamps") is not None:
            sc.word_timestamps = r["word_timestamps"]
        if r.get("phrase_timestamps") is not None:
            sc.phrase_timestamps = r["phrase_timestamps"]
    record.script_json = content.model_dump_json()
    session.add(record)
    session.commit()

    errors = sum(1 for r in results if r.get("error"))
    logger.info("Batch audio generation complete for script %s: %d succeeded, %d failed", body.script_id, len(results) - errors, errors)
    # Note: response uses original batch results — tightened scenes are persisted
    # in script_json; the frontend re-reads the script after voiceover completes.
    return GenerateBatchAudioResponse(results=[BatchAudioResultItem(**r) for r in results])

@router.post("/clone", response_model=CloneVoiceResponse)
async def clone_voice_endpoint(
    name: str = Form(...),
    description: str = Form(""),
    files: list[UploadFile] = File(...),
):
    """Clone a voice by uploading audio samples to ElevenLabs."""
    t0 = time.monotonic()
    if not files:
        raise HTTPException(status_code=400, detail="At least one audio file is required")
    if len(files) > 25:
        raise HTTPException(status_code=400, detail="Maximum 25 audio samples allowed")

    logger.info("Cloning voice %s with %d audio samples", name, len(files))

    audio_files: list[tuple] = []
    for f in files:
        content = await f.read()
        audio_files.append((f.filename or "sample.mp3", content))

    voice_id = clone_voice(name=name, audio_files=audio_files, description=description)
    logger.info("Voice cloned successfully: %s", voice_id)

    from database import engine
    from sqlmodel import Session as SyncSession
    with SyncSession(engine) as s:
        s.add(GenerationDuration(operation_type="voice_cloning", duration_seconds=time.monotonic() - t0))
        s.commit()

    return CloneVoiceResponse(voice_id=voice_id)

@router.get("/voices", response_model=VoiceListResponse)
def get_voices():
    """List available ElevenLabs voices."""
    try:
        voices = list_voices()
    except RuntimeError:
        logger.warning("ElevenLabs API key not configured — returning empty voice list")
        return VoiceListResponse(voices=[])
    logger.info("Listed %d voices", len(voices))
    return VoiceListResponse(voices=[VoiceInfo(**v) for v in voices])


@router.post("/library/search", response_model=LibrarySearchResponse)
def search_library(body: LibrarySearchRequest):
    """Search the ElevenLabs shared voice library."""
    try:
        results = search_library_voices(body.search, body.page_size)
    except RuntimeError:
        logger.warning("ElevenLabs API key not configured")
        return LibrarySearchResponse(voices=[])
    logger.info("Library search for %r returned %d results", body.search, len(results))
    return LibrarySearchResponse(voices=[LibraryVoiceInfo(**v) for v in results])


@router.post("/library/add", response_model=AddLibraryVoiceResponse, status_code=201)
def add_from_library(body: AddLibraryVoiceRequest):
    """Add a voice from the ElevenLabs shared library to your account."""
    logger.info("Adding library voice %s (%s)", body.voice_id, body.name)
    new_voice_id = add_library_voice(body.public_owner_id, body.voice_id, body.name)
    logger.info("Library voice added as %s", new_voice_id)
    return AddLibraryVoiceResponse(voice_id=new_voice_id)
