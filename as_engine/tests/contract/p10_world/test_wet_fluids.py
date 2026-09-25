"""The wet strain as the owner told it (P10, W1: DECISIONS D-77, D-80). physical/bodies.py
contagious; action/effects.py treat_wound / strike_melee (fluid contact) and spit; turn/cognition.py
step 3 (the compulsion) and urge_pc; narration/narrator.py URGE_LINE; world/infected.py INF-07.

The owner: from day three every fluid of a host carries it — blood, saliva, mucus — and the dead's
fluids too. The urge is to contaminate: spit into water and food, and into the mouths of people
asleep; the host is sickened by it, and it grows without end. And for the player: what you type
mostly happens — but as it advances, some of what you do comes out as the urge instead.

A clinic at night (a dict scenario): Vera the medic, Lou (a host), Sam asleep on a cot beside him,
Kit awake by the door, a strip of jerky on the table, the player across the room.
"""

from __future__ import annotations

import copy

import pytest

import helpers
from as_engine.action.intent import barrier
from as_engine.action.resolve import resolve_wave
from as_engine.contracts.common import LOD, Lane
from as_engine.contracts.events import Event, EventType, WriteOp, WriteRecord
from as_engine.lanes.scheduler import CognitionPlan
from as_engine.mind.affordance import enumerate_affordances
from as_engine.physical import bodies, objects
from as_engine.physical.bodies import WoundSpec
from as_engine.physical.objects import Holder
from as_engine.testing.scenario import load_scenario
from as_engine.world import infected

pytestmark = pytest.mark.phase(10)

H = 3_600_000
MIN = 60_000

CLINIC = {
    "schema": "as.scenario.v1", "name": "night_clinic", "seed": 101, "start": {"day": 1100, "time": "02:00"},
    "places": [{"id": "clinic", "name": "Clinic", "material": "brick", "light": 3, "width_m": 12, "depth_m": 8,
                "anchors": [{"id": "table", "name": "table", "x": 3.5, "y": 4}, {"id": "door", "name": "door", "x": 11, "y": 1}]}],
    "bodies": [
        {"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "clinic", "x": 10, "y": 7},
        {"id": "vera", "stub": {"name": "Vera Lind", "age": 45, "sex": "female", "skills": {"medicine": 2}},
         "place": "clinic", "x": 2.5, "y": 4},
        {"id": "lou", "stub": {"name": "Lou Carr", "age": 33, "sex": "male"}, "place": "clinic", "x": 3, "y": 4,
         "wounds": [{"anatomy": "arm_l", "type": "cut", "severity": "significant"}]},
        {"id": "sam", "stub": {"name": "Sam Carr", "age": 30, "sex": "male"}, "place": "clinic", "x": 3, "y": 5,
         "awareness": "asleep", "posture": "lying"},
        {"id": "kit", "stub": {"name": "Kit Salas", "age": 26, "sex": "female"}, "place": "clinic", "anchor": "door",
         "inventory": [{"item": "core:item/kitchen_knife", "slot": "hand_r", "label": "knife"}]},
    ],
    "items": [{"item": "core:item/jerky_pack", "place": "clinic", "anchor": "table", "label": "jerky"}],
}


@pytest.fixture
def clinic(fixture_packs, core_pack_dir):
    worlds = []

    def _load(change=None):
        spec = copy.deepcopy(CLINIC)
        if change is not None:
            change(spec)
        w = load_scenario(spec, packs_root=fixture_packs, core_pack_dir=core_pack_dir)
        worlds.append(w)
        return w

    yield _load
    for w in worlds:
        w.store.close()


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def infect(w, local, hours_ago, pathway="wet"):
    rec = w.canon.find("pathway", pathway)
    stage = [s for s in rec.stages if s.starts_at_h <= hours_ago][-1].name
    b = w.id(local)
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.INFECTION_EXPOSURE, writer="physical.bodies", at=now(w), turn_index=0,
                              actor_id=b, payload={"body_id": b, "pathway": pathway, "exposure": "bite", "infected": True},
                              writes=[WriteRecord(op=WriteOp.INSERT, table="infections", values={
                                  "body_id": b, "pathway": pathway, "exposed_at": now(w) - int(hours_ago * H),
                                  "stage": stage, "cause_event": "test", "known_to_self": 0})]))
    return stage


