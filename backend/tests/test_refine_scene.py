import json

from models.script import Scene, ScriptContent, Segment


def test_life_as_a_refinement_uses_format_guardrails(monkeypatch):
    from pipeline import refine

    captured = {}

    def fake_chat(system: str, user: str, **kwargs):
        captured["system"] = system
        captured["user"] = user
        return json.dumps({
            "id": "scene-1",
            "narration": "You stand in the hallway with the keys in your hand.",
            "visual_prompt": "[CLOSE-UP] worn keys in a hand",
            "duration_estimate_seconds": 8,
            "is_title_card": False,
            "visual_mode": "full_frame",
            "visual_beat": "static",
            "frame_directives": [],
        })

    content = ScriptContent(
        title="Your Life As A Night Guard",
        format_id="life-as-a",
        intro_hook="You arrive before the building wakes.",
        segments=[
            Segment(name="Level 1, the new", scenes=[
                Scene(
                    id="scene-1",
                    narration="You stand in the hallway with the keys in your hand.",
                    visual_prompt="[CLOSE-UP] worn keys in a hand",
                ),
            ]),
        ],
    )
    monkeypatch.setattr(refine, "chat", fake_chat)

    refined = refine.refine_scene(content, 0, "scene-1")

    assert refined.id == "scene-1"
    assert "Format-Specific Guardrails: Your Life As A" in captured["system"]
    assert "Preserve second-person, present-tense narration" in captured["system"]
    assert "do not add listicle cadence" in captured["system"]
