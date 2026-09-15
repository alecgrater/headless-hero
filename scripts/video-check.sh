#!/bin/bash
# Verification helper for a full video run. Read-only: it opens the app database
# in read-only mode, inspects generated files, and prints what to look at.
#
#   bash scripts/video-check.sh preflight        services, keys, routing, disk
#   bash scripts/video-check.sh latest           newest script id + title
#   bash scripts/video-check.sh script  [id]     scene + visual mode breakdown
#   bash scripts/video-check.sh audio   [id]     scene durations vs word counts
#   bash scripts/video-check.sh prep    [id]     was visual mode prep applied
#   bash scripts/video-check.sh cutouts [id]     cutout transparency
#   bash scripts/video-check.sh fx      [id]     FX assignment coverage
#   bash scripts/video-check.sh cost    [id]     recorded spend
#   bash scripts/video-check.sh all     [id]     every check above
#
# `id` defaults to the most recently created non-Test-Lab script.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

PY="uv run --frozen --project backend python"

usage() { sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'; }

run_py() { $PY - "$@"; }

# Every python block starts by importing this, so the checks call the same
# functions the pipeline does rather than reimplementing them. Reimplementation
# is how this script previously claimed a valid renderer_context was invalid.
read -r -d '' PRELUDE <<'PYEOF'
import json
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, "backend")

DB = Path(os.environ.get("HH_DATA_DIR", "data")) / "db.sqlite"
DATA = Path(os.environ.get("HH_DATA_DIR", "data"))


def db():
    if not DB.exists():
        print(f"no app database at {DB} — start the app once first")
        raise SystemExit(1)
    # mode=ro so a typo can never create or migrate the real database.
    conn = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def load_settings_into_env():
    """Mirror api.settings.load_keys_into_env so imported code resolves the same."""
    for key, value in db().execute("select key, value from app_settings"):
        if value:
            os.environ[key] = value


def script_row(script_id):
    row = db().execute("select script_json from scripts where id=?", (script_id,)).fetchone()
    if row is None:
        print(f"no script with id {script_id}")
        raise SystemExit(1)
    content = json.loads(row["script_json"] or "{}")
    if not content.get("segments"):
        print("this script has no segments — generation probably failed")
        raise SystemExit(1)
    return content


def scenes_of(content):
    return [s for seg in content["segments"] for s in seg["scenes"]]
PYEOF

cmd_preflight() {
  run_py <<PYEOF
$PRELUDE

import shutil
import socket

load_settings_into_env()

from integrations.image_client import CUTOUT_SHEET, SCENE, resolved_provider
from integrations.llm_client import LLM_TASKS, _resolve_provider
from pipeline.voiceover import active_voice_engine


def port_open(port):
    with socket.socket() as s:
        s.settimeout(1.0)
        return s.connect_ex(("127.0.0.1", port)) == 0


scene_provider = resolved_provider(SCENE)
cutout_provider = resolved_provider(CUTOUT_SHEET)
voice = active_voice_engine()
# Per task, not per modality: fx/seo/media/eli all have their own provider key
# and can sit on ollama even when the script model is a cloud one.
task_providers = {task: _resolve_provider(task) for task in LLM_TASKS}
ollama_tasks = sorted(t for t, p in task_providers.items() if p == "ollama")

print("ROUTING")
print(f"  image (scenes)  {scene_provider}")
print(f"  image (cutouts) {cutout_provider}")
print(f"  voice           {voice}")
print(f"  text            {'ollama for ' + ', '.join(ollama_tasks) if ollama_tasks else 'cloud for every task'}")
if cutout_provider == "local":
    print("  !! cutouts are local — popup/comparison crops will come out as opaque panels")

print()
print("CREDENTIALS")
needs = {
    "ANTHROPIC_API_KEY": "anthropic" in task_providers.values(),
    "OPENAI_API_KEY": "openai" in task_providers.values(),
    "GOOGLE_AI_KEY": "google" in (scene_provider, cutout_provider),
    "ELEVENLABS_API_KEY": voice == "elevenlabs",
}
for key, needed in needs.items():
    have = bool((os.environ.get(key) or "").strip())
    flag = "ok " if have else ("MISSING" if needed else "unset")
    note = "   <- required by the routing above" if needed and not have else ""
    print(f"  {flag:8} {key}{note}")

print()
print("SERVICES")
comfy_needed = "local" in (scene_provider, cutout_provider)
services = [
    (8420, "backend", True),
    (8188, "ComfyUI", comfy_needed),
    (11434, "ollama", bool(ollama_tasks)),
    (8770, "mlx-audio", voice != "elevenlabs"),
]
for port, name, needed in services:
    up = port_open(port)
    state = "ok " if up else ("DOWN" if needed else "off")
    note = "   <- required" if needed and not up else ""
    print(f"  {state:8} {name:14} :{port}{note}")

print()
free_gb = shutil.disk_usage(".").free / 1024**3
print("DISK")
print(f"  {free_gb:.0f} GB free  (the last full project used ~1.1 GB)")
if free_gb < 10:
    print("  !! low — a render plus its exports can need several GB")
PYEOF
}

