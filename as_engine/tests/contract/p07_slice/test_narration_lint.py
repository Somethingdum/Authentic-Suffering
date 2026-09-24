"""Render lint and the echo ledger (P7). Rules STYLE-01..06, DISC-01..04, ECHO-01..03, NARR-00,
NARR-06, NARR-07 (narration/lint.py, narration/narrator.py narrate).

Prose quality is measured by code; quoted speech belongs to the speaker and is never measured.
The narrator may quote only what the PC heard, name only whom the PC knows and perceives, and may
not parrot the player's own phrasing back. The narrator is a reader: it writes its prose row and
nothing else.
"""

from __future__ import annotations

import ast
import asyncio
import json
from pathlib import Path

import pytest

from as_engine.contracts.common import CallClass
from as_engine.contracts.narration import NarratorLine, NarratorPacket
from as_engine.contracts.settings import EngineConfig, RulesConfig
from as_engine.lanes.client import LaneClient
from as_engine.narration import lint, narrator

pytestmark = pytest.mark.phase(7)

NUM = RulesConfig().style


@pytest.fixture
def style(canon):
    return canon.find("style", "narration")


def packet(**kw):
    base = dict(turn_index=1, world_time_text="23:14, day 18 since the Fall (night)", place_text="Sales floor", pc_name="Owen",
                allowed_names=["Owen", "Mara", "June"], length="short")
    base.update(kw)
    return NarratorPacket(**base)


SAMPLE = ("The door was opened slowly. The wind cut like a knife. She waits. She listens. She breathes. "
          "Later the dread passes. It is a testament to nothing.")


def test_prose_metrics(style):
    """STYLE-02: every metric, counted by hand for SAMPLE (27 words, 7 sentences)."""
    m = lint.prose_metrics(SAMPLE, style)
    assert (m.words, m.sentences) == (27, 7)
    assert m.passive_ratio == pytest.approx(1 / 7)
    assert m.adverb_ratio == pytest.approx(1 / 27)
    assert m.similes_per_200w == pytest.approx(200 / 27)
    assert m.abstract_ratio == pytest.approx(1 / 27)
    assert (m.vague_timers, m.banned_phrases, m.leak_phrases) == (1, 1, 0)
    assert (m.max_same_opener_bigram, m.max_consecutive_same_first_word) == (1, 3)


def test_quoted_speech_is_never_measured(style):
    """STYLE-01: the speaker's words are theirs — adverbs, similes and banned phrases inside quotes count for nothing."""
    m = lint.prose_metrics('Mara says, "Honestly, really, like a knife, a testament to it." Owen waits.', style)
    assert (m.words, m.sentences, m.adverb_ratio, m.similes_per_200w, m.banned_phrases) == (4, 2, 0.0, 0.0, 0)


def test_lint_findings(style):
    """STYLE-01..06: the failing metrics become error findings; short prose is only a warning."""
    rep = lint.lint_prose(SAMPLE, packet(), style, NUM, set())
    rules = [f.rule for f in rep.findings if f.severity == "error"]
    assert sorted(set(rules)) == ["STYLE-ABSTRACT", "STYLE-BANNED", "STYLE-REPEAT-START", "STYLE-SIMILE", "STYLE-VAGUE-TIME"]
    assert [f.rule for f in rep.findings if f.severity == "warning"] == ["STYLE-LENGTH"]
    assert rep.passed is False
    ok = lint.lint_prose("Owen waits at the counter. Glass rattles in the frame.", packet(), style, NUM, set())
    assert ok.passed is True and [f.rule for f in ok.findings] == ["STYLE-LENGTH"]


def test_leaks_are_disclosure_errors(style):
    """DISC-01: phrases that claim knowledge the viewpoint cannot have."""
    rep = lint.lint_prose("Meanwhile a man waits behind the fence.", packet(), style, NUM, set())
    assert [f.rule for f in rep.findings if f.severity == "error"] == ["DISC-LEAK"]


