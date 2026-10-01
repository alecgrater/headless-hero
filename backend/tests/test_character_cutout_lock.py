"""Parallel scene jobs must not rebuild the project character cutout at the same time."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor

from pipeline import main_character


def test_concurrent_stale_checks_rebuild_once(monkeypatch, tmp_path):
    reference, cutout, metadata = tmp_path / "reference.png", tmp_path / "cutout.png", tmp_path / "metadata.json"
    reference.write_bytes(b"ref")
    builds = []
    gate = threading.Barrier(8)

    def needs_processing(*, reference_path, cutout_path, metadata_path):
        return not cutout_path.exists()

    def slow_build(**_kwargs):
        builds.append(1)
        time.sleep(0.05)  # long enough for every other thread to reach the check
        cutout.write_bytes(b"cutout")

    monkeypatch.setattr(main_character, "_cutout_needs_processing", needs_processing)
    monkeypatch.setattr(main_character, "process_character_asset_bundle", slow_build)

    def call(_):
        gate.wait()
        return main_character._ensure_current_character_cutout(
            reference_path=reference, cutout_path=cutout, metadata_path=metadata)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(call, range(8)))

    assert len(builds) == 1
    assert results.count(True) == 1
