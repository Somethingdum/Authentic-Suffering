"""Output parsing (P1). Rules PARSE-01..05. Pure functions; no I/O.

strip_think(text) -> (visible, reasoning|None)
  * Removes every ``<think>...</think>`` block (non-greedy, DOTALL, case-insensitive) and joins
    their inner text with "\n" as reasoning. An unclosed leading ``<think>`` (no closing tag)
    means the whole text is reasoning: return ("", inner). Visible text is .strip()-ed.

extract_json(text) -> dict | None   (PARSE-02)
  Try in order, return the first that json.loads to a dict:
  1. the whole stripped text;
  2. the LAST fenced block ```json ... ``` or ``` ... ```;
  3. the LAST balanced top-level {...} span found by scanning braces while respecting JSON
     string literals and escapes.
  Returns None when nothing parses. Never evaluates code. Never "repairs" JSON by guessing.

validate(data, model) -> (instance | None, error | None)   (PARSE-03)
  model.model_validate(data); on ValidationError return (None, short error string listing the
  first 5 error locations and messages).

split_sentences(text) -> list[str]   (PARSE-04, used by lint)
  A sentence ends at a run of [.!?] (so "..." counts as one terminator), optionally followed by
  ONE closing quote (" or ”), when what follows is end-of-text, or whitespace and then an
  uppercase letter, a digit or an opening quote (" or “). Never inside a quoted span (straight
  "..." or curly “...”). The terminator and closing quote stay with their sentence; pieces are
  .strip()-ed; empty pieces dropped. Examples (tests/contract/p01_lanes/test_parse.py):
  'She waited... and waited. Done.' -> ['She waited... and waited.', 'Done.'];
  'He said, "Stop. Now." Then he left.' -> ['He said, "Stop. Now."', 'Then he left.'].

extract_quotes(text) -> list[str]   (PARSE-05)
  All spans inside straight "..." or curly “...” quotes, in order, without the quote marks.
"""

from __future__ import annotations

import json
import re

THINK = re.compile(r"<think>(.*?)</think>", re.S | re.I)


def strip_think(text: str) -> tuple[str, str | None]:
    inner = THINK.findall(text)
    vis = THINK.sub("", text)
    m = re.match(r"\s*<think>(.*)$", vis, re.S | re.I)
    if m and "</think>" not in vis.lower():
        return "", m.group(1).strip() if not inner else "\n".join(inner + [m.group(1)])
    return vis.strip(), ("\n".join(inner) if inner else None)


def _balanced_spans(text):
    spans = []
    depth = 0
    start = None
    in_str = False
    esc = False
    for i, ch in enumerate(text):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            if depth > 0:
                in_str = True
            continue
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0:
                spans.append(text[start:i + 1])
    return spans


def _try(s):
    try:
        v = json.loads(s)
    except Exception:
        return None
    return v if isinstance(v, dict) else None


def extract_json(text: str) -> dict[str, Any] | None:
    t = text.strip()
    if not t:
        return None
    v = _try(t)
    if v is not None:
        return v
    fences = re.findall(r"```(?:json)?\s*\n?(.*?)```", t, re.S)
    if fences:
        v = _try(fences[-1].strip())
        if v is not None:
            return v
    spans = _balanced_spans(t)
    if spans:
        return _try(spans[-1])
    return None


def validate(data: dict[str, Any], model: type[BaseModel]) -> tuple[BaseModel | None, str | None]:
    from pydantic import ValidationError
    try:
        return model.model_validate(data), None
    except ValidationError as e:
        parts = [f"{'.'.join(str(x) for x in er['loc'])}: {er['msg']}" for er in e.errors()[:5]]
        return None, "; ".join(parts)


OPEN_Q = {'"': '"', "“": "”"}


def _old_split(text):
    out = []
    buf = ""
    i = 0
    n = len(text)
    quote = None
    while i < n:
        ch = text[i]
        buf += ch
        if quote:
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in OPEN_Q:
            # a straight quote closes if we are in a straight quote; handled above
            quote = OPEN_Q[ch]
            i += 1
            continue
        if ch in ".!?":
            j = i + 1
            while j < n and text[j] in ".!?":
                buf += text[j]
                j += 1
            k = j
            closing = ""
            if k < n and text[k] in ('"', "”") and False:
                pass
            # end of text?
            rest = text[k:]
            if rest.strip() == "":
                out.append(buf.strip())
                buf = ""
                i = n
                break
            m = re.match(r"\s+([A-Z0-9\"“])", rest)
            if m:
                out.append(buf.strip())
                buf = ""
                i = k
                continue
            i = k
            continue
        i += 1
    if buf.strip():
        out.append(buf.strip())
    return [s for s in out if s]


def split_sentences(text: str) -> list[str]:
    """Handles terminator + closing quote at the boundary."""
    out = []
    buf = []
    i, n = 0, len(text)
    quote = None
    while i < n:
        ch = text[i]
        buf.append(ch)
        if quote is not None:
            if ch == quote:
                quote = None
                # closing quote right after a terminator may end the sentence
                if len(buf) >= 2 and buf[-2] in ".!?":
                    rest = text[i + 1:]
                    if rest.strip() == "" or re.match(r"\s+[A-Z0-9\"“]", rest):
                        out.append("".join(buf).strip())
                        buf = []
            i += 1
            continue
        if ch == '"' or ch == "“":
            quote = '"' if ch == '"' else "”"
            i += 1
            continue
        if ch in ".!?":
            j = i + 1
            while j < n and text[j] in ".!?":
                buf.append(text[j])
                j += 1
            rest = text[j:]
            if rest.strip() == "" or re.match(r"\s+[A-Z0-9\"“]", rest):
                out.append("".join(buf).strip())
                buf = []
            i = j
            continue
        i += 1
    if "".join(buf).strip():
        out.append("".join(buf).strip())
    return out


def extract_quotes(text: str) -> list[str]:
    return [a or b for a, b in re.findall(r'"([^"]*)"|“([^”]*)”', text)]
