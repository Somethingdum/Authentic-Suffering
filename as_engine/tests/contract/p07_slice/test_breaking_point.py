"""What a breaking point does (P7, the owner's H1). Rules TEMPER-06 (turn/cognition.py decide step
4), SEL-02 and SEL-03 grievance_near (turn/select.py), and the temper stage S3b of
turn/pipeline.py.

The owner: "If I were to disrespect the wrong person, too much, I expect to be decked in the jaw."
A snap is the body's, not a choice: it replaces what the person had decided, and it does not ask
their nerve (a man with none left can still swing). How a person breaks is theirs — a fist, a
screaming match, a cold walk out, tears.

A bar room (a dict scenario at day 3100): the player a step from Reggie Tate (fists), Irene
Kowalski (cold) and Tess Nakamura (words) at a table, a stranger by the far wall, a boy by the bar,
and the door to the street.
"""

from __future__ import annotations

import asyncio
import copy
import json

import pytest

from as_engine.contracts.common import LOD, CallClass, Lane
from as_engine.contracts.events import Event, EventType
from as_engine.lanes.scheduler import CognitionPlan
from as_engine.mind import perception, temper
from as_engine.mind.affordance import enumerate_affordances
from as_engine.testing.scenario import load_scenario
from as_engine.turn import select
from as_engine.turn.cognition import decide
from slice_kit import cognition, entity, pick, play

pytestmark = pytest.mark.phase(7)

