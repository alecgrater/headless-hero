"""Tests for parse_json_array_response — unwraps OpenAI json_object wrapping."""

import pytest

from config import parse_json_array_response


def test_plain_array():
    assert parse_json_array_response('[{"a": 1}, {"a": 2}]') == [{"a": 1}, {"a": 2}]


def test_array_with_markdown_fences():
    assert parse_json_array_response('```json\n[{"a": 1}]\n```') == [{"a": 1}]


def test_dict_wrapped_array():
    raw = '{"ideas": [{"title": "x"}, {"title": "y"}]}'
    assert parse_json_array_response(raw) == [{"title": "x"}, {"title": "y"}]


def test_numeric_keyed_dict():
    raw = '{"0": {"title": "x"}, "1": {"title": "y"}, "2": {"title": "z"}}'
    assert parse_json_array_response(raw) == [
        {"title": "x"},
        {"title": "y"},
        {"title": "z"},
    ]


def test_numeric_keys_sorted_numerically():
    raw = '{"10": {"i": 10}, "2": {"i": 2}, "1": {"i": 1}}'
    assert parse_json_array_response(raw) == [{"i": 1}, {"i": 2}, {"i": 10}]


def test_rejects_unrecognized_dict():
    with pytest.raises(ValueError):
        parse_json_array_response('{"foo": 1, "bar": 2}')


def test_rejects_top_level_string():
    with pytest.raises(ValueError):
        parse_json_array_response('"hello"')