def bottle(w, local, slot="hand_r"):
    with w.store.transaction() as tx:
        ev = objects.create(tx, "core:item/water_bottle", 1, Holder(kind="body", id=w.id(local), slot=slot), "scenario", {},
                            now(w), None, 0)
    return ev.payload["item_id"]


def run(w, *intents, rng=None, at=None):
    t = now(w) if at is None else at
    with w.store.transaction() as tx:
        return resolve_wave(tx, rng or w.rng, barrier(tx, list(intents)), t, 0, horizon_ms=t + 10 * MIN)


def of(evs, type_):
    return [e for e in evs if e.type == type_]


def events(w, type_):
    import json
    return [dict(r, payload=json.loads(r["payload"])) for r in w.store.query("SELECT * FROM events WHERE type = ? ORDER BY seq",
                                                                             (type_,))]


def decide(w, locals_, at):
    import asyncio
    from as_engine.turn import cognition
    ids = [w.id(x) for x in locals_]
    s = w.session()
    with w.store.transaction() as tx:
        affs = {a: enumerate_affordances(tx, a, w.canon.all("affordance"), at, 0) for a in ids}
        plan = CognitionPlan(lod={a: LOD.COLD for a in ids}, lane={a: Lane.A for a in ids})
        return asyncio.run(cognition.decide(tx, s, plan, affs, 0, at, reaction=False))


def wound_of(w, local):
    return w.store.query_one("SELECT wound_id FROM wounds WHERE body_id = ? ORDER BY wound_id", (w.id(local),))[0]


# --------------------------------------------------------------------------- every fluid
def test_from_day_three_everything_that_comes_out_of_them_carries_it(clinic):
    w = clinic()
    assert not bodies.contagious(w.store, w.id("lou"))
    infect(w, "lou", 48)
    assert not bodies.contagious(w.store, w.id("lou")), "before day three"
    w2 = clinic()
    infect(w2, "lou", 80)
    assert bodies.contagious(w2.store, w2.id("lou"))
    with w2.store.transaction() as tx:
        dead = infected.spawn(tx, w2.rng, w2.id("clinic"), infected.SHAMBLER, now(w2), 0, None, x_m=8, y_m=6)
    assert bodies.contagious(w2.store, dead), "the dead's fluids too"
    assert not bodies.contagious(w2.store, w2.id("vera"))


def test_blood_on_the_hands_that_stop_it(clinic):
    """Vera presses on Lou's cut: a host's blood on her hands is an exposure ('fluid_contact')."""
    w = clinic()
    infect(w, "lou", 80)
    rng = helpers.ScriptedRng(True)
    evs = run(w, helpers.make_intent(w, "vera", "apply_pressure", target=wound_of(w, "lou")), rng=rng)
    (tr,) = of(evs, "TREATMENT")
    (exp,) = of(evs, "INFECTION_EXPOSURE")
    assert (exp.payload["body_id"], exp.payload["exposure"], exp.payload["infected"], exp.cause_event_id) == \
        (w.id("vera"), "fluid_contact", True, tr.event_id)


def test_a_clean_wound_is_just_a_wound(clinic):
    w = clinic()
    evs = run(w, helpers.make_intent(w, "vera", "apply_pressure", target=wound_of(w, "lou")), rng=helpers.ScriptedRng())
    assert of(evs, "TREATMENT") and not of(evs, "INFECTION_EXPOSURE")


