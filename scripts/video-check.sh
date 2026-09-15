#!/bin/bash
# Verification helper for a full video run. Read-only: it inspects the app DB
# and generated files and prints what to look at. It changes nothing.
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
# `id` defaults to the most recently created script.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

PY="uv run --frozen --project backend python"

usage() { sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; }

run_py() { $PY - "$@"; }

cmd_preflight() {
  run_py <<'PYEOF'
import shutil
import sqlite3
import socket

def port_open(port):
    with socket.socket() as s:
        s.settimeout(1.0)
        return s.connect_ex(("127.0.0.1", port)) == 0

settings = dict(sqlite3.connect("data/db.sqlite").execute("select key, value from app_settings"))


def get(key, default=""):
    return (settings.get(key) or default).strip()


local_on = get("LOCAL_MODELS_ENABLED") == "true"


def source(modality):
    mode = get(f"LOCAL_{modality}_MODE", "auto")
    if mode in ("local", "cloud"):
        return mode
    return "local" if local_on else "cloud"


text, image, voice = source("TEXT"), source("IMAGE"), source("VOICE")
cutout_pref = get("LOCAL_IMAGE_CUTOUT_PROVIDER", "auto")
has_google = bool(get("GOOGLE_AI_KEY"))
if image == "cloud":
    cutout = "cloud"
elif cutout_pref == "local":
    cutout = "local"
elif cutout_pref == "cloud" or has_google:
    cutout = "cloud"
else:
    cutout = "local"

print("ROUTING")
print(f"  text            {text}")
print(f"  image (scenes)  {image}")
print(f"  image (cutouts) {cutout}")
print(f"  voice           {voice}")
if cutout == "local":
    print("  !! cutouts are local — popup/comparison crops will come out as opaque panels")

print()
print("CREDENTIALS")
for key, needed_when in (
    ("ANTHROPIC_API_KEY", text == "cloud"),
    ("OPENAI_API_KEY", text == "cloud"),
    ("GOOGLE_AI_KEY", image == "cloud" or cutout == "cloud"),
    ("ELEVENLABS_API_KEY", voice == "cloud"),
):
    have = bool(get(key))
    flag = "ok " if have else ("MISSING" if needed_when else "unset")
    print(f"  {flag:8} {key}{'' if have or not needed_when else '   <- required by the routing above'}")

print()
print("SERVICES")
print(f"  {'ok ' if port_open(8420) else 'DOWN':8} backend        :8420")
comfy_needed = image == "local" or cutout == "local"
state = "ok " if port_open(8188) else ("DOWN" if comfy_needed else "off")
print(f"  {state:8} ComfyUI        :8188{'   <- required for local scene images' if comfy_needed and state == 'DOWN' else ''}")
for port, name, needed in ((11434, "ollama", text == "local"), (8770, "mlx-audio", voice == "local")):
    state = "ok " if port_open(port) else ("DOWN" if needed else "off")
    note = "" if not needed or state == "ok " else "   <- required"
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
  $PY -c "
import sqlite3
row = sqlite3.connect('data/db.sqlite').execute(
    'select id from scripts order by created_at desc limit 1').fetchone()
print(row[0] if row else '')
"
}

cmd_latest() {
  run_py <<'PYEOF'
import sqlite3
c = sqlite3.connect("data/db.sqlite")
c.row_factory = sqlite3.Row
rows = c.execute(
    "select id, topic_title, format_id, created_at from scripts order by created_at desc limit 5"
).fetchall()
if not rows:
    print("no scripts yet")
for i, r in enumerate(rows):
    print(f"{'*' if i == 0 else ' '} {r['id']}  {r['format_id']:16}  {r['created_at'][:16]}  {r['topic_title'][:52]}")
PYEOF
}

cmd_script() {
  run_py "$1" <<'PYEOF'
import collections
import sqlite3
import sys

sid = sys.argv[1]
row = sqlite3.connect("data/db.sqlite").execute(
    "select script_json from scripts where id=?", (sid,)).fetchone()
if not row:
    raise SystemExit(f"no script {sid}")
import json
sc = json.loads(row[0])
scenes = [s for seg in sc["segments"] for s in seg["scenes"]]
modes = collections.Counter(s.get("visual_mode") for s in scenes)
print(f"{len(sc['segments'])} segments, {len(scenes)} scenes")
print(f"script rating: {(sc.get('script_rating') or {}).get('overall', 'n/a')}")
print()
print("VISUAL MODES")
for mode, n in modes.most_common():
    print(f"  {n:4}  {mode}")
print()
print("WHAT TO EXPECT AFTER THE FIXES")
print(f"  stat_card       {modes.get('stat_card', 0)}   (0-2; regex promotion is gone, so 0 is normal)")
print(f"  popup_sequence  {modes.get('popup_sequence', 0)}   (only genuine comma lists survive the gate now)")
bad_ctx = collections.Counter(
    s.get("renderer_context") for s in scenes
    if s.get("renderer_context") not in
    ("", None, "plain", "desk", "classroom", "office", "kitchen", "shop", "lab", "street")
)
if bad_ctx:
    print()
    print(f"  note: unrecognised renderer_context values {dict(bad_ctx)} — not in the documented set")
PYEOF
}

