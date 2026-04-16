# Scene Duration Variance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure high-energy scenes (quick_cuts, aha_subtitle) stay punchy by adding duration guidance to the scriptwriter prompt and a post-voiceover rewrite pass that tightens any scene over 10 seconds.

**Architecture:** Two-layer approach — (1) upstream prompt guidance in `script_prompt.md` so Claude writes shorter narration for high-energy beats, and (2) a new `pipeline/duration_variance.py` module that checks actual audio durations after batch voiceover and rewrites + re-voices any overruns in a single pass. Called from the batch voiceover endpoint.

**Tech Stack:** Python 3.12, FastAPI, Anthropic SDK (via existing `claude_client`), ElevenLabs TTS (via existing `voiceover` pipeline), SQLModel, pytest

**Spec:** `docs/superpowers/specs/2026-04-16-scene-duration-variance-design.md`

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `backend/prompts/script_prompt.md:104-105` | Add duration guidance to quick_cuts and aha_subtitle beat definitions |
| Create | `backend/pipeline/duration_variance.py` | Duration check + Claude rewrite + re-voice orchestration |
| Modify | `backend/api/voiceover.py:1-2,166-167` | Import and call `check_and_tighten` after batch persist |
| Create | `backend/tests/test_duration_variance.py` | Unit tests for the duration variance module |

---

### Task 1: Add duration guidance to scriptwriter prompt

**Files:**
- Modify: `backend/prompts/script_prompt.md:104-105`

- [ ] **Step 1: Update quick_cuts beat definition**

In `backend/prompts/script_prompt.md`, line 104, change:

```
- "quick_cuts" — When narration covers multiple examples, lists, comparisons, or rapid context switches. 3-8 frames with reference_previous: false and transition: "cut" (primarily). Each frame is a completely DIFFERENT shot — different subject, angle, composition. Use deliberately for visual energy.
```

to:

```
- "quick_cuts" — When narration covers multiple examples, lists, comparisons, or rapid context switches. 3-8 frames with reference_previous: false and transition: "cut" (primarily). Each frame is a completely DIFFERENT shot — different subject, angle, composition. Use deliberately for visual energy. Narration should be 1 short punchy sentence — aim for under 8 seconds of speech.
```

- [ ] **Step 2: Update aha_subtitle beat definition**

In `backend/prompts/script_prompt.md`, line 105, change:

```
- "aha_subtitle" — When a sentence delivers a shocking stat, counterintuitive fact, or "wait, really?" moment. Pure white text on black. 1 frame directive with source: "subtitle". Aim for 5-6 per video, no more than 7. Must be preceded and followed by image-bearing beats for contrast. visual_prompt should be empty.
```

to:

```
- "aha_subtitle" — When a sentence delivers a shocking stat, counterintuitive fact, or "wait, really?" moment. Pure white text on black. 1 frame directive with source: "subtitle". Aim for 5-6 per video, no more than 7. Must be preceded and followed by image-bearing beats for contrast. visual_prompt should be empty. Narration should be 1 short sentence — a single stat or fact, under 8 seconds of speech.
```

- [ ] **Step 3: Commit**

```bash
cd ~/git/headless-hero && git add backend/prompts/script_prompt.md && git commit -m "Add duration guidance to quick_cuts and aha_subtitle beat definitions"
```

---

### Task 2: Create duration variance module — scene flagging logic

**Files:**
- Create: `backend/pipeline/duration_variance.py`
- Create: `backend/tests/test_duration_variance.py`

- [ ] **Step 1: Create test file with test for flagging logic**

Create `backend/tests/__init__.py` (empty) and `backend/tests/test_duration_variance.py`:

```python
"""Tests for the duration variance check-and-tighten pipeline."""

import json
from unittest.mock import patch, MagicMock

import pytest

# Add backend to path so imports resolve
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.duration_variance import (
    HIGH_ENERGY_BEATS,
    MAX_DURATION_SECONDS,
    _flag_overlong_scenes,
)
from models.script import ScriptContent


def _make_script_content(scenes_data: list[dict]) -> ScriptContent:
    """Build a minimal ScriptContent with one segment containing given scenes."""
    scenes = []
    for i, sd in enumerate(scenes_data):
        scenes.append({
            "id": sd.get("id", f"scene_{i:03d}"),
            "narration": sd.get("narration", "Test narration."),
            "visual_prompt": "",
            "visual_beat": sd.get("visual_beat", "static"),
            "audio_duration_seconds": sd.get("audio_duration_seconds", 0.0),
        })
    return ScriptContent(
        title="Test Video",
        segments=[{"name": "Test Segment", "scenes": scenes}],
    )


class TestFlagOverlongScenes:
    def test_no_high_energy_scenes_returns_empty(self):
        content = _make_script_content([
            {"visual_beat": "static", "audio_duration_seconds": 15.0},
            {"visual_beat": "continuous", "audio_duration_seconds": 12.0},
        ])
        flagged = _flag_overlong_scenes(content)
        assert flagged == []

    def test_high_energy_under_threshold_returns_empty(self):
        content = _make_script_content([
            {"visual_beat": "quick_cuts", "audio_duration_seconds": 8.0},
            {"visual_beat": "aha_subtitle", "audio_duration_seconds": 6.0},
        ])
        flagged = _flag_overlong_scenes(content)
        assert flagged == []

    def test_high_energy_over_threshold_flagged(self):
        content = _make_script_content([
            {"id": "scene_001", "visual_beat": "quick_cuts", "audio_duration_seconds": 12.5},
            {"id": "scene_002", "visual_beat": "static", "audio_duration_seconds": 15.0},
            {"id": "scene_003", "visual_beat": "aha_subtitle", "audio_duration_seconds": 11.0},
        ])
        flagged = _flag_overlong_scenes(content)
        assert len(flagged) == 2
        assert flagged[0].id == "scene_001"
        assert flagged[1].id == "scene_003"

    def test_exactly_at_threshold_not_flagged(self):
        content = _make_script_content([
            {"visual_beat": "quick_cuts", "audio_duration_seconds": 10.0},
        ])
        flagged = _flag_overlong_scenes(content)
        assert flagged == []

    def test_high_energy_no_audio_not_flagged(self):
        content = _make_script_content([
            {"visual_beat": "quick_cuts", "audio_duration_seconds": 0.0},
        ])
        flagged = _flag_overlong_scenes(content)
        assert flagged == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/git/headless-hero/backend && uv run python -m pytest tests/test_duration_variance.py -v
```

Expected: ImportError — `pipeline.duration_variance` does not exist yet.

- [ ] **Step 3: Create duration_variance.py with constants and flagging function**

Create `backend/pipeline/duration_variance.py`:

```python
"""Duration variance — tighten overlong high-energy scenes after voiceover.

After batch voiceover, checks quick_cuts and aha_subtitle scenes against a
duration threshold. If any exceed it, rewrites narration via Claude and
re-voices in a single pass.
"""

import json
import logging

from config import DEFAULT_TTS_MODEL, strip_markdown_fences
from integrations.claude_client import chat
from models.script import Scene, Script, ScriptContent
from pipeline.voiceover import generate_scene_audio

logger = logging.getLogger(__name__)

HIGH_ENERGY_BEATS = {"quick_cuts", "aha_subtitle"}
MAX_DURATION_SECONDS = 10.0


def _flag_overlong_scenes(content: ScriptContent) -> list[Scene]:
    """Return high-energy scenes whose audio exceeds the duration threshold."""
    flagged: list[Scene] = []
    for scene in content.all_scenes():
        if (
            scene.visual_beat in HIGH_ENERGY_BEATS
            and scene.audio_duration_seconds > MAX_DURATION_SECONDS
        ):
            flagged.append(scene)
    return flagged
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd ~/git/headless-hero/backend && uv run python -m pytest tests/test_duration_variance.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/git/headless-hero && git add backend/pipeline/duration_variance.py backend/tests/__init__.py backend/tests/test_duration_variance.py && git commit -m "Add duration variance module with scene flagging logic and tests"
```

---

### Task 3: Add Claude rewrite function

**Files:**
- Modify: `backend/pipeline/duration_variance.py`
- Modify: `backend/tests/test_duration_variance.py`

- [ ] **Step 1: Add test for the rewrite function**

Append to `backend/tests/test_duration_variance.py`:

```python
from pipeline.duration_variance import _rewrite_narrations

TIGHTEN_SYSTEM_PROMPT = (
    "You are a script editor. You will receive high-energy video scenes whose narration is too long.\n"
    "Rewrite each narration to be shorter and punchier while preserving the core fact or message.\n"
    "- quick_cuts scenes: 1 short punchy sentence\n"
    "- aha_subtitle scenes: 1 short sentence with the key stat or fact\n"
    'Return ONLY valid JSON: {"scene_id": "new narration", ...}'
)


class TestRewriteNarrations:
    @patch("pipeline.duration_variance.chat")
    def test_returns_mapping_from_claude_response(self, mock_chat):
        mock_chat.return_value = json.dumps({
            "scene_001": "Shorter version.",
            "scene_003": "Punchy fact.",
        })
        scenes = [
            MagicMock(id="scene_001", visual_beat="quick_cuts", narration="Long narration here.", audio_duration_seconds=12.5),
            MagicMock(id="scene_003", visual_beat="aha_subtitle", narration="Another long narration.", audio_duration_seconds=11.0),
        ]
        result = _rewrite_narrations(scenes, script_id="test-script")
        assert result == {"scene_001": "Shorter version.", "scene_003": "Punchy fact."}
        mock_chat.assert_called_once()
        call_kwargs = mock_chat.call_args
        assert "script_id" in call_kwargs.kwargs or call_kwargs[1].get("script_id")

    @patch("pipeline.duration_variance.chat")
    def test_returns_empty_on_claude_failure(self, mock_chat):
        mock_chat.side_effect = RuntimeError("API error")
        scenes = [
            MagicMock(id="scene_001", visual_beat="quick_cuts", narration="Long.", audio_duration_seconds=12.0),
        ]
        result = _rewrite_narrations(scenes, script_id="test-script")
        assert result == {}

    @patch("pipeline.duration_variance.chat")
    def test_returns_empty_on_invalid_json(self, mock_chat):
        mock_chat.return_value = "not valid json"
        scenes = [
            MagicMock(id="scene_001", visual_beat="quick_cuts", narration="Long.", audio_duration_seconds=12.0),
        ]
        result = _rewrite_narrations(scenes, script_id="test-script")
        assert result == {}
```

- [ ] **Step 2: Run tests to verify new tests fail**

```bash
cd ~/git/headless-hero/backend && uv run python -m pytest tests/test_duration_variance.py::TestRewriteNarrations -v
```

Expected: ImportError — `_rewrite_narrations` does not exist yet.

- [ ] **Step 3: Implement _rewrite_narrations**

Add to `backend/pipeline/duration_variance.py`, after `_flag_overlong_scenes`:

```python
_TIGHTEN_SYSTEM_PROMPT = (
    "You are a script editor. You will receive high-energy video scenes whose narration is too long.\n"
    "Rewrite each narration to be shorter and punchier while preserving the core fact or message.\n"
    "- quick_cuts scenes: 1 short punchy sentence\n"
    "- aha_subtitle scenes: 1 short sentence with the key stat or fact\n"
    'Return ONLY valid JSON: {"scene_id": "new narration", ...}'
)


def _rewrite_narrations(
    scenes: list[Scene],
    script_id: str | None = None,
) -> dict[str, str]:
    """Call Claude to rewrite overlong narrations. Returns {scene_id: new_narration}.

    Returns empty dict on any failure (best-effort).
    """
    payload = [
        {
            "scene_id": sc.id,
            "visual_beat": sc.visual_beat,
            "narration": sc.narration,
            "current_duration_seconds": sc.audio_duration_seconds,
        }
        for sc in scenes
    ]

    try:
        response = chat(
            system=_TIGHTEN_SYSTEM_PROMPT,
            user_message=json.dumps(payload, indent=2),
            max_tokens=2048,
            script_id=script_id,
        )
        cleaned = strip_markdown_fences(response)
        result = json.loads(cleaned)
        if not isinstance(result, dict):
            logger.warning("Claude returned non-dict for narration rewrite: %s", type(result))
            return {}
        logger.info("Claude rewrote %d narrations", len(result))
        return result
    except Exception:
        logger.exception("Failed to rewrite narrations via Claude")
        return {}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd ~/git/headless-hero/backend && uv run python -m pytest tests/test_duration_variance.py -v
```

