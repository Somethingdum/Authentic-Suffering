"""Output parsing (P1). Rules PARSE-01..05 (lanes/parse.py)."""

from __future__ import annotations

import pytest

from as_engine.contracts.mind import SayMyWayOutput
from as_engine.lanes.parse import extract_json, extract_quotes, split_sentences, strip_think, validate

pytestmark = pytest.mark.phase(1)


def test_strip_think():
    """PARSE-01: think blocks removed and returned as reasoning; unclosed leading think = all reasoning."""
    assert strip_think("<think>plan A</think>  Hello  ") == ("Hello", "plan A")
    vis, rea = strip_think("<THINK>a</THINK>x<think>b</think>y")
    assert vis == "xy" and rea == "a\nb"
    assert strip_think("<think>never closed") == ("", "never closed")
    assert strip_think("no thinking here") == ("no thinking here", None)


def test_extract_json_order_and_refusal_to_guess():
    """PARSE-02: whole text -> last fenced block -> last balanced {...}; None when nothing parses."""
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('noise ```json\n{"a": 1}\n``` more ```\n{"a": 2}\n```') == {"a": 2}
    assert extract_json('I think {"x": "has } brace", "n": 1} and then {"y": 2}') == {"y": 2}
    assert extract_json('prefix {"x": "a \\" quote } inside", "n": 3} suffix') == {"x": 'a " quote } inside', "n": 3}
    assert extract_json("[1, 2, 3]") is None  # a list is not an object
    assert extract_json('{"a": 1,}') is None  # never repaired
    assert extract_json("") is None


def test_validate_reports_locations():
    """PARSE-03: (instance, None) or (None, short error naming the failing fields)."""
    ok, err = validate({"line": "hi", "survived": "intact"}, SayMyWayOutput)
    assert ok is not None and err is None
    bad, err = validate({"line": "", "survived": "maybe"}, SayMyWayOutput)
    assert bad is None and "line" in err and "survived" in err


def test_split_sentences():
    """PARSE-04: split on . ! ? + space, never inside quotes; ellipsis rules."""
    assert split_sentences("One. Two! Three?") == ["One.", "Two!", "Three?"]
    assert split_sentences('He said, "Stop. Now." Then he left.') == ['He said, "Stop. Now."', "Then he left."]
    assert split_sentences("She waited... and waited. Done.") == ["She waited... and waited.", "Done."]
    assert split_sentences("Wait... Then it moved.") == ["Wait...", "Then it moved."]
    assert split_sentences("Curly “quote. inside.” end.") == ["Curly “quote. inside.” end."]
    assert split_sentences("") == []


def test_extract_quotes():
    """PARSE-05: every straight or curly quoted span, in order, without marks."""
    assert extract_quotes('Mara said "Quiet." and June asked “What was that?”') == ["Quiet.", "What was that?"]
    assert extract_quotes("no quotes") == []
