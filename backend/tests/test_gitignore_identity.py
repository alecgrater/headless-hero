"""Guard the .gitignore allowlist that makes data/ safe to track.

data/ holds both the curated visual identity (committed) and runtime scratch
that must never reach a public repo — db.sqlite carries plaintext API keys and
data/projects/ carries every render. The ignore rules are deny-all plus explicit
negations; these assertions fail loudly if an edit re-opens that hole.
"""

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

MUST_BE_IGNORED = [
    "data/db.sqlite",
    "data/projects/abc-123/renders/full_youtube.mp4",
    "data/projects/abc-123/images/scene1.png",
    "data/projects/abc-123/audio/scene1.mp3",
    "data/test-lab/runs/run.json",
    "data/character/.DS_Store",
    "data/voices/sample.mp3",
    "data/brands/brand.json",
]

MUST_BE_TRACKED = [
    "data/identity.json",
    "data/style/presets/preset-id.png",
    "data/style/presets/preset-id/characters/char-id.png",
    "data/style/presets/preset-id/characters/char-id.cutout.png",
    "data/style/presets/preset-id/characters/char-id.metadata.json",
    "data/character/frames/smiling_waving_open.png",
    "data/character/manifest.json",
    "data/character/reference_selection.json",
    "data/character/references/reference_01.png",
    "data/character/thumbnail_references/ref.png",
    "data/projects/asset-vault/characters/char.png",
    "data/projects/asset-vault/items/item.png",
]


def _is_ignored(path: str) -> bool:
    result = subprocess.run(
        ["git", "check-ignore", "-q", path],
        cwd=REPO_ROOT,
        capture_output=True,
    )
    if result.returncode not in (0, 1):
        pytest.fail(f"git check-ignore failed for {path}: {result.stderr!r}")
    return result.returncode == 0


@pytest.mark.parametrize("path", MUST_BE_IGNORED)
def test_runtime_scratch_is_ignored(path: str) -> None:
    assert _is_ignored(path), f"{path} would be committed — it must stay ignored"


@pytest.mark.parametrize("path", MUST_BE_TRACKED)
def test_identity_assets_are_tracked(path: str) -> None:
    assert not _is_ignored(path), f"{path} is ignored — it must travel with the repo"
