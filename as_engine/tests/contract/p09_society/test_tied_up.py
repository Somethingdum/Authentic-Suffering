"""Tied up (D-208). physical.bodies tied / tie_event / untie_event (capacity: tied hands are not free), action.effects
tie_up / untie / work_free, mind.affordance (who can be tied, untied, or work free), mind.packet body_lines (what has
hold of you; tied), mind.perception LOOK-03 (seen tied), action.cascade tied_up_by / saw_them_tied and the untie as a
rescue; core CAS-083..085.

There was a length of rope in the game and no way to tie anyone with it: a captive was someone you held with both
hands, for as long as you stood there. And a person in the dead's grip was told so only the moment it grabbed them —
the next turn their own prompt said nothing about it. Now someone who cannot fight it — held, out cold, asleep, or
seen giving up — can be tied hand and foot with a rope or tape; they know it, everyone who sees them sees it, they
can work at the knots, and whoever unties them (not the one who tied them) has their trust, and they owe them.
Being tied leaves fear and a grudge; those who love the one tied and saw it trust the one who did it less — unless
they knew the one tied was infected (tying up the bitten is quarantine, D-202).

A back room at noon (a dict scenario): Owen with a length of rope, Mara beside him, June — who loves Mara — and Dale.
"""

from __future__ import annotations

import copy
import re

import pytest

import helpers
from as_engine.action import cascade
from as_engine.action.resolve import resolve_wave
from as_engine.contracts.common import LOD
from as_engine.contracts.events import Event, EventType
from as_engine.mind import perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.mind.packet import build_packet
from as_engine.physical import bodies
from as_engine.testing.scenario import load_scenario

pytestmark = pytest.mark.phase(9)

MIN = 60_000

ROOM = {
    "schema": "as.scenario.v1", "name": "back_room", "seed": 3, "start": {"day": 400, "time": "12:00"},
    "places": [{"id": "room", "name": "Back room", "material": "brick", "light": 4, "width_m": 8, "depth_m": 6,
                "anchors": [{"id": "shelf", "name": "shelf", "x": 7, "y": 5}]}],
    "bodies": [
        {"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "room", "x": 2, "y": 2,
         "inventory": [{"item": "core:item/rope", "slot": "hand_r", "label": "rope"}]},
        {"id": "mara", "stub": {"name": "Mara Voss", "age": 38, "sex": "female"}, "place": "room", "x": 3, "y": 2},
        {"id": "june", "stub": {"name": "June Okafor", "age": 29, "sex": "female"}, "place": "room", "x": 3.8, "y": 2},
        {"id": "dale", "stub": {"name": "Dale Pruitt", "age": 52, "sex": "male"}, "place": "room", "x": 6, "y": 4},
    ],
    "relationships": [{"from": "june", "to": "mara", "kind": "friend", "trust": 2, "affection": 2}],
}


@pytest.fixture
def room(fixture_packs, core_pack_dir):
    worlds = []

    def _load():
        w = load_scenario(copy.deepcopy(ROOM), packs_root=fixture_packs, core_pack_dir=core_pack_dir)
        worlds.append(w)
        return w

    yield _load
    for w in worlds:
        w.store.close()


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def offered(w, who, defs):
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id(who), now(w), 0)
        aff = enumerate_affordances(tx, w.id(who), w.canon.all("affordance"), now(w), 0)
    return sorted((o.def_id, w.local(o.target_id) if o.target_id else None) for o in aff.pool if o.def_id in defs)


def grab(w, who, whom):
    with w.store.transaction() as tx:
        c = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=now(w), turn_index=0, payload={"what": "test"}))
        bodies.grip_event(tx, w.id(who), w.id(whom), now(w), c.event_id, 0)


def act(w, intent, *, seen=("mara", "june"), at=None):
    """Resolve one act, let those named take in what they saw, sweep the captivity rules."""
    at = at or now(w) + 1000
    with w.store.transaction() as tx:
        evs = resolve_wave(tx, w.rng, [intent], at, 1, horizon_ms=at + 10 * MIN)
        for x in seen:
            perception.compile_aftermath(tx, w.id(x), evs, at + 1000, 1)
        cascade.sweep(tx, evs, [r for r in w.canon.all("cascade") if r.id in ("CAS-082", "CAS-083", "CAS-084", "CAS-085")],
                      at + 1000, 1)
    return next(e for e in evs if e.type in (EventType.ACTION_COMPLETE, EventType.ACTION_BLOCKED)).payload.get("result"), evs