def test_their_blood_in_your_eyes(clinic):
    """Kit opens a host up with a knife (a clean win: significant): his blood splashes back
    ('fluid_splash'). The same blow on a clean man carries nothing."""
    w = clinic(lambda s: [b.update(anchor=None, x=3.5, y=4) for b in s["bodies"] if b["id"] == "kit"])
    infect(w, "lou", 80)
    rng = helpers.ScriptedRng(1, 10, 0, False)
    evs = run(w, helpers.make_intent(w, "kit", "strike_melee", target="lou", item="knife"), rng=rng)
    (harm,) = of(evs, "HARM")
    assert harm.payload["severity"] in ("significant", "severe", "catastrophic")
    (exp,) = of(evs, "INFECTION_EXPOSURE")
    assert (exp.payload["body_id"], exp.payload["exposure"], exp.cause_event_id) == (w.id("kit"), "fluid_splash", harm.event_id)
    w2 = clinic(lambda s: [b.update(anchor=None, x=3.5, y=4) for b in s["bodies"] if b["id"] == "kit"])
    evs = run(w2, helpers.make_intent(w2, "kit", "strike_melee", target="lou", item="knife"), rng=helpers.ScriptedRng(1, 10, 0))
    assert of(evs, "HARM") and not of(evs, "INFECTION_EXPOSURE")


def test_a_nick_splashes_nothing(clinic):
    """Only a blow that opens them up (significant or worse) splashes: the same knife winning by a
    hair (COST: a light weapon's minor wound) draws no blood worth the name."""
    w = clinic(lambda s: [b.update(anchor=None, x=3.5, y=4) for b in s["bodies"] if b["id"] == "kit"])
    infect(w, "lou", 80)
    evs = run(w, helpers.make_intent(w, "kit", "strike_melee", target="lou", item="knife"), rng=helpers.ScriptedRng(1, 3, 0, False))
    (harm,) = of(evs, "HARM")
    assert harm.payload["severity"] == "minor" and not of(evs, "INFECTION_EXPOSURE")


# --------------------------------------------------------------------------- the urge to contaminate
def test_the_sleeper_first(clinic):
    """Week three, a bottle in his hand, Vera awake beside him and Sam asleep on the cot: he bends
    over the sleeper. He is sickened by it."""
    w = clinic()
    infect(w, "lou", 400)
    bottle(w, "lou")
    t = now(w)
    it = decide(w, ["lou"], t)[w.id("lou")]
    assert (it.bound.def_id, it.bound.target_id, it.source) == ("spit_in_mouth", w.id("sam"), "reflex")
    [inv] = events(w, "INVOLUNTARY")
    assert inv["payload"] == {"actor_id": w.id("lou"), "kind": "compulsion", "pathway": "wet", "act": "mouth",
                              "item_id": None, "target_id": w.id("sam")}
    stress = [e for e in events(w, "RESOLVE_CHANGE") if e["payload"].get("stress_delta") == 1]
    disgust = [e for e in events(w, "RESOLVE_CHANGE") if e["payload"].get("reason") == "self_disgust"]
    assert stress and disgust and stress[0]["cause_event_id"] == disgust[0]["cause_event_id"] == inv["event_id"]


def test_what_it_does_to_a_sleeper(clinic):
    w = clinic()
    infect(w, "lou", 400)
    evs = run(w, helpers.make_intent(w, "lou", "spit_in_mouth", target="sam"), rng=helpers.ScriptedRng(True))
    (exp,) = of(evs, "INFECTION_EXPOSURE")
    assert (exp.payload["body_id"], exp.payload["exposure"], exp.payload["infected"]) == (w.id("sam"), "mouth_contact_direct", True)
    assert of(evs, "ACTION_COMPLETE")[0].payload["result"] == "spat"
    evs = run(w, helpers.make_intent(w, "lou", "spit_in_mouth", target="vera"), rng=helpers.ScriptedRng())
    assert of(evs, "ACTION_COMPLETE")[0].payload["result"] == "missed" and not of(evs, "INFECTION_EXPOSURE"), "awake"


def test_nobody_asleep_and_nothing_in_hand_it_goes_for_the_food(clinic):
    """Week three with empty hands and nobody asleep: the jerky on the table half a metre away."""
    w = clinic(lambda s: [b.update(awareness="awake", posture="standing") for b in s["bodies"] if b["id"] == "sam"])
    infect(w, "lou", 400)
    it = decide(w, ["lou"], now(w))[w.id("lou")]
    assert (it.bound.def_id, it.bound.item_id) == ("spit_into", w.id("jerky"))
    evs = run(w, it)
    assert of(evs, "ACTION_COMPLETE")[-1].payload["result"] == "spat"
    mark = objects.contaminated(w.store, w.id("jerky"), now(w) + MIN)
    assert mark is not None and mark["by"] == w.id("lou") and mark["lasting"] is False


