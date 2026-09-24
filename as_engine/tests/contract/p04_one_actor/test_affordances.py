"""Affordance enumeration (P4). Rules AFF-01..10, WILL-03 (mind/affordance.py).

Code decides what a body could attempt; a mind only chooses among those options. Numbers here are
hand-checked from the fixtures (anchor coordinates in tests/fixtures/scenarios/*.yaml).
"""

from __future__ import annotations

import math
import re

import pytest

from as_engine.contracts.events import Event, EventType
from as_engine.contracts.settings import PacketRules, RulesConfig
from as_engine.mind import perception
from as_engine.mind.affordance import AffordanceSet, duration_words, enumerate_affordances, jaccard

pytestmark = pytest.mark.phase(4)

ID_RE = re.compile(r"\b(evt|act|plc|anc|prt|itm|pct|prp|clm|wnd|tsk)_\d{6}\b")
GATES = {"physical", "skill", "belief", "resolve", "resource", "duty", "moral"}
POST = "It means leaving your post at the front window."


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def commit(w, **ev):
    with w.store.transaction() as tx:
        return tx.commit_event(Event(turn_index=0, **ev))


def gust(w):
    """The metal_fence crash, early: 98 dB at the fence sheet in the alley."""
    return commit(w, type=EventType.NOISE, writer="action.propagate", at=now(w),
                  payload={"source_db": 98, "kind": "metal_crash", "text": "a loud metal crash",
                           "place_id": w.id("alley"), "anchor_id": w.id("fence_sheet")})


def options_for(w, local, at=None) -> AffordanceSet:
    t = now(w) if at is None else at
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id(local), t, 0)
        return enumerate_affordances(tx, w.id(local), w.canon.all("affordance"), t, 0)


def defs(aset):
    return [o.def_id for o in aset.options]


def by_def(aset, def_id):
    return [o for o in aset.options if o.def_id == def_id]


# --------------------------------------------------------------------------- June hears the crash
def test_june_is_offered_her_task_first_and_a_look(scenario):
    w = scenario("metal_fence")
    gust(w)
    a = options_for(w, "june")
    assert a.options[0].def_id == "keep_working"
    assert a.options[0].label == "Keep doing what you were doing (counting cans)"
    (look,) = by_def(a, "go_look")
    # shelves (2, 2) -> back door (4, 4.5): 3.20 m; go_look 1 s + 1.0 s/m -> 4.2 s
    assert look.destination_id == w.id("back_door_in")
    assert look.label == "Go and look toward the back door (3 m, about 4 seconds)"
    assert look.est_duration_s == pytest.approx(1 + math.hypot(2, 2.5))
    for d in ("speak", "wait_here", "observe_area", "watch_portal"):
        assert d in defs(a), d
    assert not any(d.startswith(("shoot_", "strike_")) for d in defs(a)), "she holds no weapon"


def test_anchors_toward_the_sound_come_first(scenario):
    """The attention point after the crash is the back door (the sound came through it), so the
    move options go there, not to the nearest shelf."""
    w = scenario("metal_fence")
    gust(w)
    a = options_for(w, "june")
    walks = by_def(a, "move_to_anchor")
    assert walks and walks[0].destination_id == w.id("back_door_in")
    m = options_for(w, "mara")
    (look,) = by_def(m, "go_look")
    assert look.destination_id == w.id("storeroom_door_front"), "the crash reached Mara through the storeroom door"


def test_leaving_a_post_costs_something(scenario):
    w = scenario("metal_fence")
    gust(w)
    m = options_for(w, "mara")
    moves = [o for o in m.options if o.def_id in ("go_look", "move_to_anchor", "run_to_anchor", "move_through_portal", "leave_place")]
    assert moves
    for o in moves:
        assert o.cost_note == POST and "abandon_post" in o.tags, o.def_id
    for o in m.options:
        if o.def_id in ("wait_here", "observe_area", "close_portal", "speak"):
            assert o.cost_note is None, o.def_id
    # (13.5, 8.5) is 13.2 m from the front window (3, 0.5)
    (look,) = by_def(m, "go_look")
    assert look.label == "Go and look toward the storeroom doorway (13 m, about 14 seconds)"