def tie(w, by="pc", whom="mara", item="rope"):
    return act(w, helpers.make_intent(w, by, "tie_up", whom, item=item))


def rel(w, a, b, axis):
    r = w.store.query_one(f"SELECT {axis} FROM relationships WHERE from_id = ? AND to_id = ?", (w.id(a), w.id(b)))
    return r[0] if r else 0


def loops(w, who, kind):
    return [tuple(r) for r in w.store.query("SELECT text, strength FROM open_loops WHERE holder_id = ? AND kind = ? AND "
                                            "status = 'open'", (w.id(who), kind))]


# --------------------------------------------------------------------------- who can be tied
def test_only_someone_who_cannot_fight_it(room):
    w = room()
    assert offered(w, "pc", {"tie_up"}) == [], "Mara is awake and free"
    assert tie(w)[0] == "resisted" and bodies.tied(w.store, w.id("mara")) is None
    grab(w, "pc", "mara")
    assert offered(w, "pc", {"tie_up"}) == [("tie_up", "mara")], "held"
    w2 = room()
    with w2.store.transaction() as tx:
        bodies.posture_event(tx, w2.id("mara"), "lying", now(w2), None, 0, awareness="asleep")
    assert offered(w2, "pc", {"tie_up"}) == [("tie_up", "mara")], "asleep"
    w3 = room()
    with w3.store.transaction() as tx:
        st = tx.commit_event(Event(type=EventType.GESTURE, writer="action.propagate", at=now(w3), turn_index=0, actor_id=w3.id("mara"),
                                   payload={"actor_id": w3.id("mara"), "gesture": "empty_hands", "target_id": None}))
        perception.compile_aftermath(tx, w3.id("pc"), [st], now(w3) + 500, 0)
    assert offered(w3, "pc", {"tie_up"}) == [("tie_up", "mara")], "she showed him empty hands"


# --------------------------------------------------------------------------- tied
def test_tied_hand_and_foot(room):
    w = room()
    grab(w, "pc", "mara")
    res, _ = tie(w)
    rope = w.id("rope")
    assert res == "tied" and bodies.tied(w.store, w.id("mara")) == rope
    assert bodies.grips_on(w.store, w.id("mara")) == [], "the hands that held her are free again"
    cap = bodies.capacity(w.store, w.id("mara"))
    assert (cap.hands_free, cap.mobile) == (0, False)
    assert w.store.query_one("SELECT restrained FROM bodies WHERE body_id = ?", (w.id("mara"),))[0] == 1
    with w.store.transaction() as tx:
        seen = perception.appearance_text(tx, w.id("june"), w.id("mara"), "clear", 1.0)
        far = perception.appearance_text(tx, w.id("dale"), w.id("mara"), "partial", 4.0)
    assert "hands and feet tied with a length of rope" in seen.lower() and "carrying" not in seen.lower()
    assert "tied up" in far.lower()


def test_she_knows_she_is_tied_and_can_work_at_it(room):
    w = room()
    grab(w, "pc", "mara")
    tie(w)
    t = now(w)
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id("mara"), t, 0)
        aff = enumerate_affordances(tx, w.id("mara"), w.canon.all("affordance"), t, 0)
        pkt = build_packet(tx, w.id("mara"), LOD.HOT, aff, 0, t)
    assert pkt.body_lines[0] == "Your hands and feet are tied."
    defs = {o.def_id for o in aff.pool}
    assert "work_free" in defs and not defs & {"move_to_anchor", "pick_up_item", "punch", "untie"}
    assert offered(w, "pc", {"untie", "tie_up"}) == [("untie", "mara")]


def test_held_after_the_moment_it_happened(room):
    """D-208: a hand on you is in your own lines every turn it stays there, not only the moment it grabbed you."""
    w = room()
    grab(w, "dale", "mara")
    t = now(w)
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id("mara"), t, 0)
        aff = enumerate_affordances(tx, w.id("mara"), w.canon.all("affordance"), t, 0)
        pkt = build_packet(tx, w.id("mara"), LOD.HOT, aff, 0, t)
    assert re.fullmatch(r"[A-Z].* has hold of you\.", pkt.body_lines[0]), pkt.body_lines


