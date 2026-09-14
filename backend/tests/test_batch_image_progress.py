"""A long image batch must report progress, or pollers abandon it mid-run.

The frontend's `pollBackgroundJob` times out when `job.progress` stops
advancing, not on total elapsed time. `generate_batch` used to report nothing
between start and finish, so any batch slower than the stall budget (30 min in
Local Mode) was abandoned while its thread kept generating — the UI then
retried the whole batch against an orphaned first run.
"""

from unittest.mock import patch

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
    with patch.object(image_gen, "_generate_one_scene", _fake_one):
        results = image_gen.generate_batch(
            scenes=_scenes(20),
            script_id="sid",
            should_cancel=lambda: True,
            on_scene_done=lambda d, t: None,
        )

    # Cancelling after the first completion must not run the whole list.
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
    payload = get_job(job.id).to_dict()

    assert payload["completed_units"] == 12
    assert payload["total_units"] == 58