BAR = {
    "schema": "as.scenario.v1", "name": "last_call", "seed": 71, "start": {"day": 3100, "time": "22:00"},
    "places": [
        {"id": "bar", "name": "Bar room", "material": "brick", "light": 3, "width_m": 14, "depth_m": 8,
         "anchors": [{"id": "door_side", "name": "door", "x": 1, "y": 1},
                     {"id": "back_booth", "name": "back booth", "x": 13, "y": 7}]},
        {"id": "street", "name": "Street", "kind": "street", "indoor": False, "material": "open_air", "light": 1,
         "width_m": 30, "depth_m": 10, "anchors": [{"id": "kerb", "name": "kerb", "x": 5, "y": 5}]},
    ],
    "portals": [{"id": "front_door", "a": "bar", "b": "street", "kind": "door", "name": "front door",
                 "anchor_a": "door_side", "anchor_b": "kerb", "open": True, "w": 90, "h": 200}],
    "bodies": [
        {"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "bar", "x": 2, "y": 4},
        {"id": "reggie", "dossier": "core:actor/reggie_tate", "place": "bar", "x": 3, "y": 4, "resolve": 0},
        {"id": "irene", "dossier": "core:actor/irene_kowalski", "place": "bar", "x": 6, "y": 4},
        {"id": "tess", "dossier": "core:actor/tess_nakamura", "place": "bar", "x": 7, "y": 4},
        {"id": "cal", "stub": {"name": "Cal Hobbs", "age": 30, "sex": "male"}, "place": "bar", "x": 12, "y": 2},
        {"id": "kid", "stub": {"name": "Danny Reyes", "age": 9, "sex": "male"}, "place": "bar", "x": 3.5, "y": 5},
    ],
}


@pytest.fixture
def bar(fixture_packs, core_pack_dir, fake):
    worlds = []

    def _load(change=None):
        spec = copy.deepcopy(BAR)
        if change is not None:
            change(spec)
        w = load_scenario(spec, packs_root=fixture_packs, core_pack_dir=core_pack_dir, transport=fake)
        worlds.append(w)
        return w

    yield _load
    for w in worlds:
        w.store.close()


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def snap(w, who, toward, outlet, at):
    """The snap as mind.temper.take_in commits it (TEMPER-05)."""
    with w.store.transaction() as tx:
        return tx.commit_event(Event(type=EventType.INVOLUNTARY, writer="mind.temper", actor_id=w.id(who), at=at,
                                     turn_index=0, payload={"actor_id": w.id(who), "kind": "outburst", "outlet": outlet,
                                                            "toward_id": w.id(toward)}))


def moment(w, actors, at):
    """One wave of decisions (decide) for ``actors`` at ``at``, turn 0, everyone thinking hot."""
    s = w.session()
    with s.store.transaction() as tx:
        affs = {}
        for a in actors:
            perception.compile_scene(tx, w.id(a), at, 0)
            affs[w.id(a)] = enumerate_affordances(tx, w.id(a), w.canon.all("affordance"), at, 0)
    plan = CognitionPlan(lod={w.id(a): LOD.HOT for a in actors}, lane={w.id(a): Lane.A for a in actors})

    async def go():
        with s.store.transaction() as tx:
            return await decide(tx, s, plan, affs, 0, at, reaction=False)
    return affs, asyncio.run(go())


def watch(w, def_id="observe_area"):
    return cognition(lambda r: pick(w, r, def_id), goal="stay put")


def saying(w, def_id, words, to, volume):
    return lambda r: {"choice": pick(w, r, def_id), "speech": {"text": words, "to": [entity(w, r, to)], "volume": volume},
                      "manner": "", "goal": "have it out", "private_reason": "Enough."}


# --------------------------------------------------------------------------- SEL-02 / SEL-03
def test_a_person_who_snaps_must_act(bar):
    w = bar()
    t = now(w)
    with w.store.transaction() as tx:
        assert not select.mandatory(tx, w.id("irene"), 0, t, t + 60_000, None)
    snap(w, "irene", "pc", "cold", t)
    with w.store.transaction() as tx:
        assert select.mandatory(tx, w.id("irene"), 0, t, t + 60_000, None)
        assert not select.mandatory(tx, w.id("irene"), 0, t + 1, t + 60_000, None), "a snap belongs to its moment"


def test_someone_you_can_hardly_stand_is_right_there(bar):
    """Irene's breaking point is 8: from heat 4 on, the stranger she is angry with standing in the
    room makes her more worth thinking for (SEL-03); a grudge does the same."""
    w = bar()
    t = now(w)
    cands = [w.id(x) for x in ("reggie", "irene", "tess", "cal")]

    def flags(who):
        with w.store.transaction() as tx:
            return select.salience_flags(tx, w.id(who), cands, w.id("pc"), 0, t)

    assert flags("irene")["grievance_near"] is False
    with w.store.transaction() as tx:
        temper.provoke(tx, w.id("irene"), w.id("cal"), "ordered_about", "test:1", t, 0)
    assert flags("irene")["grievance_near"] is False, "heat 1 of the 4 it takes"
    with w.store.transaction() as tx:
        temper.provoke(tx, w.id("irene"), w.id("cal"), "threatened", "test:2", t, 0)
    assert flags("irene")["grievance_near"] is True
    from as_engine.mind import mind as mindmod
    with w.store.transaction() as tx:
        mindmod.open_loop(tx, w.id("tess"), "grudge", "He shorted me on the salt.", [w.id("cal")], 1, "test:3", t, 0)
    assert flags("tess")["grievance_near"] is True
    with w.store.transaction() as tx:
        weights = tx.rules.scheduler.salience_weights
    assert weights["grievance_near"] > 0


# --------------------------------------------------------------------------- TEMPER-06 fists
def test_he_swings(bar, fake):
    """Reggie has no nerve left (resolve 0: no attack is on his menu), and snaps at the player a
    metre away: whatever he had decided, he throws a punch."""
    w = bar()
    t = now(w)
    snap(w, "reggie", "pc", "fists", t)
    fake.script(CallClass.ACTOR_COGNITION, actor_id=w.id("reggie"), response=watch(w, "wait_here"))
    affs, out = moment(w, ["reggie"], t)
    assert not any(o.def_id == "punch" for o in affs[w.id("reggie")].pool), "not something he would choose"
    it = out[w.id("reggie")]
    assert (it.bound.def_id, it.bound.target_id, it.source, it.speech) == ("punch", w.id("pc"), "reflex", None)
    assert it.bound.verb == "attack" and it.bound.est_duration_s == w.canon.find("affordance", "punch").duration.base_s


def test_too_far_to_hit_he_shouts(bar, fake):
    """The stranger is nine metres off: the fist becomes words — and words said raised stand."""
    w = bar()
    t = now(w)
    snap(w, "reggie", "cal", "fists", t)
    fake.script(CallClass.ACTOR_COGNITION, actor_id=w.id("reggie"),
                response=saying(w, "wait_here", "Say that again. Go on.", "cal", "shout"))
    _, out = moment(w, ["reggie"], t)
    it = out[w.id("reggie")]
    assert it.source == "model" and it.speech is not None and it.speech.to == (w.id("cal"),)
    assert not fake.calls(CallClass.INTENT_REPAIR)


def test_just_out_of_reach_is_out_of_reach(bar, fake):
    """The player two metres off (reach is 1.5 m): no punch; he has to say it."""
    w = bar(lambda s: s["bodies"][0].update(x=5, y=4))
    t = now(w)
    snap(w, "reggie", "pc", "fists", t)
    fake.script(CallClass.ACTOR_COGNITION, actor_id=w.id("reggie"),
                response=saying(w, "wait_here", "Come here and say that.", "pc", "shout"))
    _, out = moment(w, ["reggie"], t)
    it = out[w.id("reggie")]
    assert it.bound.def_id != "punch" and it.speech is not None and it.speech.to == (w.id("pc"),)


def test_never_a_child(bar, fake):
    w = bar()
    t = now(w)
    snap(w, "reggie", "kid", "fists", t)
    fake.script(CallClass.ACTOR_COGNITION, actor_id=w.id("reggie"), response=watch(w, "wait_here"))
    fake.script(CallClass.INTENT_REPAIR, actor_id=w.id("reggie"), response=watch(w, "wait_here"))
    _, out = moment(w, ["reggie"], t)
    assert out[w.id("reggie")].bound.def_id != "punch"


# --------------------------------------------------------------------------- words
def test_a_snap_in_words_is_said_out_loud(bar, fake):
    """Tess snaps at the player. Her first answer mutters; the one repair says what she must do;
    she mutters again — so she walks out."""
    w = bar()
    t = now(w)
    snap(w, "tess", "pc", "words", t)
    quiet = saying(w, "observe_area", "Unbelievable.", "pc", "low")
    fake.script(CallClass.ACTOR_COGNITION, actor_id=w.id("tess"), response=quiet)
    fake.script(CallClass.INTENT_REPAIR, actor_id=w.id("tess"), response=quiet)
    _, out = moment(w, ["tess"], t)
    (first,) = fake.calls(CallClass.ACTOR_COGNITION, actor_id=w.id("tess"))
    assert first.context.outburst is not None and first.context.outburst.startswith("You snap.")
    (rep,) = fake.calls(CallClass.INTENT_REPAIR, actor_id=w.id("tess"))
    pc = entity(w, first, "pc")
    assert f"You have snapped at {pc}: say what you say to them, raised or shouted." in json.dumps(
        [m.content for m in rep.messages], ensure_ascii=False)
    it = out[w.id("tess")]
    assert (it.bound.def_id, it.source) == ("leave_place", "reflex")


def test_the_repair_that_raises_its_voice_stands(bar, fake):
    w = bar()
    t = now(w)
    snap(w, "tess", "pc", "words", t)
    fake.script(CallClass.ACTOR_COGNITION, actor_id=w.id("tess"), response=watch(w))
    fake.script(CallClass.INTENT_REPAIR, actor_id=w.id("tess"),
                response=saying(w, "observe_area", "You think you can talk to me like that? In here?", "pc", "raised"))
    _, out = moment(w, ["tess"], t)
    it = out[w.id("tess")]
    assert it.speech is not None and it.speech.volume == "raised" and it.speech.to == (w.id("pc"),)


# --------------------------------------------------------------------------- cold, flight, tears
def test_she_goes_cold_and_walks_out(bar, fake):
    w = bar()
    t = now(w)
    snap(w, "irene", "pc", "cold", t)
    fake.script(CallClass.ACTOR_COGNITION, actor_id=w.id("irene"), response=watch(w))
    _, out = moment(w, ["irene"], t)
    it = out[w.id("irene")]
    assert (it.bound.def_id, it.bound.target_id, it.bound.destination_id, it.source) == ("leave_place", None, None, "reflex")


def test_with_the_door_shut_she_goes_to_the_far_end(bar, fake):
    w = bar(lambda s: s["portals"][0].update(open=False))
    t = now(w)
    snap(w, "irene", "pc", "cold", t)
    fake.script(CallClass.ACTOR_COGNITION, actor_id=w.id("irene"), response=watch(w))
    _, out = moment(w, ["irene"], t)
    it = out[w.id("irene")]
    assert (it.bound.def_id, it.bound.destination_id) == ("move_to_anchor", w.id("back_booth")), "as far from him as the room goes"
    d = w.canon.find("affordance", "move_to_anchor").duration
    assert it.bound.est_duration_s == pytest.approx(d.base_s + d.per_meter_s * ((13 - 6) ** 2 + (7 - 4) ** 2) ** 0.5)


def test_he_breaks_down(fixture_packs, core_pack_dir, fake):
    """Dale Pruitt, at the end of everything, breaks down in tears (a different day: his)."""
    w = load_scenario({
        "schema": "as.scenario.v1", "name": "culvert", "seed": 72, "start": {"day": 300, "time": "18:00"},
        "places": [{"id": "culvert", "name": "Storm culvert", "material": "concrete", "light": 2, "width_m": 4, "depth_m": 20}],
        "bodies": [
            {"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "culvert", "x": 2, "y": 5},
            {"id": "dale", "dossier": "core:actor/dale_pruitt", "place": "culvert", "x": 2, "y": 7},
        ],
    }, packs_root=fixture_packs, core_pack_dir=core_pack_dir, transport=fake)
    try:
        t = now(w)
        snap(w, "dale", "pc", "tears", t)
        fake.script(CallClass.ACTOR_COGNITION, actor_id=w.id("dale"), response=watch(w))
        _, out = moment(w, ["dale"], t)
        assert (out[w.id("dale")].bound.def_id, out[w.id("dale")].source) == ("rest", "reflex")
    finally:
        w.store.close()


# --------------------------------------------------------------------------- the whole turn
def test_disrespect_him_twice_and_he_decks_you(bar, fake):
    """Reggie at the end of his rope with no nerve left: the first insult gets under his skin, the
    second one breaks him, and in the same turn he punches the player (whether it lands is the
    dice's). The anger was taken in by the pipeline (S3b), the snap is on record, and his packet
    never had to choose it."""
    from as_engine.service.view import build_view
    w = bar()
    t = now(w)
    from as_engine.mind import actor
    with w.store.transaction() as tx:
        c = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=t, turn_index=0, payload={"what": "test"}))
        actor.adjust_stress(tx, w.id("reggie"), 9, c.event_id, t, 0)
    s = w.session()
    fake.script(CallClass.INTAKE, lambda r: {"choice": pick(w, r, "observe_area"), "none_reason": None, "manner": "",
                                            "remainder": None, "clarify": None})
    assert play(s, "do", "I stay where I am and take in the room.").ok     # the player stands his ground

    def ref(local):
        with s.store.transaction() as tx:
            v = build_view(tx, s)
        return next(p.ref for p in v.location.people if s.extras["view_refs"][p.ref] == w.id(local))

    assert play(s, "say", "You're a useless bastard, Reggie.", addressee_refs=[ref("reggie")]).ok
    assert not [e for e in w.store.query("SELECT * FROM events WHERE type = 'INVOLUNTARY'")]
    heat = temper.heat(w.store, w.id("reggie"), w.id("pc"), now(w))
    assert heat == 2, "it gets under his skin"
    assert play(s, "say", "I said you're a useless bastard. Everybody here knows it.", addressee_refs=[ref("reggie")]).ok
    (inv,) = [dict(r, payload=json.loads(r["payload"])) for r in w.store.query("SELECT * FROM events WHERE type = 'INVOLUNTARY'")]
    assert inv["actor_id"] == w.id("reggie") and inv["payload"]["outlet"] == "fists" and inv["payload"]["toward_id"] == w.id("pc")
    starts = [dict(r, payload=json.loads(r["payload"])) for r in w.store.query(
        "SELECT * FROM events WHERE type = 'ACTION_START' AND actor_id = ? ORDER BY seq", (w.id("reggie"),))]
    punch = [e for e in starts if e["payload"]["def_id"] == "punch"]
    assert len(punch) == 1 and punch[0]["payload"]["target_id"] == w.id("pc") and punch[0]["at"] == inv["at"]
    (done,) = [dict(r, payload=json.loads(r["payload"])) for r in w.store.query(
        "SELECT * FROM events WHERE type = 'ACTION_COMPLETE' AND actor_id = ? AND json_extract(payload, '$.def_id') = 'punch'",
        (w.id("reggie"),))]
    assert done["payload"]["result"] in ("hit", "miss")