resolve_id() {
  if [ -n "${1:-}" ]; then echo "$1"; return; fi
  run_py <<PYEOF
$PRELUDE

row = db().execute(
    "select id from scripts where coalesce(is_test_lab, 0) = 0 order by created_at desc limit 1"
).fetchone()
print(row["id"] if row else "")
PYEOF
}

cmd_latest() {
  run_py <<PYEOF
$PRELUDE

rows = db().execute(
    """select id, topic_title, format_id, created_at from scripts
       where coalesce(is_test_lab, 0) = 0 order by created_at desc limit 5"""
).fetchall()
if not rows:
    print("no scripts yet")
for i, r in enumerate(rows):
    marker = "*" if i == 0 else " "
    print(f"{marker} {r['id']}  {r['format_id']:16}  {r['created_at'][:16]}  {(r['topic_title'] or '')[:52]}")
PYEOF
}

cmd_script() {
  run_py "$1" <<PYEOF
$PRELUDE

import collections

from pipeline.renderer_context import RENDERER_CONTEXTS

content = script_row(sys.argv[1])
scenes = scenes_of(content)
modes = collections.Counter(s.get("visual_mode") for s in scenes)
print(f"{len(content['segments'])} segments, {len(scenes)} scenes")
print(f"script rating: {(content.get('script_rating') or {}).get('overall', 'n/a')}")
print()
print("VISUAL MODES")
for mode, n in modes.most_common():
    print(f"  {n:4}  {mode}")
print()
print("WHAT TO EXPECT AFTER THE FIXES")
print(f"  stat_card       {modes.get('stat_card', 0)}   (0-2 and only real figures; regex promotion is gone)")
print("  popup_sequence      script generation still emits these freely — the")
print("                      prose gate empties their layers later, during")
print("                      visual mode prep, so judge the count after that.")

allowed = set(RENDERER_CONTEXTS) | {"", None}
unknown = collections.Counter(
    s.get("renderer_context") for s in scenes if s.get("renderer_context") not in allowed
)
if unknown:
    print()
    print(f"  note: renderer_context values outside {sorted(RENDERER_CONTEXTS)}: {dict(unknown)}")
PYEOF
}

cmd_audio() {
  run_py "$1" <<PYEOF
$PRELUDE

from pipeline.speech_validation import evaluate_speech_length, spoken_end_seconds

content = script_row(sys.argv[1])
scenes = scenes_of(content)
missing = [s["id"] for s in scenes if not s.get("audio_duration_seconds")]
total = sum(s.get("audio_duration_seconds", 0) for s in scenes)
print(f"{len(scenes)} scenes, {total/60:.1f} min of audio, {len(missing)} without audio")

# The same classifier the local TTS client uses, so this can never disagree
# with what the pipeline would have accepted or resampled.
bad = []
for s in scenes:
    spoken = s.get("tts_narration") or s.get("narration") or ""
    duration = s.get("audio_duration_seconds", 0)
    verdict = evaluate_speech_length(
        word_count=len(spoken.split()),
        audio_seconds=duration,
        spoken_end_seconds=spoken_end_seconds(s.get("word_timestamps") or []),
    )
    if verdict.status != "ok":
        bad.append((s["id"], len(spoken.split()), round(duration, 1), verdict.status))

print()
if bad:
    print("SCENES WHOSE AUDIO DOES NOT MATCH THEIR NARRATION")
    print(f"  {'scene':12}{'words':>7}{'audio':>8}  problem")
    for scene_id, words, duration, status in bad:
        label = "trailing junk after the speech" if status == "trim" else "runaway / looping generation"
        print(f"  {scene_id:12}{words:7}{duration:8}  {label}")
    print()
    print("  On ElevenLabs this should be empty. On a local voice the runaway")
    print("  guard should have caught these — worth reporting if it did not.")
else:
    print("every scene's audio length matches its narration")
PYEOF
}

cmd_prep() {
  run_py "$1" <<PYEOF
$PRELUDE

content = script_row(sys.argv[1])
prepared = content.get("visual_modes_prepared", False)
scenes = [s for s in scenes_of(content) if not s.get("is_title_card")]
no_timing = [s["id"] for s in scenes if not s.get("word_timestamps")]
print(f"visual_modes_prepared: {prepared}")
if prepared:
    print("  the analysis ran — you did not have to press the button")
else:
    print("  not yet. It runs automatically when images are generated,")
    print("  provided every non-title scene has voiceover word timing.")
if no_timing:
    print(f"  blocked by {len(no_timing)} scene(s) with no word timing: {no_timing[:5]}")
PYEOF
}