def test_the_urge_comes_ever_more_often(clinic):
    """The gap is compulsion_cooldown_min x 336 / hours (never under the minimum): at two weeks it
    comes back after 10 minutes, at four weeks after 5."""
    R_ = None
    for hours, again_after in ((336, 10), (672, 5)):
        w = clinic()
        R_ = w.store.rules.infected
        infect(w, "lou", hours)
        t = now(w)
        decide(w, ["lou"], t)
        assert len(events(w, "INVOLUNTARY")) == 1
        decide(w, ["lou"], t + (again_after - 1) * MIN)
        assert len(events(w, "INVOLUNTARY")) == 1, (hours, "not yet")
        decide(w, ["lou"], t + again_after * MIN)
        assert len(events(w, "INVOLUNTARY")) == 2, (hours, "again")
    assert R_.compulsion_cooldown_min == 10 and R_.compulsion_min_gap_min == 2


# --------------------------------------------------------------------------- the player's hand (D-80)
def test_what_the_player_types_mostly_happens(clinic):
    from as_engine.turn import cognition
    w = clinic(lambda s: [b.update(x=3.5, y=5) for b in s["bodies"] if b["id"] == "pc"])
    infect(w, "pc", 400)
    mine = helpers.make_intent(w, "pc", "wait_here", source="human")
    with w.store.transaction() as tx:
        kept = cognition.urge_pc(tx, helpers.ScriptedRng(False), w.id("pc"), mine, 0, now(w))
    assert kept is mine and events(w, "INVOLUNTARY") == []
    rng = helpers.ScriptedRng(True)
    with w.store.transaction() as tx:
        taken = cognition.urge_pc(tx, rng, w.id("pc"), mine, 0, now(w))
    assert (taken.bound.def_id, taken.bound.target_id, taken.source) == ("spit_in_mouth", w.id("sam"), "reflex")
    assert rng.asked == [("chance", "mind", f"pc_urge:{w.id('pc')}:{now(w)}")]
    [inv] = events(w, "INVOLUNTARY")
    assert inv["payload"]["pc"] is True and inv["payload"]["kind"] == "compulsion" and inv["actor_id"] == w.id("pc")


def test_the_story_says_it_was_not_their_choice(clinic):
    from as_engine.narration.narrator import URGE_LINE, build_narrator_packet
    from as_engine.turn import cognition
    w = clinic(lambda s: [b.update(x=3.5, y=5) for b in s["bodies"] if b["id"] == "pc"])
    infect(w, "pc", 400)
    with w.store.transaction() as tx:
        cognition.urge_pc(tx, helpers.ScriptedRng(True), w.id("pc"), helpers.make_intent(w, "pc", "wait_here", source="human"),
                          0, now(w))
        pkt = build_narrator_packet(tx, w.id("pc"), 0, now(w), w.session().settings)
    assert URGE_LINE == "Your body did it before you could stop it." and URGE_LINE in pkt.pc_state_lines


def test_week_two_the_player_only_feels_it(clinic):
    from as_engine.turn import cognition
    w = clinic(lambda s: [b.update(x=3.5, y=5) for b in s["bodies"] if b["id"] == "pc"])
    infect(w, "pc", 200)
    mine = helpers.make_intent(w, "pc", "wait_here", source="human")
    with w.store.transaction() as tx:
        assert cognition.urge_pc(tx, helpers.ScriptedRng(), w.id("pc"), mine, 0, now(w)) is mine


def test_the_urge_is_never_on_a_menu(clinic):
    w = clinic()
    infect(w, "lou", 400)
    with w.store.transaction() as tx:
        aff = enumerate_affordances(tx, w.id("lou"), w.canon.all("affordance"), now(w), 0)
    names = {o.def_id for o in aff.pool} | {r.def_id for r in aff.rejected}
    assert not names & {"spit_into", "spit_in_mouth"}