def test_invented_dialogue_rejected(style):
    """NARR-06 / DISC-SPEECH (pivot): a quote must match words the PC heard (gaps and punctuation
    aside); anything else is invented dialogue."""
    k = packet(lines=[NarratorLine(seconds=0.4, kind="speech", text='June calls out, not all of it clear: "What … that?"',
                                   speaker="June", words="What … that?")])
    heard = lint.lint_prose('June calls out, "What... that?"', k, style, NUM, set())
    assert heard.passed
    invented = lint.lint_prose('June calls out, "What... that?" Mara says, "Get down, all of you."', k, style, NUM, set())
    assert [(f.rule, f.detail) for f in invented.findings if f.severity == "error"] == [("DISC-SPEECH", "Get down, all of you.")]


def test_names_the_pc_does_not_know(style):
    """DISC-NAME: a name known somewhere in the run but not allowed for this PC, this turn."""
    rep = lint.lint_prose("Mara looks toward Dale.", packet(), style, NUM, {"Dale", "Dale Pruitt", "Mara", "Nita"})
    assert [(f.rule, f.detail) for f in rep.findings if f.severity == "error"] == [("DISC-NAME", "Dale")]


def test_the_players_words_are_not_parroted(style):
    """ECHO-01: a 4-word run (two content words or more) of the player's input, outside quotes."""
    block = sorted(lint.content_ngrams("I watch the front window and keep quiet.", NUM.echo_n, NUM.echo_min_content_tokens))
    assert block == ["front window and keep", "i watch the front", "the front window and", "watch the front window",
                     "window and keep quiet"]
    k = packet(player_input_echo_block=block)
    rep = lint.lint_prose("Owen keeps his eyes on the front window and keeps quiet.", k, style, NUM, set())
    assert [(f.rule, f.detail) for f in rep.findings if f.severity == "error"] == [("ECHO-01", "the front window and")]
    k2 = packet(player_input_echo_block=block, lines=[NarratorLine(seconds=0, kind="speech", text='Owen says, "I watch the front window."',
                                                                    speaker="Owen", words="I watch the front window.")])
    assert lint.lint_prose('Owen says, "I watch the front window."', k2, style, NUM, set()).passed, "quoted: his words, licensed"


def test_normalise_tokens():
    assert lint.normalise_tokens("Don't MOVE, Mara's gun!") == ["dont", "move", "maras", "gun"]


def test_echo_ledger_records_checks_and_expires(store):
    """ECHO-02/03: the player's 4-grams are kept for echo_window_turns turns; any generated line is checked against them."""
    with store.transaction() as tx:
        lint.record_pc_input(tx, 1, "I watch the front window and keep quiet.", NUM)
    rows = [tuple(r) for r in store.query("SELECT turn_index, ngram, source, licensed_uses FROM echo_ledger ORDER BY ngram")]
    assert len(rows) == 5 and all(r[0] == 1 and r[2] == "pc_input" and r[3] == 0 for r in rows)
    ev = dict(store.query_one("SELECT * FROM events WHERE type = 'ECHO_RECORD'"))
    assert ev["writer"] == "narration.lint"
    with store.transaction() as tx:
        assert lint.check_line(tx, "Keep your eyes on the front window and keep quiet", NUM) == [
            "front window and keep", "the front window and", "window and keep quiet"]
        assert lint.check_line(tx, "Quiet.", NUM) == []
    with store.transaction() as tx:
        lint.record_pc_input(tx, 1 + NUM.echo_window_turns, "Nothing to see here.", NUM)
    assert not store.query_one("SELECT 1 FROM echo_ledger WHERE turn_index = 1"), "older than the window: expired"


# --------------------------------------------------------------------------- narrate (NARR-07)
def _narrate(fake, k, style, names=frozenset()):
    cfg = EngineConfig()
    return asyncio.run(narrator.narrate(LaneClient(cfg, fake), k, style, NUM, config=cfg, all_known_names=set(names),
                                        turn_index=1))


