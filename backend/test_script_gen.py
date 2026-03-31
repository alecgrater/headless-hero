#!/usr/bin/env python3
"""Standalone test for video script generation.

Usage:
    uv run python test_script_gen.py
    uv run python test_script_gen.py --topic "Why cats sleep so much"
    uv run python test_script_gen.py --model anthropic.claude-sonnet-4-6 --segments 6
    uv run python test_script_gen.py --list-models
"""

import argparse
import json
import logging
import os
import sys
import time

# Add backend to path so imports work standalone
sys.path.insert(0, os.path.dirname(__file__))

AVAILABLE_MODELS = [
    "claude-sonnet-4-20250514",
    "anthropic.claude-sonnet-4-6",
    "anthropic.claude-opus-4-6-v1",
    "anthropic.claude-sonnet-4-5-20250929-v1:0",
    "anthropic.claude-haiku-4-5-20251001-v1:0",
]

DEFAULT_TOPIC = "Why Do We Dream? The Science Behind Sleep"


def main():
    parser = argparse.ArgumentParser(description="Test video script generation")
    parser.add_argument("--topic", default=DEFAULT_TOPIC, help="Video topic")
    parser.add_argument("--description", default="", help="Optional angle/description")
    parser.add_argument("--brand", default="Test Brand", help="Brand name for context")
    parser.add_argument("--segments", type=int, default=None, help="Number of segments (default: let Claude decide)")
    parser.add_argument("--model", default=None, help="Model to use (overrides SCRIPT_MODEL env var)")
    parser.add_argument("--list-models", action="store_true", help="List available models and exit")
    parser.add_argument("--no-modifiers", action="store_true", help="Skip content modifiers")
    parser.add_argument("--output", default=None, help="Save output JSON to file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    args = parser.parse_args()

    if args.list_models:
        print("Available models:")
        for m in AVAILABLE_MODELS:
            marker = " (default)" if m == "claude-sonnet-4-20250514" else ""
            print(f"  {m}{marker}")
        return

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.model:
        os.environ["SCRIPT_MODEL"] = args.model

    # Import after path setup
    from pipeline.scriptwriter import generate_script

    model = os.environ.get("SCRIPT_MODEL", "claude-sonnet-4-20250514")
    modifier_ids = [] if args.no_modifiers else ["title_cards"]

    print(f"Topic:      {args.topic}")
    print(f"Model:      {model}")
    print(f"Segments:   {args.segments or 'auto'}")
    print(f"Modifiers:  {modifier_ids or 'none'}")
    print(f"{'—' * 50}")
    print("Generating script...\n")

    t0 = time.monotonic()
    try:
        content = generate_script(
            topic=args.topic,
            description=args.description,
            brand_context=args.brand,
            segment_count=args.segments,
            modifier_ids=modifier_ids,
            brand={"name": args.brand, "style_string": ""},
        )
    except Exception as e:
        elapsed = time.monotonic() - t0
        print(f"\nFAILED after {elapsed:.1f}s: {e}")
        sys.exit(1)

    elapsed = time.monotonic() - t0
    total_scenes = sum(len(s.scenes) for s in content.segments)

    print(f"SUCCESS in {elapsed:.1f}s")
    print(f"{'—' * 50}")
    print(f"Title:      {content.title}")
    print(f"Segments:   {len(content.segments)}")
    print(f"Scenes:     {total_scenes}")
    print(f"Intro hook: {content.intro_hook}")
    print()

    for i, seg in enumerate(content.segments):
        print(f"  [{i+1}] {seg.name} ({len(seg.scenes)} scenes)")
        for scene in seg.scenes:
            tag = " [TITLE]" if scene.is_title_card else ""
            frames = f" [{scene.frame_count} frames]" if scene.frame_count else ""
            print(f"      {scene.id}: {scene.narration[:80]}...{tag}{frames}")

    if args.output:
        out = json.loads(content.model_dump_json())
        with open(args.output, "w") as f:
            json.dump(out, f, indent=2)
        print(f"\nSaved to {args.output}")


if __name__ == "__main__":
    main()
