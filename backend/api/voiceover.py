"""Endpoints for TTS voiceover generation via ElevenLabs."""

import json
import logging

from config import DEFAULT_TTS_MODEL
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session

from database import get_session
from integrations.elevenlabs_client import (
    add_library_voice,
    clone_voice,
    list_voices,
    search_library_voices,
)
from models.script import Script, ScriptContent
from pipeline.voiceover import generate_batch_audio, generate_scene_audio

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/voice", tags=["voice"])

# --- Request / Response schemas ---

class GenerateAudioRequest(BaseModel):
    script_id: str
    scene_id: str
    narration: str
    voice_id: str
    model_id: str = DEFAULT_TTS_MODEL
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
    model_id: str = DEFAULT_TTS_MODEL
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

# --- Helpers ---

def _update_scene_audio(
    session: Session,
    script_id: str,
    scene_id: str,
    audio_url: str,
    duration_seconds: float,
    word_timestamps: list[dict] | None = None,
) -> None:
    """Persist audio_url, audio_duration_seconds, and word_timestamps into the scene inside script_json."""
    record = session.get(Script, script_id)
    if not record:
        return
    content = ScriptContent.model_validate(json.loads(record.script_json))
    for seg in content.segments:
        for scene in seg.scenes:
            if scene.id == scene_id:
                scene.audio_url = audio_url
                scene.audio_duration_seconds = duration_seconds
                if word_timestamps is not None:
                    scene.word_timestamps = word_timestamps
                break
    record.script_json = content.model_dump_json()
    session.add(record)
    session.commit()

# --- Endpoints ---

@router.post("/generate", response_model=GenerateAudioResponse)
def generate_audio(body: GenerateAudioRequest, session: Session = Depends(get_session)):
    """Generate TTS audio for a single scene."""
    record = session.get(Script, body.script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    logger.info("Generating audio for scene %s in script %s", body.scene_id, body.script_id)
    audio_url, duration, word_timestamps = generate_scene_audio(
        scene_id=body.scene_id,
        narration=body.narration,
        voice_id=body.voice_id,
        script_id=body.script_id,
        model_id=body.model_id,
        voice_settings=body.voice_settings,
    )

    _update_scene_audio(session, body.script_id, body.scene_id, audio_url, duration, word_timestamps)

    logger.info("Audio generated for scene %s: %.1fs duration", body.scene_id, duration)
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

    scenes = [{"scene_id": s.scene_id, "narration": s.narration} for s in body.scenes]

    results = generate_batch_audio(
        scenes=scenes,
        voice_id=body.voice_id,
        script_id=body.script_id,
        model_id=body.model_id,
        voice_settings=body.voice_settings,
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
        if r.get("word_timestamps") is not None:
            sc.word_timestamps = r["word_timestamps"]
    record.script_json = content.model_dump_json()
    session.add(record)
    session.commit()

    errors = sum(1 for r in results if r.get("error"))
    logger.info("Batch audio generation complete for script %s: %d succeeded, %d failed", body.script_id, len(results) - errors, errors)
    return GenerateBatchAudioResponse(results=[BatchAudioResultItem(**r) for r in results])

@router.post("/clone", response_model=CloneVoiceResponse)
async def clone_voice_endpoint(
    name: str = Form(...),
    description: str = Form(""),
    files: list[UploadFile] = File(...),
):
    """Clone a voice by uploading audio samples to ElevenLabs."""
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
