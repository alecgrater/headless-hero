"""Eli pose picker — selects one character pose per scene via the routed LLM provider."""

import json
import logging
import os
import re

from integrations.llm_client import chat
from pipeline.character_frames import get_manifest
from prompts import ELI_POSE_PICKER_BATCH_SYSTEM, ELI_POSE_PICKER_SYSTEM

logger = logging.getLogger(__name__)

CORNERS = ["TL", "TR", "BL", "BR"]
LEFT_CORNERS = {"TL", "BL"}
RIGHT_CORNERS = {"TR", "BR"}
BOTTOM_CORNERS = {"BL", "BR"}

_BATCH_SIZE = 20

# Heuristic cues mapped to pose-id prefixes. The first prefix that has a
# matching frame in the manifest wins. Keep these tight: when the regex
# fires, we want high confidence the pose category fits — anything
# ambiguous should fall through to the LLM batch. Common filler words
# like "first/then/so/next/because" are deliberately excluded so the
# heuristic doesn't fire on the vast majority of educational narration.
_HEURISTIC_RULES: list[tuple[re.Pattern[str], tuple[str, ...]]] = [
    (re.compile(r"\b(why|how come|wonder(?:s|ed)?|hmm|imagine|what if)\b", re.IGNORECASE),
     ("thinking_", "curious_")),
    (re.compile(r"(?:!{2,}|\bwow\b|\bincredible\b|\bamazing\b|\bsurpris(?:e|ing|ed)\b|\bshocking\b|\bunbelievable\b)", re.IGNORECASE),
     ("excited_", "surprised_")),
    (re.compile(r"\b(warning|danger(?:ous)?|risky|beware|catastrophic|deadly|fatal)\b", re.IGNORECASE),
     ("serious_", "warning_", "stern_")),
]


def _pick_corner(previous_corner: str | None) -> str:
    """Deterministic corner alternation: left↔right, 70% bottom."""
    if not previous_corner:
        return "BR"
    if previous_corner in LEFT_CORNERS:
        return "BR"
    return "BL"


def _heuristics_enabled() -> bool:
    raw = os.environ.get("ELI_HEURISTICS_ENABLED", "1").strip().lower()
    return raw not in {"0", "false", "no", "off", ""}


def _heuristic_pose(narration: str, frame_ids: list[str]) -> str | None:
    """Pick a frame id deterministically when the narration tone is obvious.

    Returns None when no rule matches, or when a matched rule has no
    corresponding pose in the available manifest.
    """
    if not narration or not frame_ids:
        return None
    for pattern, prefixes in _HEURISTIC_RULES:
        if not pattern.search(narration):
            continue
        for prefix in prefixes:
            for frame_id in frame_ids:
                if frame_id.startswith(prefix):
                    return frame_id
    return None


def _fallback_result(previous_corner: str | None, frame_ids: list[str]) -> dict:
    fallback_id = "neutral_standingneutral"
    if frame_ids and fallback_id not in frame_ids:
        fallback_id = frame_ids[0]
    return {"enabled": True, "corner": _pick_corner(previous_corner), "frame_id": fallback_id}


def _normalize_eli_entry(
    raw: dict,
    frame_ids: list[str],
    previous_corner: str | None,
) -> dict:
    frame_id = raw.get("frame_id", "neutral_standingneutral")
    corner = raw.get("corner", _pick_corner(previous_corner))
    if frame_id not in frame_ids:
        frame_id = "neutral_standingneutral" if "neutral_standingneutral" in frame_ids else frame_ids[0]
    if corner not in CORNERS or corner == previous_corner:
        corner = _pick_corner(previous_corner)
    return {"enabled": True, "corner": corner, "frame_id": frame_id}


def generate_scene_eli(
    narration: str,
    previous_corner: str | None = None,
    script_id: str | None = None,
    bypass_heuristics: bool = False,
) -> dict:
    """Pick one pose for a scene based on narration tone.

    Returns: {"enabled": True, "corner": "BR", "frame_id": "thinking_handonchin"}

    `bypass_heuristics=True` forces the LLM call even when a heuristic rule
    would match — used by the manual /api/eli/regenerate endpoint so users
    don't keep getting the same deterministic pose on regenerate.
    """
    manifest = get_manifest()
    if not manifest or not manifest.get("frames"):
        return {"enabled": True, "corner": _pick_corner(previous_corner), "frame_id": "neutral_standingneutral"}

    frame_ids = [f["id"] for f in manifest["frames"]]

    if not bypass_heuristics and _heuristics_enabled():
        heur = _heuristic_pose(narration, frame_ids)
        if heur is not None:
            return {"enabled": True, "corner": _pick_corner(previous_corner), "frame_id": heur}

    user_msg = json.dumps({
        "narration": narration,
        "available_poses": frame_ids,
        "previous_corner": previous_corner,
    })

    text = chat(
        system=ELI_POSE_PICKER_SYSTEM.template,
        user_message=user_msg,
        max_tokens=200,
        script_id=script_id,
        json_mode=True,
        task="eli",
    )

    try:
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        result = json.loads(text)
    except (json.JSONDecodeError, IndexError, AttributeError) as e:
        logger.warning("Failed to parse Eli pose response: %s — using fallback", e)
        return _fallback_result(previous_corner, frame_ids)

    return _normalize_eli_entry(result, frame_ids, previous_corner)


