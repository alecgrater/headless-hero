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


def test_a_refusal_after_partial_text_raises_instead_of_returning_the_fragment():
    """A streamed turn can be declined mid-answer; the prefix is not an answer."""
    response = _response(_text('{"scenes": [{"narr'), stop_reason="refusal")

    with pytest.raises(RuntimeError, match="declined"):
        _extract_anthropic_text(response)


class _FakeStream:
    def __init__(self, message):
        self._message = message

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        return self._message


class _FakeMessages:
    def __init__(self, message):
        self.message = message
        self.stream_kwargs = None

    def create(self, **kwargs):  # pragma: no cover - must not be used
        raise AssertionError("Anthropic calls must stream")

    def stream(self, **kwargs):
        self.stream_kwargs = kwargs
        return _FakeStream(self.message)


def test_chat_streams_anthropic_calls_and_prices_cached_tokens_disjointly(monkeypatch):
    from integrations import llm_client

    usage = SimpleNamespace(
        input_tokens=1_000,
        output_tokens=2_000,
        cache_read_input_tokens=10_000,
        cache_creation_input_tokens=0,
    )
    message = SimpleNamespace(content=[_text("ok")], stop_reason="end_turn", usage=usage)
    messages = _FakeMessages(message)
    monkeypatch.setattr(llm_client, "get_anthropic_client", lambda: SimpleNamespace(messages=messages))
    monkeypatch.setattr(llm_client, "_resolve_provider", lambda task: "anthropic")
    recorded = {}
    monkeypatch.setattr(llm_client, "record_usage", lambda **kw: recorded.update(kw))

    assert llm_client.chat("sys", "hi", model="claude-sonnet-5-5", cache=True, max_tokens=32768) == "ok"

    assert messages.stream_kwargs["max_tokens"] == 32768
    # Claude 5.5 models 400 on any of these; chat() must never send them.
    assert not {"thinking", "temperature", "top_p", "top_k", "tool_choice"} & messages.stream_kwargs.keys()
    # Sonnet 5.5: $2 in, $10 out, $0.20 cache read per million tokens.
    expected = 1_000 * 2e-6 + 10_000 * 0.2e-6 + 2_000 * 10e-6
    assert recorded["cost_estimate"] == pytest.approx(expected)


class _FailingStream:
    """A stream that opens, then fails while the body is being read."""

    def __init__(self, error):
        self._error = error

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def get_final_message(self):
        raise self._error


class _FlakyMessages(_FakeMessages):
    def __init__(self, message, failures, *, on_open=False):
        super().__init__(message)
        self.failures = list(failures)
        self.on_open = on_open
        self.calls = 0

    def stream(self, **kwargs):
        self.calls += 1
        if self.failures:
            error = self.failures.pop(0)
            if self.on_open:
                raise error
            return _FailingStream(error)
        return super().stream(**kwargs)


def _anthropic_status_error(status: int):
    import anthropic
    import httpx

    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(status, request=request)
    return anthropic.APIStatusError("boom", response=response, body=None)


def test_a_mid_stream_failure_is_retried_once():
    import httpx

    from integrations.llm_client import _anthropic_message

    message = SimpleNamespace(content=[_text("ok")], stop_reason="end_turn")
    messages = _FlakyMessages(message, [httpx.ReadTimeout("stalled")])
    client = SimpleNamespace(messages=messages)

    assert _anthropic_message(client, "claude-sonnet-5-5", 100, "sys", "hi", 30.0) is message
    assert messages.calls == 2


def test_a_mid_stream_server_error_on_the_200_response_is_retried():
    from integrations.llm_client import _anthropic_message

    message = SimpleNamespace(content=[_text("ok")], stop_reason="end_turn")
    messages = _FlakyMessages(message, [_anthropic_status_error(200)])

    assert _anthropic_message(SimpleNamespace(messages=messages), "m", 100, "s", "hi", 30.0) is message


def test_a_client_error_is_not_retried():
    from integrations.llm_client import _anthropic_message

    messages = _FlakyMessages(None, [_anthropic_status_error(400)])

    with pytest.raises(Exception, match="boom"):
        _anthropic_message(SimpleNamespace(messages=messages), "m", 100, "s", "hi", 30.0)
    assert messages.calls == 1


def test_a_second_failure_propagates():
    import httpx

    from integrations.llm_client import _anthropic_message

    messages = _FlakyMessages(None, [httpx.ReadTimeout("a"), httpx.ReadTimeout("b")])

    with pytest.raises(httpx.ReadTimeout):
        _anthropic_message(SimpleNamespace(messages=messages), "m", 100, "s", "hi", 30.0)
    assert messages.calls == 2


def test_a_failure_to_open_the_stream_is_left_to_the_sdk_retries():
    """The SDK already retried the open; retrying again would multiply attempts."""
    import httpx

    from integrations.llm_client import _anthropic_message

    messages = _FlakyMessages(None, [httpx.ConnectError("refused")], on_open=True)

    with pytest.raises(httpx.ConnectError):
        _anthropic_message(SimpleNamespace(messages=messages), "m", 100, "s", "hi", 30.0)
    assert messages.calls == 1
