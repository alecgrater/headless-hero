"""Tests for reading text out of an Anthropic Messages response."""

from types import SimpleNamespace

import pytest

from integrations.llm_client import _extract_anthropic_text


def _thinking(text: str = "") -> SimpleNamespace:
    return SimpleNamespace(type="thinking", thinking=text)


def _text(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)


def _response(*blocks: SimpleNamespace, stop_reason: str = "end_turn") -> SimpleNamespace:
    return SimpleNamespace(content=list(blocks), stop_reason=stop_reason)


def test_text_is_read_past_a_leading_thinking_block():
    """Claude 5 models think by default, so content[0] is a ThinkingBlock."""
    response = _response(_thinking(), _text('{"scenes": []}'))

    assert _extract_anthropic_text(response) == '{"scenes": []}'


def test_plain_text_only_response_is_unchanged():
    assert _extract_anthropic_text(_response(_text("hello"))) == "hello"


def test_multiple_text_blocks_are_joined_in_order():
    response = _response(_thinking(), _text("part one "), _text("part two"))

    assert _extract_anthropic_text(response) == "part one part two"


def test_truncation_while_thinking_names_max_tokens():
    """Thinking tokens count against max_tokens, so this is a live failure mode."""
    response = _response(_thinking("reasoning..."), stop_reason="max_tokens")

    with pytest.raises(RuntimeError, match="max_tokens"):
        _extract_anthropic_text(response)


def test_a_response_with_no_text_block_raises_rather_than_returning_empty():
    response = _response(_thinking(), stop_reason="refusal")

    with pytest.raises(RuntimeError, match="refusal"):
        _extract_anthropic_text(response)
