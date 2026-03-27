"""Endpoints for TTS voiceover generation via ElevenLabs."""

from __future__ import annotations

import json
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlmodel import Session

from api.database import get_session
from integrations.elevenlabs_client import clone_voice, list_voices
from models.script import Script, ScriptContent
from pipeline.voiceover import generate_batch_audio, generate_scene_audio

router = APIRouter(prefix="/api/voice", tags=["voice"])


# --- Request / Response schemas ---


class GenerateAudioRequest(BaseModel):
    script_id: str
    scene_id: str
    narration: str
    voice_id: str
    model_id: str = "eleven_multilingual_v2"


class GenerateAudioResponse(BaseModel):
    audio_url: str
    duration_seconds: float


class BatchAudioScene(BaseModel):
    scene_id: str
    narration: str


class GenerateBatchAudioRequest(BaseModel):
    script_id: str
    scenes: List[BatchAudioScene]
    voice_id: str
    model_id: str = "eleven_multilingual_v2"


class BatchAudioResultItem(BaseModel):
    scene_id: str
    audio_url: Optional[str] = None
    duration_seconds: Optional[float] = None
    error: Optional[str] = None


class GenerateBatchAudioResponse(BaseModel):
    results: List[BatchAudioResultItem]


class VoiceInfo(BaseModel):
    voice_id: str
    name: str
    category: str


class VoiceListResponse(BaseModel):
    voices: List[VoiceInfo]


class CloneVoiceResponse(BaseModel):
    voice_id: str


# --- Helpers ---


def _update_scene_audio(
    session: Session,
    script_id: str,
    scene_id: str,
    audio_url: str,
    duration_seconds: float,
) -> None:
    """Persist audio_url and audio_duration_seconds into the scene inside script_json."""
    record = session.get(Script, script_id)
    if not record:
        return
    content = ScriptContent.model_validate(json.loads(record.script_json))
    for seg in content.segments:
        for scene in seg.scenes:
            if scene.id == scene_id:
                scene.audio_url = audio_url
                scene.audio_duration_seconds = duration_seconds
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

    audio_url, duration = generate_scene_audio(
        scene_id=body.scene_id,
        narration=body.narration,
        voice_id=body.voice_id,
        script_id=body.script_id,
        model_id=body.model_id,
    )

    _update_scene_audio(session, body.script_id, body.scene_id, audio_url, duration)

    return GenerateAudioResponse(audio_url=audio_url, duration_seconds=duration)


@router.post("/generate-batch", response_model=GenerateBatchAudioResponse)
def generate_audio_batch(
    body: GenerateBatchAudioRequest, session: Session = Depends(get_session)
):
    """Generate TTS audio for multiple scenes sequentially."""
    record = session.get(Script, body.script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    scenes = [{"scene_id": s.scene_id, "narration": s.narration} for s in body.scenes]

    results = generate_batch_audio(
        scenes=scenes,
        voice_id=body.voice_id,
        script_id=body.script_id,
        model_id=body.model_id,
    )

    # Persist successful audio URLs
    for r in results:
        if r["audio_url"]:
            _update_scene_audio(
                session,
                body.script_id,
                r["scene_id"],
                r["audio_url"],
                float(r["duration_seconds"]),
            )

    return GenerateBatchAudioResponse(results=[BatchAudioResultItem(**r) for r in results])


@router.post("/clone", response_model=CloneVoiceResponse)
async def clone_voice_endpoint(
    name: str = Form(...),
    description: str = Form(""),
    files: List[UploadFile] = File(...),
):
    """Clone a voice by uploading audio samples to ElevenLabs."""
    if not files:
        raise HTTPException(status_code=400, detail="At least one audio file is required")
    if len(files) > 25:
        raise HTTPException(status_code=400, detail="Maximum 25 audio samples allowed")

    audio_files = []  # type: List[tuple]
    for f in files:
        content = await f.read()
        audio_files.append((f.filename or "sample.mp3", content))

    voice_id = clone_voice(name=name, audio_files=audio_files, description=description)
    return CloneVoiceResponse(voice_id=voice_id)


@router.get("/voices", response_model=VoiceListResponse)
def get_voices():
    """List available ElevenLabs voices."""
    voices = list_voices()
    return VoiceListResponse(voices=[VoiceInfo(**v) for v in voices])
