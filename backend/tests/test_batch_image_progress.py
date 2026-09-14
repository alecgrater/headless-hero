"""A long image batch must report progress, or pollers abandon it mid-run.

The frontend's `pollBackgroundJob` times out when `job.progress` stops
advancing, not on total elapsed time. `generate_batch` used to report nothing
between start and finish, so any batch slower than the stall budget (30 min in
Local Mode) was abandoned while its thread kept generating — the UI then
retried the whole batch against an orphaned first run.
"""

from unittest.mock import patch

import os
import threading

from pipeline import image_gen


def _scenes(n: int) -> list[dict]:
    return [{"scene_id": f"s{i}", "visual_prompt": f"p{i}", "visual_mode": "full_frame"} for i in range(n)]


def _fake_one(scene, script_id, width, height, style_guide):
    return {"scene_id": scene["scene_id"], "image_url": f"/img/{scene['scene_id']}.png", "error": None}


def test_generate_batch_reports_progress_for_every_scene():
    seen: list[tuple[int, int]] = []
    with patch.object(image_gen, "_generate_one_scene", _fake_one):
        results = image_gen.generate_batch(
            scenes=_scenes(5), script_id="sid", on_scene_done=lambda d, t: seen.append((d, t))
        )

    assert len(results) == 5
    # Monotonic 1..5, always against the full total.
    assert seen == [(1, 5), (2, 5), (3, 5), (4, 5), (5, 5)]


def test_generate_batch_stops_when_cancelled():
    """Cancelling must prevent queued scenes from ever starting."""
    started: list[str] = []
    release = threading.Event()

    def _slow_one(scene, script_id, width, height, style_guide):
        started.append(scene["scene_id"])
        release.wait(timeout=5.0)
        return {"scene_id": scene["scene_id"], "image_url": "/i.png", "error": None}

    # Cancel as soon as the first scene lands, then let everything drain.
    def _cancel_now() -> bool:
        release.set()
        return True

    with patch.object(image_gen, "_generate_one_scene", _slow_one):
        with patch.dict(os.environ, {"HH_IMAGE_GEN_CONCURRENCY": "2"}):
            results = image_gen.generate_batch(
                scenes=_scenes(20), script_id="sid", should_cancel=_cancel_now
            )

    # Only the in-flight workers may have run; the queued tail must be dropped.
    assert len(started) < 20
    assert len(results) < 20


def test_generate_batch_survives_a_failing_progress_callback():
    def boom(done: int, total: int) -> None:
        raise RuntimeError("progress sink died")

    with patch.object(image_gen, "_generate_one_scene", _fake_one):
        results = image_gen.generate_batch(scenes=_scenes(3), script_id="sid", on_scene_done=boom)

    assert len(results) == 3


def test_job_exposes_unit_counts_to_pollers():
    from pipeline.render_jobs import create_job, get_job, update_job

    job = create_job(scene_count=58)
    update_job(job.id, completed_units=12, total_units=58)
    stored = get_job(job.id)
    assert stored is not None

    payload = stored.to_dict()
    assert payload["completed_units"] == 12
    assert payload["total_units"] == 58
