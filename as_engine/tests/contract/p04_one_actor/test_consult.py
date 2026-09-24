"""Bounded consultation: what a packet offers and what a lookup brings back (P4, Actor v2 — Actor
Spec §7, §8). Rules CONSULT-01..04 and CONSULT-06's menu part (mind/consult.py, mind/packet.py).

A person deciding may look up ONE thing in their own head before they choose: something they
remember (recall, P6) or more attempts of one kind their short menu did not show (more_actions).
Nothing physical happens and nothing outside the person is read. A reaction offers nothing, and a
packet rebuilt with a lookup's answer offers nothing more.

Mara on the metal-fence sales floor, with the first menu cut to four options so that most of what
she could try is behind "more of that kind".
"""

from __future__ import annotations

import dataclasses

import pytest

from as_engine.contracts.common import LOD, CallClass
from as_engine.contracts.content import AFFORDANCE_FAMILIES
from as_engine.contracts.mind import Consultation
from as_engine.contracts.settings import PacketRules, RulesConfig
from as_engine.mind import consult, perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.mind.consult import Consulted, family_of
from as_engine.mind.packet import build_packet
from as_engine.prompts.render import render

pytestmark = pytest.mark.phase(4)


@pytest.fixture
def short(scenario):
    """metal_fence with a four-option first menu."""
    return scenario("metal_fence", rules=RulesConfig(packet=PacketRules(max_affordances=4)))


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def moment(w, local="mara", **kw):
    """(AffordanceSet, packet, defs by id) for ``local`` at the world's now."""
    t = now(w)
    defs = {d.id: d for d in w.canon.all("affordance")}
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id(local), t, 0)
        aff = enumerate_affordances(tx, w.id(local), w.canon.all("affordance"), t, 0)
        p = build_packet(tx, w.id(local), LOD.HOT, aff, 0, t, **kw)
    return aff, p, defs


def hidden(aff):
    shown = {o.signature for o in aff.options}
    return [o for o in aff.pool if o.signature not in shown]


# --------------------------------------------------------------------------- CONSULT-01 / -03
def test_a_deliberation_offers_recall_and_the_kinds_the_menu_hides(short):
    aff, p, defs = moment(short)
    assert len(aff.options) == 4 and hidden(aff), "the cut menu hides most of what she could try"
    want = [f for f in AFFORDANCE_FAMILIES if any(family_of(defs[o.def_id]) == f for o in hidden(aff))]
    assert consult.families(aff, defs) == want, "CONSULT-03: the families with a hidden option, in table order"
    assert p.families == want and p.consult_kinds == ["recall", "more_actions"], "CONSULT-01"
    assert "compose" not in p.consult_kinds, "compose waits for typed plans"


def test_a_menu_that_shows_everything_offers_recall_only(short):
    aff, _p, defs = moment(short)
    everything = dataclasses.replace(aff, pool=list(aff.options))      # nothing behind the menu
    assert consult.families(everything, defs) == []
    t = now(short)
    with short.store.transaction() as tx:
        p = build_packet(tx, short.id("mara"), LOD.HOT, everything, 0, t)
    assert p.families == [] and p.consult_kinds == ["recall"]


def test_a_reaction_offers_no_consultation(short):
    _aff, p, _defs = moment(short, reaction=True)
    assert p.consult_kinds == [] and p.families == [], "CONSULT-01: a reaction offers nothing"


def test_the_prompt_offers_exactly_what_the_packet_offers(short):
    _aff, p, _defs = moment(short)
    user = render(CallClass.ACTOR_COGNITION, p=p)[1].content
    assert "Before you decide you may look up one thing" in user
    for fam in p.families:
        assert AFFORDANCE_FAMILIES[fam] in user, f"the family {fam} is offered in words"
    _aff, r, _defs = moment(short, reaction=True)
    assert "Before you decide you may look up one thing" not in render(CallClass.ACTOR_REACTION, p=r)[1].content


# --------------------------------------------------------------------------- CONSULT-02
def _person(p):
    return next(h for h in p.handles if h.startswith("P"))


