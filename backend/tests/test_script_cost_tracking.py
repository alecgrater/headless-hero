from pipeline import scriptwriter
from pipeline.modifiers import title_cards


def test_single_pass_script_generation_attributes_llm_usage(monkeypatch):
    calls = []

    def fake_chat(*args, **kwargs):
        calls.append(kwargs)
        return """
        {
          "title": "Test Script",
          "intro_hook": "Hook.",
          "outro_cta": "",
          "segments": [
            {
              "name": "Segment",
              "scenes": [
                {
                  "id": "scene_001",
                  "narration": "Narration.",
                  "visual_prompt": "[WIDE] Visual."
                }
              ]
            }
          ]
        }
        """

    monkeypatch.setattr(scriptwriter, "chat", fake_chat)
    monkeypatch.setattr(title_cards, "enforce_title_cards_and_min_scenes", lambda content: content)

    scriptwriter.generate_script("Topic", segmented=False, script_id="script-123")

    assert calls
    assert calls[0]["task"] == "script"
    assert calls[0]["script_id"] == "script-123"


def test_segmented_script_generation_attributes_all_llm_usage(monkeypatch):
    calls = []

    def fake_chat(*args, **kwargs):
        calls.append(kwargs)
        if len(calls) == 1:
            return """
            {
              "title": "Segmented Script",
              "intro_hook": "Hook.",
              "outro_cta": "",
              "segments": [
                {
                  "name": "Segment A",
                  "topic_summary": "A",
                  "circle_color": "#ffffff",
                  "title_card_image_prompt": "Card A"
                },
                {
                  "name": "Segment B",
                  "topic_summary": "B",
                  "circle_color": "#ffffff",
                  "title_card_image_prompt": "Card B"
                }
              ]
            }
            """
        return """
        {
          "scenes": [
            {
              "id": "scene_001",
              "narration": "Narration.",
              "visual_prompt": "[WIDE] Visual."
            }
          ]
        }
        """

    monkeypatch.setattr(scriptwriter, "chat", fake_chat)
    monkeypatch.setattr(title_cards, "enforce_title_cards_and_min_scenes", lambda content: content)

    scriptwriter.generate_script("Topic", segmented=True, script_id="script-456")

    assert len(calls) == 3
    assert all(call["task"] == "script" for call in calls)
    assert all(call["script_id"] == "script-456" for call in calls)