def generate_eli_batch(
    scenes: list[dict],
    script_id: str | None = None,
) -> dict[str, dict]:
    """Pick poses for many scenes in one LLM call per chunk of 20.

    Each scene dict needs `id` and `narration`. Returns a dict keyed by
    scene id. Scenes the heuristic resolves locally are filled in without
    hitting the LLM. Corners alternate via `_pick_corner` based on the
    scene immediately preceding it in the input list.
    """
    results: dict[str, dict] = {}
    if not scenes:
        return results

    manifest = get_manifest()
    if not manifest or not manifest.get("frames"):
        prev_corner: str | None = None
        for scene in scenes:
            sid = scene.get("id")
            if not sid:
                continue
            corner = _pick_corner(prev_corner)
            results[sid] = {"enabled": True, "corner": corner, "frame_id": "neutral_standingneutral"}
            prev_corner = corner
        return results

    frame_ids = [f["id"] for f in manifest["frames"]]
    use_heuristics = _heuristics_enabled()

    # Phase 1: heuristic pass. Decide what we can locally; collect the rest
    # for the batched LLM call.
    undecided: list[dict] = []
    heuristic_pose: dict[str, str] = {}
    for scene in scenes:
        sid = scene.get("id")
        if not sid:
            continue
        narration = scene.get("narration") or ""
        if use_heuristics:
            pose = _heuristic_pose(narration, frame_ids)
            if pose is not None:
                heuristic_pose[sid] = pose
                continue
        undecided.append(scene)

    # Phase 2: batched LLM calls for the undecided scenes.
    llm_pose: dict[str, str] = {}
    for chunk_start in range(0, len(undecided), _BATCH_SIZE):
        chunk = undecided[chunk_start:chunk_start + _BATCH_SIZE]
        chunk_payload = [
            {"id": sc.get("id"), "narration": sc.get("narration") or ""}
            for sc in chunk
        ]
        user_msg = json.dumps({
            "available_poses": frame_ids,
            "scenes": chunk_payload,
        })
        try:
            response = chat(
                system=ELI_POSE_PICKER_BATCH_SYSTEM.template,
                user_message=user_msg,
                max_tokens=2048,
                script_id=script_id,
                json_mode=True,
                task="eli",
            )
        except Exception:
            logger.warning(
                "[ELI] Batch call failed for chunk starting at %d; will retry per-scene",
                chunk_start, exc_info=True,
            )
            continue

        text = (response or "").strip()
        if text.startswith("```"):
            try:
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            except IndexError:
                pass
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            logger.warning(
                "[ELI] Batch response not valid JSON for chunk starting at %d",
                chunk_start, exc_info=True,
            )
            continue

        entries = parsed.get("scenes") if isinstance(parsed, dict) else parsed
        if not isinstance(entries, list):
            logger.warning("[ELI] Batch response missing 'scenes' array for chunk %d", chunk_start)
            continue

        for entry in entries:
            if not isinstance(entry, dict):
                continue
            eid = entry.get("id")
            fid = entry.get("frame_id")
            if not isinstance(eid, str) or not isinstance(fid, str):
                continue
            if fid in frame_ids:
                llm_pose[eid] = fid

    # Phase 3: stitch together corner assignments in input order so
    # alternation matches the sequential code path.
    prev_corner = None
    for scene in scenes:
        sid = scene.get("id")
        if not sid:
            continue
        pose = heuristic_pose.get(sid) or llm_pose.get(sid)
        if pose is None:
            continue
        corner = _pick_corner(prev_corner)
        results[sid] = {"enabled": True, "corner": corner, "frame_id": pose}
        prev_corner = corner

    still_undecided = sum(1 for sc in undecided if sc.get("id") not in llm_pose)
    logger.info(
        "[ELI] Batch picked %d/%d scenes (heuristics=%d, llm=%d, undecided=%d)",
        len(results), len(scenes), len(heuristic_pose), len(llm_pose), still_undecided,
    )
    return results