@pytest.mark.parametrize("case, why", [
    ("compose", "not_offered"),
    ("subject_is_an_option", "hallucinated_ref"),
    ("subject_nobody", "hallucinated_ref"),
    ("blank_recall", "empty"),
    ("family_not_listed", "not_offered"),
    ("recall_by_query", None),
    ("recall_by_subject", None),
    ("more_of_a_listed_family", None),
])
def test_check_says_why_a_consultation_cannot_be_answered(short, case, why):
    _aff, p, _defs = moment(short)
    listed = p.families[0]
    unlisted = next(f for f in AFFORDANCE_FAMILIES if f not in p.families)
    c = {
        "compose": Consultation(kind="compose", template="t"),
        "subject_is_an_option": Consultation(kind="recall", query="the revolver", subjects=["A1"]),
        "subject_nobody": Consultation(kind="recall", query="the revolver", subjects=["P99"]),
        "blank_recall": Consultation(kind="recall", query="   "),
        "family_not_listed": Consultation(kind="more_actions", family=unlisted),
        "recall_by_query": Consultation(kind="recall", query="Who has the keys to the back door?"),
        "recall_by_subject": Consultation(kind="recall", subjects=[_person(p)]),
        "more_of_a_listed_family": Consultation(kind="more_actions", family=listed),
    }[case]
    assert consult.check(p, c) == why


def test_a_reaction_packet_answers_no_consultation_at_all(short):
    _aff, p, _defs = moment(short, reaction=True)
    assert consult.check(p, Consultation(kind="recall", query="the keys")) == "not_offered"


# --------------------------------------------------------------------------- CONSULT-04
def test_more_actions_brings_the_hidden_options_of_that_kind_in_pool_order(short):
    aff, p, defs = moment(short)
    for fam in p.families:
        got = consult.more_actions(aff, fam, [], defs)
        want = [o for o in hidden(aff) if family_of(defs[o.def_id]) == fam][:consult.MAX_MORE]
        assert got == want and got, fam
        assert not ({o.signature for o in got} & {o.signature for o in aff.options}), "never what the menu shows"


def test_more_actions_about_something_keeps_the_options_about_it(short):
    aff, _p, defs = moment(short)
    doors = sorted({o.target_id for o in hidden(aff) if o.target_id and o.target_id.startswith("prt_")})
    assert doors, "the hidden options name a way through"
    door = doors[0]
    got = {fam: consult.more_actions(aff, fam, [door], defs) for fam in AFFORDANCE_FAMILIES}
    assert any(got.values())
    for fam, opts in got.items():
        assert all(door in (o.target_id, o.destination_id, o.item_id) for o in opts), fam
        assert opts == [o for o in hidden(aff) if family_of(defs[o.def_id]) == fam
                        and door in (o.target_id, o.destination_id, o.item_id)][:consult.MAX_MORE], fam
    assert all(consult.more_actions(aff, fam, ["prt_999999"], defs) == [] for fam in AFFORDANCE_FAMILIES)


# --------------------------------------------------------------------------- CONSULT-06 (the menu part)
def test_a_packet_with_a_lookups_answer_keeps_every_handle_and_adds_after_them(short):
    aff, p, defs = moment(short)
    fam = p.families[0]
    more = consult.more_actions(aff, fam, [], defs)
    n = len(aff.options)
    lines = [f"More ways of {AFFORDANCE_FAMILIES[fam]}: " + ", ".join(f"A{n + i}" for i in range(1, len(more) + 1)) + "."]
    _aff, p2, _defs = moment(short, consulted=Consulted("more_actions", lines=lines, options=more))
    for h, sig in p.handles.items():
        if h.startswith("A"):
            assert p2.handles[h] == sig, f"{h} keeps its meaning"
    assert [p2.handles[f"A{n + i}"] for i in range(1, len(more) + 1)] == [o.signature for o in more]
    assert [a.handle for a in p2.affordances][-len(more):] == [f"A{n + i}" for i in range(1, len(more) + 1)]
    assert p2.looked_up == lines and p2.consult_kinds == [] and p2.families == [], "one consultation per decision"
    user = render(CallClass.ACTOR_COGNITION, p=p2)[1].content
    assert lines[0] in user and "Before you decide you may look up one thing" not in user