def test_a_failed_draft_is_regenerated_with_its_faults(fake, style):
    """NARR-07: lint failure -> the next attempt is asked to fix the listed faults."""
    fake.script(CallClass.NARRATION, "Meanwhile Owen waits.")
    fake.script(CallClass.NARRATION, "Owen waits at the counter.")
    prose, findings, attempts, passed = _narrate(fake, packet(), style)
    assert (prose, attempts, passed) == ("Owen waits at the counter.", 2, True)
    second = fake.calls(CallClass.NARRATION)[1]
    assert "DISC-LEAK: meanwhile" in second.messages[-1].content


def test_the_judge_only_adds_findings(fake, style):
    """RENDER_LINT (lane B) flags a sentence the packet does not support: that draft fails too."""
    fake.script(CallClass.NARRATION, "Owen hears a shot.")
    fake.script(CallClass.RENDER_LINT, {"unsupported": [{"sentence_index": 0, "reason": "not_in_packet"}]})
    fake.script(CallClass.NARRATION, "Owen waits at the counter.")
    prose, findings, attempts, passed = _narrate(fake, packet(), style)
    assert (prose, attempts, passed) == ("Owen waits at the counter.", 2, True)
    assert len(fake.calls(CallClass.RENDER_LINT)) == 2


def test_three_failures_keep_the_least_bad_draft(fake, style):
    """NARR-07: never roll back the world for prose; keep the draft with the fewest errors."""
    fake.script(CallClass.NARRATION, "Meanwhile, unbeknownst to Owen, it is a testament to fate.")
    fake.script(CallClass.NARRATION, "Meanwhile Owen waits.")
    fake.script(CallClass.NARRATION, "Soon, meanwhile, later, Owen waits.")
    prose, findings, attempts, passed = _narrate(fake, packet(), style)
    assert (prose, attempts, passed) == ("Meanwhile Owen waits.", 3, False)
    assert [f.rule for f in findings if f.severity == "error"] == ["DISC-LEAK"]


def test_no_draft_at_all_is_told_plainly(fake, style):
    """G17: when no attempt returns text the code tells the moment plainly from the packet lines."""
    fake.fail(CallClass.NARRATION, "empty", times=3)
    k = packet(lines=[NarratorLine(seconds=0, kind="sound", text="A loud metal crash came from the rear alley."),
                      NarratorLine(seconds=0.1, kind="speech", text='Mara says, "Quiet."', speaker="Mara", words="Quiet.")])
    prose, findings, attempts, passed = _narrate(fake, k, style)
    assert prose == 'A loud metal crash came from the rear alley. Mara: "Quiet."'
    assert (attempts, passed, [f.rule for f in findings]) == (3, False, ["NARR-FALLBACK"])


# --------------------------------------------------------------------------- NARR-00
NARRATION_DIR = Path(narrator.__file__).parent
OWN_WRITERS = {"narration.narrator", "narration.lint"}
OWN_TABLES = {"narration", "narrator_state", "echo_ledger"}


def test_narrator_has_no_write_handle(metal_turn):
    """NARR-00 (pivot): the narration band writes only its own three tables, and building what the
    narrator reads changes nothing."""
    for path in sorted(NARRATION_DIR.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.keyword) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                if node.arg == "writer":
                    assert node.value.value in OWN_WRITERS, f"{path.name}: writer {node.value.value}"
                if node.arg == "table":
                    assert node.value.value in OWN_TABLES, f"{path.name}: table {node.value.value}"
            if isinstance(node, ast.Attribute) and node.attr == "bookkeep":
                raise AssertionError(f"{path.name}: the narrator keeps no books")
    w = metal_turn.w
    for r in w.store.query("SELECT type, state_delta FROM events WHERE writer LIKE 'narration.%'"):
        assert {d["table"] for d in json.loads(r["state_delta"])} <= OWN_TABLES
    n = w.store.query_one("SELECT COUNT(*) FROM events")[0]
    from as_engine.narration.location import describe
    with w.store.transaction() as tx:
        narrator.build_narrator_packet(tx, w.id("pc"), 1, metal_turn.t0, metal_turn.s.settings)
        describe(tx, w.id("pc"), metal_turn.t0 + 3000)
    assert w.store.query_one("SELECT COUNT(*) FROM events")[0] == n