Expected: All 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/git/headless-hero && git add backend/pipeline/duration_variance.py backend/tests/test_duration_variance.py && git commit -m "Add Claude narration rewrite function to duration variance module"
```

---

### Task 4: Add the check_and_tighten orchestrator

**Files:**
- Modify: `backend/pipeline/duration_variance.py`
- Modify: `backend/tests/test_duration_variance.py`

- [ ] **Step 1: Add test for check_and_tighten**

Append to `backend/tests/test_duration_variance.py`:

```python
from pipeline.duration_variance import check_and_tighten
from config import DEFAULT_TTS_MODEL


def _make_script_record(scenes_data: list[dict]) -> tuple:
    """Build a Script record and ScriptContent for testing."""
    content = _make_script_content(scenes_data)
    record = MagicMock()
    record.script_json = content.model_dump_json()
    return record, content


class TestCheckAndTighten:
    @patch("pipeline.duration_variance.generate_scene_audio")
    @patch("pipeline.duration_variance.chat")
    def test_no_overlong_scenes_returns_empty(self, mock_chat, mock_audio):
        record, _ = _make_script_record([
            {"id": "scene_001", "visual_beat": "quick_cuts", "audio_duration_seconds": 8.0},
        ])
        session = MagicMock()
        session.get.return_value = record

        result = check_and_tighten(
            script_id="test-script",
            session=session,
            voice_id="voice-123",
        )
        assert result == []
        mock_chat.assert_not_called()
        mock_audio.assert_not_called()

    @patch("pipeline.duration_variance.generate_scene_audio")
    @patch("pipeline.duration_variance.chat")
    def test_rewrites_and_revoices_overlong_scenes(self, mock_chat, mock_audio):
        record, _ = _make_script_record([
            {"id": "scene_001", "visual_beat": "quick_cuts", "narration": "Too long narration.", "audio_duration_seconds": 12.5},
            {"id": "scene_002", "visual_beat": "static", "narration": "Normal scene.", "audio_duration_seconds": 8.0},
        ])
        session = MagicMock()
        session.get.return_value = record

        mock_chat.return_value = json.dumps({"scene_001": "Short version."})
        mock_audio.return_value = ("/static/projects/test/audio/scene_001.mp3", 7.5, [{"word": "Short", "start_ms": 0, "end_ms": 500}])

        result = check_and_tighten(
            script_id="test-script",
            session=session,
            voice_id="voice-123",
        )
        assert result == ["scene_001"]
        mock_audio.assert_called_once_with(
            scene_id="scene_001",
            narration="Short version.",
            voice_id="voice-123",
            script_id="test-script",
            model_id=DEFAULT_TTS_MODEL,
            voice_settings=None,
        )
        # Verify DB persistence
        session.add.assert_called_once_with(record)
        session.commit.assert_called_once()

        # Verify updated script_json
        updated_content = ScriptContent.model_validate(json.loads(record.script_json))
        scene_001 = updated_content.segments[0].scenes[0]
        assert scene_001.narration == "Short version."
        assert scene_001.audio_duration_seconds == 7.5

    @patch("pipeline.duration_variance.generate_scene_audio")
    @patch("pipeline.duration_variance.chat")
    def test_skips_scene_if_revoice_fails(self, mock_chat, mock_audio):
        record, _ = _make_script_record([
            {"id": "scene_001", "visual_beat": "aha_subtitle", "narration": "Long fact.", "audio_duration_seconds": 11.0},
        ])
        session = MagicMock()
        session.get.return_value = record

        mock_chat.return_value = json.dumps({"scene_001": "Short fact."})
        mock_audio.side_effect = RuntimeError("ElevenLabs down")

        result = check_and_tighten(
            script_id="test-script",
            session=session,
            voice_id="voice-123",
        )
        # Scene was not successfully re-voiced, so not in result
        assert result == []
