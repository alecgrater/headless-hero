"""Word-level comparison between transcribed audio and expected narration."""

import difflib
import re

from pydantic import BaseModel


class Deviation(BaseModel):
    type: str  # "missing" | "extra" | "substitution"
    expected: str | None = None
    actual: str | None = None
    position: int


class DeviationResult(BaseModel):
    match_ratio: float
    deviations: list[Deviation]
    transcript: str


def _normalize(text: str) -> list[str]:
    """Lowercase, strip punctuation, split into words."""
    text = re.sub(r"[^\w\s]", "", text.lower())
    return text.split()


def compute_deviation(transcribed_words: list[str], expected_narration: str) -> DeviationResult:
    """Compare transcribed words against expected narration using word-level diff."""
    expected_words = _normalize(expected_narration)
    actual_words = [re.sub(r"[^\w\s]", "", w.lower()) for w in transcribed_words]

    transcript = " ".join(transcribed_words)

    if not expected_words:
        return DeviationResult(match_ratio=1.0, deviations=[], transcript=transcript)

    matcher = difflib.SequenceMatcher(None, expected_words, actual_words)
    ratio = matcher.ratio()

    deviations: list[Deviation] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        elif tag == "delete":
            for pos in range(i1, i2):
                deviations.append(Deviation(type="missing", expected=expected_words[pos], position=pos))
        elif tag == "insert":
            for pos in range(j1, j2):
                deviations.append(Deviation(type="extra", actual=actual_words[pos], position=i1))
        elif tag == "replace":
            for offset in range(max(i2 - i1, j2 - j1)):
                exp = expected_words[i1 + offset] if (i1 + offset) < i2 else None
                act = actual_words[j1 + offset] if (j1 + offset) < j2 else None
                deviations.append(Deviation(
                    type="substitution" if exp and act else ("missing" if exp else "extra"),
                    expected=exp,
                    actual=act,
                    position=i1 + offset,
                ))

    return DeviationResult(match_ratio=ratio, deviations=deviations, transcript=transcript)