def test_every_option_reads_as_plain_english(scenario):
    """Placeholders are filled, no internal id leaks, the ui label is filled too (SKULL-06)."""
    for name, who in (("metal_fence", ("june", "mara", "pc", "nita")), ("two_skills", ("twin_a", "twin_b")),
                      ("request_firewall", ("mara", "ray")), ("empty_gun", ("reggie",))):
        w = scenario(name)
        for local in who:
            a = options_for(w, local)
            assert a.options, (name, local)
            for o in a.options:
                for text in (o.label, o.ui_label, o.cost_note or ""):
                    assert "{" not in text and "}" not in text, (name, local, text)
                    assert not ID_RE.search(text), (name, local, text)
                assert o.label and o.label[0].isupper(), o.label
                assert "  " not in o.label and "the the" not in o.label.lower(), o.label


def test_selection_caps_and_order(scenario):
    w = scenario("metal_fence")
    gust(w)
    for local in ("june", "mara", "pc"):
        a = options_for(w, local)
        assert 3 <= len(a.options) <= 18
        counts = {}
        for o in a.options:
            counts[o.def_id] = counts.get(o.def_id, 0) + 1
        assert max(counts.values()) <= 3, counts
        assert len({o.signature for o in a.options}) == len(a.options), "no duplicate options"


def test_a_small_menu_still_has_one_of_each_kind(scenario):
    """Round-robin: with room for 5, June still gets her task, speech, a move, an action and a hold."""
    w = scenario("metal_fence", rules=RulesConfig(packet=PacketRules(max_affordances=5)))
    gust(w)
    a = options_for(w, "june")
    assert len(a.options) == 5
    d = defs(a)
    assert d[0] == "keep_working" and "speak" in d and "wait_here" in d, d
    assert d[-1] == "wait_here", "'freeze' leads the hold group"


def test_rejections_are_audited(scenario):
    w = scenario("metal_fence")
    gust(w)
    a = options_for(w, "pc")
    assert a.rejected, "the PC has a gun and an axe: something is out of range or out of reach"
    for r in a.rejected:
        assert r.gate in GATES and r.detail, r
    assert any(r.def_id == "punch" and r.target_id == w.id("mara") and r.gate == "physical" for r in a.rejected), \
        "Mara is 5 m away: out of reach for a punch"
    assert not any(o.def_id == "punch" and o.target_id == w.id("mara") for o in a.options)


# --------------------------------------------------------------------------- WILL-03 two_skills
def test_same_body_different_training_different_options(scenario):
    """WILL-03: the menus differ, and they differ because of skill and nerve."""
    w = scenario("two_skills")
    a = options_for(w, "twin_a")   # firearms 3, knows the head-shot rule, Resolve 6
    b = options_for(w, "twin_b")   # untrained, Resolve 1
    da, db = set(defs(a)), set(defs(b))
    assert len(da ^ db) >= 3, (sorted(da - db), sorted(db - da))
    for d in da - db:
        assert any(r.def_id == d and r.gate in ("skill", "belief", "resolve") for r in b.rejected), \
            f"{d} is missing for twin_b without a capability reason"
    sh = w.id("shambler")
    # the armed, trained twin facing an infected: the shots lead the menu (threat group, attack first)
    assert [(o.def_id, o.target_id) for o in a.options[:2]] == [("shoot_center_mass", sh), ("shoot_head", sh)]
    assert not any(o.def_id.startswith("shoot_") for o in b.options), "Resolve 1: no fear-exposed options"
    assert "go_look" not in db and "flee_threat" in db


def test_gates_run_in_order(scenario):
    """The FIRST failing gate is recorded: untrained twin_b fails shoot_head at 'skill' before its
    Resolve is even looked at; shoot_center_mass needs no skill, so it fails at 'resolve'."""
    w = scenario("two_skills")
    b = options_for(w, "twin_b")
    sh = w.id("shambler")
    gate = {(r.def_id, r.target_id): r.gate for r in b.rejected}
    assert gate[("shoot_head", sh)] == "skill"
    assert gate[("shoot_center_mass", sh)] == "resolve"


# --------------------------------------------------------------------------- moral and duty gates
def _armed_threat(w):
    """The PC tells Mara to put the hammer down, weapon in hand (payload.armed)."""
    return commit(w, type=EventType.SPEECH, writer="action.propagate", actor_id=w.id("pc"), at=now(w),
                  payload={"words": "Put the hammer down or I'll shoot.", "volume": "raised",
                           "to": [w.id("mara")], "source_db": 70, "armed": True})


