"""The guidance a user types at ideation must survive into script generation."""

import pytest
from pydantic import ValidationError

from api.ideas import GenerateIdeasRequest
from models.script import GenerateScriptRequest


def _script_request(**overrides):
    body = {"topic": "Why you still aren't happy", "format_id": "youtube-listicle"}
    body.update(overrides)
    return GenerateScriptRequest(**body)


def test_long_guide_accepted_at_ideation_is_accepted_at_script_generation():
    """Guide mode is a free-text textarea; ideation caps nothing, so neither can
    script generation. A cap here 422s the exact value the app just produced."""
    guidance = "Explain the angle in detail. " * 200  # ~5600 chars

    GenerateIdeasRequest(niche="happiness", guide=guidance)

    assert _script_request(creator_guidance=guidance).creator_guidance == guidance


def test_creator_guidance_stays_optional():
    assert _script_request().creator_guidance is None
    assert _script_request(creator_guidance=None).creator_guidance is None


def test_topic_is_still_required_and_non_empty():
    with pytest.raises(ValidationError):
        _script_request(topic="")
