"""Build remote content profile artifacts from an uploaded script snapshot."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.setdefault("HEADLESS_HERO_DISABLE_USAGE_THREAD", "1")

from pipeline.remote_content_profile import build_remote_profile_artifacts  # noqa: E402


def _default_analysis_provider() -> str | None:
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    return None


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate content profile and discovery seed artifacts from a profile input snapshot."
    )
    parser.add_argument("--input", default="discovery/content-profile-input.json")
    parser.add_argument("--profile-output", default="frontend/public/discovery/content-profile.json")
    parser.add_argument("--seed-output", default="discovery/content-profile-seed.json")
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Profile input snapshot missing: {input_path}; keeping previous profile artifacts.")
        return 0

    provider = _default_analysis_provider()
    if provider and not os.environ.get("ANALYSIS_LLM_PROVIDER"):
        os.environ["ANALYSIS_LLM_PROVIDER"] = provider
    if not provider and os.environ.get("ANALYSIS_LLM_PROVIDER", "").strip().lower() != "ollama":
        print("OPENAI_API_KEY or ANTHROPIC_API_KEY missing; keeping previous profile artifacts.")
        return 0

    snapshot = json.loads(input_path.read_text())
    profile, seed = build_remote_profile_artifacts(snapshot)
    _write_json(Path(args.profile_output), profile)
    _write_json(Path(args.seed_output), seed)
    print(f"Wrote remote content profile to {args.profile_output}")
    print(f"Wrote discovery seed to {args.seed_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
