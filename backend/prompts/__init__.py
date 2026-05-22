"""Central prompt registry — single source of truth for all AI prompts.

Shared registry for Headless Hero prompt definitions.

Domain prompts live in sibling modules and are re-exported here for backwards-compatible imports.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RetentionMeta:
    goal: str = ""
    failure_mode: str = ""
    metrics_to_watch: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PromptDef:
    name: str
    domain: str
    purpose: str
    template: str
    builder: Callable[..., str] | None = None
    inputs: list[str] = field(default_factory=list)
    expected_output_format: str = ""
    target_model: str = "claude"
    retention: RetentionMeta = field(default_factory=RetentionMeta)

    def build(self, *args: object, **kwargs: object) -> str:
        """Call the builder function, raising if this prompt has no builder."""
        if self.builder is None:
            raise TypeError(f"PromptDef {self.name!r} has no builder function")
        return self.builder(*args, **kwargs)


PROMPTS: dict[str, PromptDef] = {}


def register(prompt: PromptDef) -> PromptDef:
    """Register a PromptDef in the global registry and return it."""
    PROMPTS[prompt.name] = prompt
    return prompt


# ===================================================================
# DOMAIN: SEO
# ===================================================================


from .script import *  # noqa: F403
from .title_cards import *  # noqa: F403
from .fx import *  # noqa: F403
from .character import *  # noqa: F403
from .image import *  # noqa: F403
from .ideation import *  # noqa: F403


_CONTRADICTION_RULES: list[tuple[str, str, str, str]] = [
    (
        "text_in_images",
        r"NEVER include any text",
        r"(?<!never )(?<!NEVER )(?<!no )include.*text.*label",
        "Contradictory text-in-images instructions",
    ),
    (
        "segment_count",
        r"exactly \d+ or \d+ segments",
        r"any number of segments",
        "Contradictory segment count constraints",
    ),
    (
        "output_format",
        r"Return ONLY valid JSON",
        r"Return\s+(in\s+)?markdown",
        "Contradictory output format instructions",
    ),
]


def detect_conflicts() -> list[dict[str, str]]:
    """Scan all prompt templates for known contradiction patterns.

    Returns list of {rule, prompt_a, prompt_b, description} dicts.
    Empty list means no conflicts detected.
    """
    conflicts: list[dict[str, str]] = []
    all_prompts = list(PROMPTS.values())

    for rule_name, pattern_a, pattern_b, description in _CONTRADICTION_RULES:
        regex_a = re.compile(pattern_a, re.IGNORECASE)
        regex_b = re.compile(pattern_b, re.IGNORECASE)

        has_a: list[str] = []
        has_b: list[str] = []

        for p in all_prompts:
            text = p.template
            if regex_a.search(text):
                has_a.append(p.name)
            if regex_b.search(text):
                has_b.append(p.name)

        # Conflict exists if the SAME prompt matches BOTH contradictory patterns
        for name_a in has_a:
            if name_a in has_b:
                conflicts.append({
                    "rule": rule_name,
                    "prompt_a": name_a,
                    "prompt_b": name_a,
                    "description": description,
                })

    return conflicts


# Run conflict detection at import time (logs warnings only)
_import_conflicts = detect_conflicts()
if _import_conflicts:
    for c in _import_conflicts:
        logger.warning(
            "Prompt conflict detected [%s]: %s vs %s — %s",
            c["rule"], c["prompt_a"], c["prompt_b"], c["description"],
        )
