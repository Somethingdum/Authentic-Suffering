"""Implementation of narration/lint.py."""
from __future__ import annotations

import difflib
import re

WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
QUOTE_RE = re.compile(r'"[^"]*"|“[^”]*”')
SIMILE_RE = re.compile(r"\blike (?:a|an|the)\b|\bas if\b|\bas though\b", re.I)


def _stop():
    from .lint import STOPWORDS
    return STOPWORDS


def _passive_re():
    from .lint import IRREGULAR_PARTICIPLES
    return re.compile(r"\b(am|is|are|was|were|be|been|being|get|gets|got|gotten)\s+(\w+ly\s+)?(\w+ed|\w+en|"
                      + "|".join(IRREGULAR_PARTICIPLES) + r")\b", re.I)


def unquoted(text):
    return QUOTE_RE.sub(" ", text)


def normalise_tokens(text):
    return [w.lower().replace("'", "") for w in WORD_RE.findall(text)]


def content_ngrams(text, n, min_content):
    toks = normalise_tokens(text)
    stop = _stop()
    out = set()
    for i in range(len(toks) - n + 1):
        win = toks[i:i + n]
        if sum(1 for t in win if t not in stop and len(t) >= 3) >= min_content:
            out.add(" ".join(win))
    return out


def _count_phrases(text, phrases):
    n = 0
    for p in phrases:
        n += len(re.findall(r"\b" + re.escape(p) + r"\b", text, re.I))
    return n


def _sentences(text):
    from ..lanes.parse import split_sentences
    out = []
    for s in split_sentences(text):
        ws = WORD_RE.findall(unquoted(s))
        if ws:
            out.append((unquoted(s), ws))
    return out


def prose_metrics(text, style):
    from ..contracts.narration import ProseMetrics
    nq = unquoted(text)
    words = WORD_RE.findall(nq)
    nw = len(words)
    sents = _sentences(text)
    ns = len(sents)
    pre = _passive_re()
    passive = sum(1 for s, _w in sents if pre.search(s))
    exc = {e.lower() for e in style.adverb_exceptions}
    adv = sum(1 for w in words if w.lower().endswith("ly") and len(w) > 3 and w.lower() not in exc)
    absw = {a.lower() for a in style.abstract_words}
    abstract = sum(1 for w in words if w.lower() in absw)
    similes = len(SIMILE_RE.findall(nq))
    bigrams = {}
    for _s, ws in sents:
        if len(ws) >= 2:
            k = f"{ws[0].lower()} {ws[1].lower()}"
            bigrams[k] = bigrams.get(k, 0) + 1
    run = best = 0
    prev = None
    for _s, ws in sents:
        f = ws[0].lower()
        run = run + 1 if f == prev else 1
        prev = f
        best = max(best, run)
    return ProseMetrics(words=nw, sentences=ns, passive_ratio=(passive / ns if ns else 0.0),
                        adverb_ratio=(adv / nw if nw else 0.0), similes_per_200w=(similes * 200 / nw if nw else 0.0),
                        abstract_ratio=(abstract / nw if nw else 0.0),
                        vague_timers=_count_phrases(nq, style.vague_timers), banned_phrases=_count_phrases(nq, style.banned_phrases),
                        leak_phrases=_count_phrases(nq, style.leak_phrases),
                        max_same_opener_bigram=max(bigrams.values()) if bigrams else 0, max_consecutive_same_first_word=best)


def _norm_speech(s):
    s = s.lower()
    s = re.sub(r"[^a-z0-9' ]+", " ", s)
    return " ".join(s.split())


