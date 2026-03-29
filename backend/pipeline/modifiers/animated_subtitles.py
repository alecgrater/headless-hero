"""Animated subtitles (auto-edit) content modifier.

Provides an alternate full-video render using Claude-generated editing
timelines with word-synced typography, and exposes the auto-edit API endpoint.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from pipeline.modifiers.base import ContentModifier, ModifierMeta


class AnimatedSubtitlesModifier(ContentModifier):
    meta = ModifierMeta(
        id="animated_subtitles",
        name="Animated Subtitles",
        description="AI-powered auto-edit with word-synced text overlays and motion.",
        icon="✨",
    )

    def get_full_render_override(self, script_id: str, content, **kwargs) -> str | None:
        # This modifier's render is triggered via its own endpoint, not the
        # default full render path. Return None so the normal render proceeds.
        return None

    def get_router(self):
        return _build_router()


def _build_router() -> APIRouter:
    """Build the auto-edit API router (deferred to avoid circular imports)."""
    import json

    from api.database import get_session
    from models.brand import BrandProfile
    from models.script import Script, ScriptContent
    from pipeline.auto_editor import generate_edit_timeline, render_auto_edit_video
    from pipeline.render_jobs import create_job, run_in_background, update_job
    from pipeline.title_card import ensure_title_card_images

    router = APIRouter(prefix="/api/render", tags=["render"])

    class AutoEditRequest(BaseModel):
        script_id: str
        width: int = 1920
        height: int = 1080
        title: str = ""
        speed: float = 1.0

    class RenderJobResponse(BaseModel):
        job_id: str

    def _load_content(session: Session, script_id: str) -> ScriptContent:
        record = session.get(Script, script_id)
        if not record:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Script not found")
        return ScriptContent.model_validate(json.loads(record.script_json))

    def _ensure_title_cards(session: Session, script_id: str, content: ScriptContent) -> None:
        record = session.get(Script, script_id)
        if not record:
            return
        brand = session.get(BrandProfile, record.brand_id)
        primary, secondary = "#1a1a2e", "#16213e"
        if brand and brand.color_palette:
            colors = [c.strip() for c in brand.color_palette.split(",") if c.strip()]
            if len(colors) >= 1:
                primary = colors[0]
            if len(colors) >= 2:
                secondary = colors[1]
        font_family = brand.font if brand else ""
        ensure_title_card_images(script_id, content.segments, primary, secondary, font_family=font_family)

    def _total_audio_duration(content: ScriptContent) -> float:
        total = 0.0
        for seg in content.segments:
            for sc in seg.scenes:
                if sc.audio_duration_seconds:
                    total += sc.audio_duration_seconds
        return total

    @router.post("/auto-edit", response_model=RenderJobResponse)
    def start_auto_edit_render(body: AutoEditRequest, session: Session = Depends(get_session)):
        """Start an auto-edited YouTube video render in the background."""
        content = _load_content(session, body.script_id)
        _ensure_title_cards(session, body.script_id, content)
        scene_count = sum(len(seg.scenes) for seg in content.segments)
        audio_dur = _total_audio_duration(content)
        job = create_job(scene_count=scene_count, total_audio_duration=audio_dur)

        speed = max(0.5, min(3.0, body.speed))

        def do_render():
            def on_progress(p: float, msg: str):
                update_job(job.id, progress=p, current_step=msg)

            on_progress(0.0, "Generating editing timeline with Claude...")
            timeline = generate_edit_timeline(content)

            # Load brand font for subtitle rendering
            record = session.get(Script, body.script_id)
            brand_font = ""
            if record:
                brand_obj = session.get(BrandProfile, record.brand_id)
                if brand_obj:
                    brand_font = brand_obj.font or ""

            return render_auto_edit_video(
                script_id=body.script_id,
                content=content,
                timeline=timeline,
                width=body.width,
                height=body.height,
                on_progress=on_progress,
                title=body.title,
                speed=speed,
                font_name=brand_font,
            )

        run_in_background(job.id, do_render)
        return RenderJobResponse(job_id=job.id)

    return router
