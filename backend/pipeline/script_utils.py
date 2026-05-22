"""Pure-data helpers for navigating ScriptContent."""

from models.script import Scene, ScriptContent


def find_scene_in_content(content: ScriptContent, scene_id: str) -> Scene:
    """Find a scene by ID across all segments.

    Raises RuntimeError if the scene is not found.
    """
    for seg in content.segments:
        for sc in seg.scenes:
            if sc.id == scene_id:
                return sc
    raise RuntimeError(f"Scene {scene_id} not found in content")