def lint_prose(text, packet, style, numbers, all_known_names):
    from ..contracts.narration import LintFinding, LintReport
    m = prose_metrics(text, style)
    f = []

    def err(rule, detail, sev="error"):
        f.append(LintFinding(rule=rule, detail=detail, severity=sev))
    if m.passive_ratio > numbers.max_passive_ratio:
        err("STYLE-PASSIVE", f"{m.passive_ratio:.2f} of sentences are passive (max {numbers.max_passive_ratio:.2f})")
    if m.adverb_ratio > numbers.max_adverb_ratio:
        err("STYLE-ADVERB", f"{m.adverb_ratio:.2f} of words are -ly adverbs (max {numbers.max_adverb_ratio:.2f})")
    if m.similes_per_200w > numbers.max_similes_per_200w:
        err("STYLE-SIMILE", f"{m.similes_per_200w:.1f} comparisons per 200 words (max {numbers.max_similes_per_200w:.1f})")
    if m.abstract_ratio > numbers.max_abstract_ratio:
        err("STYLE-ABSTRACT", f"{m.abstract_ratio:.2f} of words are abstract (max {numbers.max_abstract_ratio:.2f})")
    nq = unquoted(text)
    for p in style.vague_timers:
        if _count_phrases(nq, [p]):
            err("STYLE-VAGUE-TIME", p)
    for p in style.banned_phrases:
        if _count_phrases(nq, [p]):
            err("STYLE-BANNED", p)
    for p in style.leak_phrases:
        if _count_phrases(nq, [p]):
            err("DISC-LEAK", p)
    if m.max_same_opener_bigram > numbers.max_same_opener_bigram:
        err("STYLE-OPENER", f"{m.max_same_opener_bigram} sentences open with the same two words (max {numbers.max_same_opener_bigram})")
    if m.max_consecutive_same_first_word > numbers.max_consecutive_same_first_word:
        err("STYLE-REPEAT-START", f"{m.max_consecutive_same_first_word} sentences in a row start with the same word "
                                  f"(max {numbers.max_consecutive_same_first_word})")
    total = len(WORD_RE.findall(text))
    lo, hi = numbers.narration_words[packet.length]
    if total < lo:
        err("STYLE-LENGTH", f"{total} words (at least {lo})", "warning")
    elif total > hi * 1.25:
        err("STYLE-LENGTH", f"{total} words (at most {hi})")
    allowed = set(packet.allowed_names)
    for name in sorted(n for n in all_known_names if n and n not in allowed):
        if re.search(r"\b" + re.escape(name) + r"\b", nq):
            err("DISC-NAME", name)
    heard = [_norm_speech(l.words) for l in packet.lines if l.kind == "speech" and l.words]
    from ..lanes.parse import extract_quotes
    for q in extract_quotes(text):
        nqq = _norm_speech(q)
        if not nqq:
            continue
        if not any(difflib.SequenceMatcher(None, nqq, h).ratio() >= 0.9 for h in heard):
            err("DISC-SPEECH", q)
    block = set(packet.player_input_echo_block)
    for g in sorted(content_ngrams(nq, numbers.echo_n, numbers.echo_min_content_tokens) & block):
        err("ECHO-01", g)
    return LintReport(passed=not any(x.severity == "error" for x in f), metrics=m, findings=f)


def record_pc_input(tx, turn_index, text, numbers):
    from ..contracts.events import Event, EventType, WriteOp, WriteRecord
    from ..kernel.clock import now
    grams = sorted(content_ngrams(text, numbers.echo_n, numbers.echo_min_content_tokens))
    old = [dict(r) for r in tx.query("SELECT turn_index, ngram, source FROM echo_ledger WHERE turn_index <= ? ORDER BY turn_index, ngram, source",
                                     (turn_index - numbers.echo_window_turns,))]
    ws = [WriteRecord(op=WriteOp.DELETE, table="echo_ledger", key=o) for o in old]
    ws += [WriteRecord(op=WriteOp.INSERT, table="echo_ledger", values={"turn_index": turn_index, "ngram": g, "source": "pc_input",
                                                                         "licensed_uses": 0}) for g in grams]
    if not ws:
        return None
    return tx.commit_event(Event(type=EventType.ECHO_RECORD, writer="narration.lint", at=now(tx), turn_index=turn_index,
                                 payload={"added": grams, "expired": len(old)}, writes=ws))


def echo_block(tx, turn_index, numbers):
    return sorted({r[0] for r in tx.query("SELECT ngram FROM echo_ledger WHERE source='pc_input' AND turn_index > ?",
                                          (turn_index - numbers.echo_window_turns,))})


def check_line(tx, text, numbers):
    t = tx.query_one("SELECT turn_index FROM world_clock")[0]
    block = set(echo_block(tx, t, numbers))
    return sorted(content_ngrams(text, numbers.echo_n, numbers.echo_min_content_tokens) & block)