cmd_cutouts() {
  run_py "$1" <<PYEOF
$PRELUDE

import statistics

from PIL import Image

root = DATA / "projects" / sys.argv[1]
groups = {
    "popup items": sorted(root.glob("popup_crops/*/crop_*.png")),
    "popup anchors": sorted(root.glob("popup_crops/*/anchor_cutout.png")),
    # subject_[0-9]* so the opaque contact sheet (subject_sheet.png) is excluded.
    "comparison subjects": sorted(root.glob("comparison_boards/*/subject_[0-9]*.png")),
    "stat card icons": sorted(root.glob("stat_cards/*/icon_cutout.png")),
}
found = False
for label, paths in groups.items():
    if not paths:
        continue
    found = True
    values = []
    for p in paths:
        with Image.open(p) as im:
            alpha = im.convert("RGBA").getchannel("A")
            values.append(sum(alpha.histogram()[:16]) / (im.width * im.height))
    median = statistics.median(values)
    verdict = "good" if median > 0.5 else "BROKEN — opaque panels, not cutouts"
    print(f"{label:22} n={len(values):3}  median {median:5.1%}  min {min(values):5.1%}  max {max(values):5.1%}  {verdict}")
if not found:
    print("no cutouts generated yet for this project")
else:
    print()
    print("Reference: the broken local path measured 20% median across 40 item")
    print("crops. A 3-item Test Lab probe on the Gemini path measured 80-91%,")
    print("which is promising but a small sample — >50% is the bar.")
PYEOF
}

cmd_fx() {
  run_py "$1" <<PYEOF
$PRELUDE

content = script_row(sys.argv[1])
scenes = scenes_of(content)
# SceneFX is {zoom_punch, drift} — there is no "effect" field. Reading one is
# how this check previously reported every scene as missing FX.
zoom = sum(1 for s in scenes if (s.get("fx") or {}).get("zoom_punch"))
drift = sum(1 for s in scenes if (s.get("fx") or {}).get("drift"))
none = [s["id"] for s in scenes if not any((s.get("fx") or {}).get(k) for k in ("zoom_punch", "drift"))]
print(f"{len(scenes)} scenes: {zoom} with zoom_punch, {drift} with drift, {len(none)} with neither")
if len(none) == len(scenes):
    print()
    print("  !! no scene has any FX — the FX stage did not run.")
elif none:
    print(f"  scenes without FX: {none[:8]}{' ...' if len(none) > 8 else ''}")
    print("  Some scenes legitimately get none; a handful here is normal.")
PYEOF
}

cmd_cost() {
  run_py "$1" <<PYEOF
$PRELUDE

conn = db()
rows = conn.execute(
    """select service, model, count(*) n, sum(cost_estimate) cost
       from api_usage where script_id=? group by service, model order by cost desc""",
    (sys.argv[1],),
).fetchall()
if not rows:
    print("no usage recorded for this project yet")
    raise SystemExit(0)
total = 0.0
for r in rows:
    cost = r["cost"] or 0.0
    total += cost
    print(f"  {r['service']:14}{(r['model'] or '')[:30]:32} n={r['n']:4}  \$ {cost:7.3f}")
print(f"\n  TOTAL  \$ {total:.2f}   (projection for this configuration was ~\$3.06)")

rows = conn.execute(
    """select operation_type, engine, round(sum(duration_seconds)/60,1) mins
       from generation_durations group by operation_type, engine
       order by sum(duration_seconds) desc limit 8"""
).fetchall()
print("\n  slowest operations across all runs (minutes):")
for r in rows:
    print(f"    {r['mins']:7}  {r['operation_type']}  {r['engine'] or ''}")
PYEOF
}

main() {
  local cmd="${1:-}"
  shift || true
  case "$cmd" in
    preflight) cmd_preflight ;;
    latest)    cmd_latest ;;
    script|audio|prep|cutouts|fx|cost)
      local id
      id="$(resolve_id "${1:-}")"
      [ -n "$id" ] || { echo "no script found — pass an id"; exit 1; }
      echo "script $id"
      echo
      "cmd_$cmd" "$id"
      ;;
    all)
      local id
      id="$(resolve_id "${1:-}")"
      [ -n "$id" ] || { echo "no script found — pass an id"; exit 1; }
      echo "script $id"
      for step in script audio prep cutouts fx cost; do
        echo
        echo "=============== $step ==============="
        "cmd_$step" "$id"
      done
      ;;
    ""|-h|--help|help) usage ;;
    *) echo "unknown command: $cmd"; echo; usage; exit 1 ;;
  esac
}

main "$@"