def test_a_mother_is_never_offered_leaving_her_son(scenario):
    """Eli sleeps in the room and Mara has seen him; once a threat is perceived, every way out of the
    room carries abandon_dependent, which is on her wont list — she never even sees those options."""
    w = scenario("request_firewall")
    _armed_threat(w)
    a = options_for(w, "mara", at=now(w) + 500)
    for d in ("leave_place", "move_through_portal", "flee_threat"):
        assert d not in defs(a), d
        assert any(r.def_id == d and r.gate == "moral" and "abandon_dependent" in r.detail for r in a.rejected), d
    assert any(o.def_id == "shield_dependent" and o.target_id == w.id("eli") for o in a.options)
    assert any(r.def_id == "strike_melee" and r.target_id == w.id("eli") and r.gate == "moral"
               and "kill_child" in r.detail for r in a.rejected)


def test_without_a_threat_she_may_leave(scenario):
    w = scenario("request_firewall")
    a = options_for(w, "mara")
    assert "surrender" not in defs(a) and "shield_dependent" not in defs(a), "nothing to give up to"
    assert not any(r.gate == "moral" and "abandon_dependent" in r.detail for r in a.rejected)


def test_the_pc_is_gated_by_its_own_dossier_only(scenario):
    """L12: Owen's wont list has no kill_human, so he is offered shooting Mara; nothing is special
    about being the PC."""
    w = scenario("metal_fence")
    a = options_for(w, "pc")
    assert any(o.def_id == "shoot_center_mass" and o.target_id == w.id("mara") for o in a.options)
    assert all("kill_human" in o.tags for o in a.options if o.def_id.startswith("shoot_"))


def test_attacking_the_unarmed_is_a_line_for_reggie(scenario):
    w = scenario("empty_gun")
    a = options_for(w, "reggie")
    carl, pc = w.id("carl"), w.id("pc")
    assert any(o.def_id == "shoot_center_mass" and o.target_id == carl for o in a.options), "Carl holds a pipe"
    assert any(r.def_id == "shoot_center_mass" and r.target_id == pc and r.gate == "moral"
               and "attack_unarmed" in r.detail for r in a.rejected), "Owen's hands are empty"


# --------------------------------------------------------------------------- knowledge, not truth
def test_the_gun_is_offered_because_he_believes_it_is_loaded(scenario):
    """Resource gate reads belief: the pistol is empty, Reggie believes it is loaded (INTENT-03)."""
    w = scenario("empty_gun")
    a = options_for(w, "reggie")
    shots = [o for o in a.options if o.def_id.startswith("shoot_")]
    assert shots and all(o.item_id == w.id("pistol") for o in shots)


def test_a_believed_item_is_offered_where_it_is_believed_to_be(scenario):
    """AFF-01: the crowbar is really in the tool room; Reggie believes it is on the workbench, so
    he is offered it there (the barrier will find it missing, HALLUC-01, P5)."""
    w = scenario("empty_gun")
    a = options_for(w, "reggie")
    (pick,) = [o for o in a.options if o.def_id == "pick_up_item"]
    assert (pick.target_id, pick.destination_id) == (w.id("crowbar"), w.id("workbench"))
    assert pick.label == "Pick up the crowbar"


def test_enumeration_writes_nothing(scenario):
    w = scenario("metal_fence")
    gust(w)
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id("june"), now(w), 0)
    n = w.store.query_one("SELECT COUNT(*) FROM events")[0]
    with w.store.transaction() as tx:
        enumerate_affordances(tx, w.id("june"), w.canon.all("affordance"), now(w), 0)
    assert w.store.query_one("SELECT COUNT(*) FROM events")[0] == n


# --------------------------------------------------------------------------- helpers
@pytest.mark.parametrize("s,words", [
    (0.4, "a second"), (1.49, "a second"), (1.5, "2 seconds"), (4.2, "4 seconds"), (59, "59 seconds"),
    (60, "a minute"), (89, "a minute"), (90, "2 minutes"), (125, "2 minutes"), (3599, "60 minutes"),
    (3600, "an hour"), (5400, "2 hours"),
])
def test_duration_words(s, words):
    assert duration_words(s) == words


def test_jaccard_is_over_signatures():
    from as_engine.contracts.common import Verb
    from as_engine.mind.affordance import BoundAffordance

    def s(*sigs):
        return AffordanceSet(actor_id="x", options=[BoundAffordance(def_id=d, verb=Verb.WAIT, label=d, ui_label=d, target_id=t)
                                                    for d, t in sigs])
    assert jaccard(s(("a", None), ("b", "t1")), s(("a", None), ("b", "t2"))) == pytest.approx(1 / 3)
    assert jaccard(s(), s()) == 1.0