cmd_audio() {
  run_py "$1" <<'PYEOF'
import json
import sqlite3
import sys

sid = sys.argv[1]
row = sqlite3.connect("data/db.sqlite").execute(
    "select script_json from scripts where id=?", (sid,)).fetchone()
sc = json.loads(row[0])
scenes = [s for seg in sc["segments"] for s in seg["scenes"]]
missing = [s["id"] for s in scenes if not s.get("audio_duration_seconds")]
total = sum(s.get("audio_duration_seconds", 0) for s in scenes)
print(f"{len(scenes)} scenes, {total/60:.1f} min of audio, {len(missing)} without audio")

suspect = []
for s in scenes:
    words = len(s["narration"].split())
    dur = s.get("audio_duration_seconds", 0)
    if words and dur > words * 1.1 + 3:
        wt = s.get("word_timestamps") or []
        suspect.append((s["id"], words, round(dur, 1), round(wt[-1]["end_ms"] / 1000, 1) if wt else 0))

print()
if suspect:
    print("SCENES LONGER THAN THEIR NARRATION JUSTIFIES")
    print(f"  {'scene':12}{'words':>7}{'audio':>8}{'speech ends':>13}")
    for sid_, w, d, a in suspect:
        print(f"  {sid_:12}{w:7}{d:8}{a:13}")
    print()
    print("  On ElevenLabs this should be empty. On a local voice the runaway")
    print("  guard should have caught these — worth reporting if it did not.")
else:
    print("no scene runs longer than its word count justifies")
PYEOF
}

cmd_prep() {
  run_py "$1" <<'PYEOF'
import json
import sqlite3
import sys

sid = sys.argv[1]
row = sqlite3.connect("data/db.sqlite").execute(
    "select script_json from scripts where id=?", (sid,)).fetchone()
sc = json.loads(row[0])
prepared = sc.get("visual_modes_prepared", False)
scenes = [s for seg in sc["segments"] for s in seg["scenes"] if not s.get("is_title_card")]
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
  run_py "$1" <<'PYEOF'
import statistics
import sys
from pathlib import Path

from PIL import Image

sid = sys.argv[1]
root = Path("data/projects") / sid
groups = {
    "popup items": sorted(root.glob("popup_crops/*/crop_*.png")),
    "popup anchors": sorted(root.glob("popup_crops/*/anchor_cutout.png")),
    "comparison subjects": sorted(root.glob("comparison_boards/*/subject_*.png")),
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
            # Histogram rather than getdata(): same answer, no per-pixel Python
            # loop and no deprecation warning.
            clear = sum(alpha.histogram()[:16])
            values.append(clear / (im.width * im.height))
    median = statistics.median(values)
    verdict = "good" if median > 0.5 else "BROKEN — opaque panels, not cutouts"
    print(f"{label:22} n={len(values):3}  median {median:5.1%}  min {min(values):5.1%}  max {max(values):5.1%}  {verdict}")
if not found:
    print("no cutouts generated yet for this project")
else:
    print()
    print("Reference: the broken export measured 20% median on popup items;")
    print("the fixed Gemini path measured 80-91%.")
PYEOF
}

cmd_fx() {
  run_py "$1" <<'PYEOF'
import collections
import json
import sqlite3
import sys

sid = sys.argv[1]
row = sqlite3.connect("data/db.sqlite").execute(
    "select script_json from scripts where id=?", (sid,)).fetchone()
sc = json.loads(row[0])
scenes = [s for seg in sc["segments"] for s in seg["scenes"]]
fx = collections.Counter(
    (s.get("fx") or {}).get("effect") if isinstance(s.get("fx"), dict) else s.get("fx")
    for s in scenes
)
missing = fx.get(None, 0)
print(f"{len(scenes)} scenes, {missing} without FX")
for effect, n in fx.most_common():
    print(f"  {n:4}  {effect or '(none)'}")
if missing == len(scenes):
    print()
    print("  !! every scene is missing FX — the FX stage did not run.")
    print("     The last export shipped this way.")
PYEOF
}

cmd_cost() {
  run_py "$1" <<'PYEOF'
import sqlite3
import sys

sid = sys.argv[1]
c = sqlite3.connect("data/db.sqlite")
c.row_factory = sqlite3.Row
rows = c.execute(
    """select service, model, count(*) n, sum(images) imgs, sum(characters) chars,
              sum(cost_estimate) cost
       from api_usage where script_id=? group by service, model order by cost desc""",
    (sid,),
).fetchall()
if not rows:
    print("no usage recorded for this project yet")
    raise SystemExit(0)
total = 0.0
for r in rows:
    cost = r["cost"] or 0.0
    total += cost
    print(f"  {r['service']:14}{(r['model'] or '')[:30]:32} n={r['n']:4}  ${cost:7.3f}")
print(f"\n  TOTAL  ${total:.2f}   (projection for this configuration was ~$3.06)")

rows = c.execute(
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
      for step in script audio prep cutouts fx cost; do
        echo "=============== $step ==============="
        "cmd_$step" "$id"
        echo
      done
      ;;
    ""|-h|--help|help) usage ;;
    *) echo "unknown command: $cmd"; echo; usage; exit 1 ;;
  esac
}

main "$@"
