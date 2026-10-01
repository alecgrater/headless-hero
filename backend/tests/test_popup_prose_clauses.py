"""Popup items must name things, not narrate.

Narration from the first all-cloud run shipped popup cutouts of "It is a night
in November" and "Elena follows your eyes upward"; across every stored script,
20 of 25 extracted "lists" were prose like these.
"""

import pytest

from models.script import Scene
from pipeline import visual_treatments as vt


def _items(narration: str) -> list[str]:
    scene = Scene(id="s1", narration=narration, visual_prompt="")
    return [item for item, _ in (vt._marker_list_items(scene) or vt._natural_list_items(scene))]


@pytest.mark.parametrize("narration", [
    "It is a night in November, year sixteen, and you are 41, working your second midnight in a row.",
    "Elena follows your eyes upward and then back down to you, and you tell her the heading.",
    "People are suffering, doctors are too afraid to help.",
    "Walt, your trainer, is 43, dry as a cracker.",
    "One might be a message, one might be a reward, one might be nothing at all.",
    "You had something good — funny, sharp, maybe even perfect.",
    "After handwashing, mortality fell to around one, two percent.",
])
def test_prose_is_not_a_popup_list(narration):
    assert _items(narration) == []


@pytest.mark.parametrize("narration,expected", [
    ("Sterilize, pasteurize, quarantine, wash.", ["Sterilize", "pasteurize", "quarantine", "wash"]),
    ("She points to missing keys, spoiled lunch, and an angry prisoner.",
     ["She points to missing keys", "spoiled lunch", "an angry prisoner"]),
    ("The case file has clues, witnesses, and a sealed report.",
     ["The case file has clues", "witnesses", "a sealed report"]),
])
def test_real_lists_survive(narration, expected):
    assert _items(narration) == expected