def test_untied(room):
    w = room()
    grab(w, "pc", "mara")
    tie(w)
    res, _ = act(w, helpers.make_intent(w, "june", "untie", "mara"), at=now(w) + MIN)
    assert res == "untied" and bodies.tied(w.store, w.id("mara")) is None
    assert tuple(w.store.query_one("SELECT holder_body, holder_slot, props FROM items WHERE item_id = ?", (w.id("rope"),))) == \
        (w.id("june"), "hand_r", "{}")
    assert bodies.capacity(w.store, w.id("mara")).mobile
    assert (rel(w, "mara", "june", "trust"), rel(w, "mara", "june", "affection")) == (2, 1)
    assert loops(w, "mara", "debt_owing") == [("A woman untied you. You owe them.", 3)], "she has never been told June's name"


def test_untying_your_own_captive_is_no_kindness(room):
    w = room()
    grab(w, "pc", "mara")
    tie(w)
    act(w, helpers.make_intent(w, "pc", "untie", "mara"), at=now(w) + MIN)
    assert bodies.tied(w.store, w.id("mara")) is None and loops(w, "mara", "debt_owing") == []


def test_working_free(room):
    """Knots tied tight are hard work (resistance 'binding'): in the room's seed six tries fail and the seventh gives;
    the rope drops at her feet."""
    w = room()
    grab(w, "pc", "mara")
    tie(w)
    results = []
    for k in range(1, 10):
        res, _ = act(w, helpers.make_intent(w, "mara", "work_free"), seen=(), at=now(w) + k * 10 * MIN)
        results.append(res)
        if res == "worked_free":
            break
    assert results == ["still_tied"] * 6 + ["worked_free"]
    assert bodies.tied(w.store, w.id("mara")) is None
    assert w.store.query_one("SELECT place_id FROM items WHERE item_id = ?", (w.id("rope"),))[0] == w.id("room")
    assert loops(w, "mara", "debt_owing") == [], "she owes nobody"


# --------------------------------------------------------------------------- reactions
def test_tied_up_and_seen(room):
    w = room()
    grab(w, "pc", "mara")
    trust = rel(w, "june", "pc", "trust")
    tie(w)
    assert (rel(w, "mara", "pc", "fear"), rel(w, "mara", "pc", "resentment")) == (1, 1)
    assert loops(w, "mara", "grudge") == [("A tall, heavyset man tied you up.", 2)]
    assert (rel(w, "june", "pc", "trust"), rel(w, "june", "pc", "resentment")) == (trust - 1, 1), "June saw her friend tied"


def test_she_rises_tied(room):
    """world.infected.rise (D-208): what got up out of Mara is still tied hand and foot — it strains where it lies."""
    from as_engine.turn import timers
    w = room()
    grab(w, "pc", "mara")
    tie(w)
    with w.store.transaction() as tx:
        bodies.die(tx, w.rng, w.id("mara"), now(w), None, 0)
    due = w.store.query_one("SELECT due_at FROM event_queue WHERE type = 'REANIMATION' AND subject_id = ? AND status = 'pending'",
                            (w.id("mara"),))[0]
    with w.store.transaction() as tx:
        timers.run_offscreen(tx, w.rng, due + 1000, 0)
    risen = w.store.query_one("SELECT body_id FROM infected_state WHERE risen_from = ?", (w.id("mara"),))[0]
    assert bodies.tied(w.store, risen) == w.id("rope")
    assert w.store.query_one("SELECT restrained FROM bodies WHERE body_id = ?", (risen,))[0] == 1


def test_the_story_knows_he_is_held_and_tied(room):
    """narration.narrator pc_state_lines (D-208): what has hold of Owen, and that he is tied, open his state."""
    from as_engine.narration.narrator import build_narrator_packet
    from as_engine.physical import objects
    w = room()
    grab(w, "mara", "pc")
    with w.store.transaction() as tx:
        pkt = build_narrator_packet(tx, w.id("pc"), 0, now(w), w.session().settings)
    assert re.fullmatch(r"[A-Z].* has hold of Owen\.", pkt.pc_state_lines[0]), pkt.pc_state_lines
    with w.store.transaction() as tx:
        objects.create(tx, "core:item/rope", 1, objects.Holder("body", w.id("mara"), "hand_r"), "scenario", {}, now(w), None, 0)
    rope = w.store.query_one("SELECT item_id FROM items WHERE holder_body = ? AND holder_slot = 'hand_r'", (w.id("mara"),))[0]
    act(w, helpers.make_intent(w, "mara", "tie_up", "pc", item=rope), seen=())
    with w.store.transaction() as tx:
        pkt = build_narrator_packet(tx, w.id("pc"), 1, now(w), w.session().settings)
    assert pkt.pc_state_lines[0] == "Owen's hands and feet are tied."