```

- [ ] **Step 2: Run tests to verify new tests fail**

```bash
cd ~/git/headless-hero/backend && uv run python -m pytest tests/test_duration_variance.py::TestCheckAndTighten -v
```

Expected: ImportError or AttributeError — `check_and_tighten` signature doesn't match yet.

- [ ] **Step 3: Implement check_and_tighten**

Add to `backend/pipeline/duration_variance.py`, after `_rewrite_narrations`:

```python
def check_and_tighten(
    script_id: str,
    session,  # sqlmodel.Session — not typed to avoid circular import
    voice_id: str,
    model_id: str = DEFAULT_TTS_MODEL,
    voice_settings: dict | None = None,
) -> list[str]:
    """Check high-energy scenes for duration overruns and rewrite if needed.

    Called after batch voiceover. Returns list of scene IDs that were
    rewritten and re-voiced. Best-effort — failures are logged, not raised.
    """
    record = session.get(Script, script_id)
    if not record:
        logger.warning("Script %s not found for duration variance check", script_id)
        return []

    content = ScriptContent.model_validate(json.loads(record.script_json))
    flagged = _flag_overlong_scenes(content)

    if not flagged:
        logger.info("[%s] Duration variance: no high-energy scenes over %.0fs",
                     script_id, MAX_DURATION_SECONDS)
        return []

    logger.info("[%s] Duration variance: %d high-energy scenes over %.0fs — %s",
                 script_id, len(flagged), MAX_DURATION_SECONDS,
                 [f"{s.id} ({s.audio_duration_seconds:.1f}s)" for s in flagged])

    rewrites = _rewrite_narrations(flagged, script_id=script_id)
    if not rewrites:
        logger.info("[%s] Duration variance: no rewrites returned", script_id)
        return []

    # Build scene lookup for updating
    scene_map = {sc.id: sc for seg in content.segments for sc in seg.scenes}

    tightened: list[str] = []
    for scene_id, new_narration in rewrites.items():
        scene = scene_map.get(scene_id)
        if not scene:
            logger.warning("[%s] Rewrite returned unknown scene_id: %s", script_id, scene_id)
            continue

        try:
            audio_url, duration, word_timestamps = generate_scene_audio(
                scene_id=scene_id,
                narration=new_narration,
                voice_id=voice_id,
                script_id=script_id,
                model_id=model_id,
                voice_settings=voice_settings,
            )
            old_duration = scene.audio_duration_seconds
            scene.narration = new_narration
            scene.audio_url = audio_url
            scene.audio_duration_seconds = duration
            if word_timestamps is not None:
                scene.word_timestamps = word_timestamps
            tightened.append(scene_id)
            logger.info("[%s] Tightened scene %s: %.1fs -> %.1fs",
                         script_id, scene_id, old_duration, duration)
        except Exception:
            logger.exception("[%s] Failed to re-voice scene %s, keeping original",
                              script_id, scene_id)

    if tightened:
        record.script_json = content.model_dump_json()
        session.add(record)
        session.commit()
        logger.info("[%s] Duration variance: tightened %d scenes: %s",
                     script_id, len(tightened), tightened)

    return tightened
```

- [ ] **Step 4: Run all tests to verify they pass**

```bash
cd ~/git/headless-hero/backend && uv run python -m pytest tests/test_duration_variance.py -v
```

Expected: All 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/git/headless-hero && git add backend/pipeline/duration_variance.py backend/tests/test_duration_variance.py && git commit -m "Add check_and_tighten orchestrator to duration variance module"
```

---

### Task 5: Integrate into batch voiceover endpoint

**Files:**
- Modify: `backend/api/voiceover.py:1-2,166-167`

- [ ] **Step 1: Add import to voiceover.py**

In `backend/api/voiceover.py`, add to the module-level imports (after line 20):

```python
from pipeline.duration_variance import check_and_tighten
```

- [ ] **Step 2: Add check_and_tighten call after batch persist**

In `backend/api/voiceover.py`, after line 166 (`session.commit()`), add:

```python

    # Check high-energy scene durations and tighten if needed
    tightened = check_and_tighten(
        script_id=body.script_id,
        session=session,
        voice_id=body.voice_id,
        model_id=body.model_id,
        voice_settings=body.voice_settings,
    )
    if tightened:
        logger.info("Duration variance: rewrote %d scenes: %s", len(tightened), tightened)
```

- [ ] **Step 3: Verify the backend starts**

```bash
cd ~/git/headless-hero && npm run dev:backend &
sleep 3
curl -s http://localhost:8420/health | head -1
kill %1
```

Expected: `{"status":"ok"}` — backend boots without import errors.

- [ ] **Step 4: Run all tests**

```bash
cd ~/git/headless-hero/backend && uv run python -m pytest tests/ -v
```

Expected: All 11 tests PASS.

- [ ] **Step 5: Commit and push**

```bash
cd ~/git/headless-hero && git add backend/api/voiceover.py && git commit -m "Integrate duration variance check into batch voiceover endpoint" && git push
```
