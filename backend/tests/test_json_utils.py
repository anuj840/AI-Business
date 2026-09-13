from app.services.ai.json_utils import extract_json


def test_extracts_plain_json():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extracts_json_from_markdown_fence():
    text = 'Sure, here it is:\n```json\n{"a": 1, "b": "two"}\n```'
    assert extract_json(text) == {"a": 1, "b": "two"}


def test_extracts_json_with_surrounding_prose():
    text = 'Here you go: {"a": 1} -- hope that helps!'
    assert extract_json(text) == {"a": 1}


def test_returns_none_for_garbage():
    assert extract_json("not json at all") is None


def test_returns_none_for_empty_string():
    assert extract_json("") is None
