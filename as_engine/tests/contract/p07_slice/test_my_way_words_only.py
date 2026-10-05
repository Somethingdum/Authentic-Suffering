"""My way, words only (D-164). turn/intake.py INTAKE-04; action/intent.py said_aloud (INTENT-10).

With the player's opt-in "say it my way" on, the model rewrites what the player's character says — and a model's
line can carry stage directions ("*shrugs* Fine."), which were then spoken aloud as words, because only the room's
lines were cleaned. Now the rewritten line keeps its words only; a line that was only a direction is what the
player typed, unless the character kept it to themselves.
"""

from __future__ import annotations

import pytest
from slice_kit import play

from as_engine.contracts.common import CallClass
from as_engine.turn.intake import NONE_MESSAGES

pytestmark = pytest.mark.phase(7)


def my_way(w):
    s = w.session()
    s.settings = s.settings.model_copy(update={"pc_voice": "my_way"})
    return s


def said(w, s):
    import json
    r = w.store.query("SELECT payload FROM events WHERE type = 'SPEECH' AND actor_id = ? ORDER BY seq", (s.pc_id,))
    return [json.loads(x[0])["words"] for x in r]


def test_the_words_alone(scenario, fake):
    w = scenario("metal_fence")
    s = my_way(w)
    fake.script(CallClass.SAY_MY_WAY, lambda r: {"line": "*shrugs* Fine. (looks away) Whatever.", "survived": "softened"})
    assert play(s, "say", "I don't care what you do.").ok
    assert said(w, s) == ["Fine. Whatever."]


def test_only_a_direction(scenario, fake):
    w = scenario("metal_fence")
    s = my_way(w)
    fake.script(CallClass.SAY_MY_WAY, lambda r: {"line": "(quietly)", "survived": "softened"})
    assert play(s, "say", "Keep it down.").ok
    assert said(w, s) == ["Keep it down."]


def test_kept_to_himself(scenario, fake):
    w = scenario("metal_fence")
    s = my_way(w)
    fake.script(CallClass.SAY_MY_WAY, lambda r: {"line": "*says nothing*", "survived": "withheld"})
    out = play(s, "say", "I loved her, you know.")
    assert not out.ok and (out.rejected_code, out.rejected_message) == ("wont", NONE_MESSAGES["wont"])
    assert said(w, s) == []
