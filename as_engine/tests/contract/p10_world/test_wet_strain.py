"""The wet strain's living spreaders (P10). Lore §3.2 (CODEX v2): saliva infective from about day
three; weeks one to three a growing pull toward sharing anything that has touched the mouth and a
will that weakens until, by week three, nothing stops compliance; week four is fever, mucus and
collapse. Rules: the wet pathway's stages (felt, signs), physical.bodies.stages,
physical.objects.contaminate / contaminated, action.effects drink (mouth contact), mind.cues
(bite_wound_seen and stage signs), mind.packet body_lines, the narrator's pc_state_lines,
turn.cognition step 3 (the compulsion, never the PC) — W1 (D-77, D-80) in test_wet_fluids.py.
"""

from __future__ import annotations

import asyncio
import json

import helpers
import pytest

from as_engine.action.intent import barrier
from as_engine.action.resolve import resolve_wave
from as_engine.contracts.common import LOD, Lane
from as_engine.contracts.events import Event, EventType, WriteOp, WriteRecord
from as_engine.lanes.scheduler import CognitionPlan
from as_engine.mind import perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.mind.cues import cues_of
from as_engine.physical import bodies, objects
from as_engine.physical.bodies import WoundSpec
from as_engine.physical.objects import Holder

pytestmark = pytest.mark.phase(10)

H = 3_600_000
MIN = 60_000


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def infect(w, local, hours_ago, pathway="wet"):
    """Test setup: the body has carried the infection for ``hours_ago`` hours (and is at the stage
    that makes). Returns the stage name."""
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


def bottle(w, local, slot="hand_r", qty=3) -> str:
    with w.store.transaction() as tx:
        ev = objects.create(tx, "core:item/water_bottle", qty, Holder(kind="body", id=w.id(local), slot=slot),
                            "scenario", {}, now(w), None, 0)
    return ev.payload["item_id"]


def drink(w, local, item_id, at):
    with w.store.transaction() as tx:
        return resolve_wave(tx, w.rng, barrier(tx, [helpers.make_intent(w, local, "drink_water", item=item_id)]), at, 0,
                            horizon_ms=at + 10 * MIN)


def hand_over(w, item_id, to_local, at, slot="hand_l"):
    with w.store.transaction() as tx:
        objects.transfer(tx, item_id, Holder(kind="body", id=w.id(to_local), slot=slot), None, at, None, None, 0)


def events(w, type_):
    return [dict(r, payload=json.loads(r["payload"])) for r in
            (dict(x) for x in w.store.query("SELECT * FROM events WHERE type = ? ORDER BY seq", (type_,)))]


# =========================================================================== the pathway
def test_the_wet_strain_runs_as_the_lore_says(canon):
    """Saliva infective from day three (72 h); the compulsion grows 1 -> 2 -> 3 and is absolute by
    week three (336 h); every stage from day three is felt; signs are registry cues; drinking after
    a spreader is an exposure."""
    rec = canon.find("pathway", "wet")
    first_saliva = next(s for s in rec.stages if s.saliva_infectious)
    assert first_saliva.starts_at_h == 72.0
    assert all(not s.saliva_infectious for s in rec.stages if s.starts_at_h < 72.0)
    comp = [s.compulsion for s in rec.stages]
    assert comp == sorted(comp) and max(comp) == 3
    assert all(s.compulsion == 0 for s in rec.stages if s.starts_at_h < 72.0)
    assert [s.compulsion for s in rec.stages if s.starts_at_h >= 336.0] == [3, 3]
    assert all(s.felt for s in rec.stages if s.starts_at_h >= 72.0)
    for s in rec.stages:
        assert "wet" not in s.felt.lower() and "infect" not in s.felt.lower() and s.name not in s.felt
        for c in s.signs:
            assert canon.find("cue", c) is not None
    assert "fever_seen" in rec.stages[-1].signs
    assert 0 < rec.exposure["mouth_contact_item"] < 1


def test_a_sign_must_be_a_known_cue(tmp_path, core_pack_dir):
    """CNT-05 covers pathway stages[].signs."""
    import shutil

    from as_engine.content.pack import load_canon
    pack = tmp_path / "core"
    shutil.copytree(core_pack_dir, pack)
    f = pack / "pathways" / "pathways.yaml"
    f.write_text(f.read_text(encoding="utf-8").replace("signs: [fever_seen, spreader_signs]",
                                                       "signs: [fever_seen, glowing_eyes]"), encoding="utf-8")
    _c, issues = load_canon([pack])
    assert any(i.code == "CNT-05" and "glowing_eyes" in i.message for i in issues if i.severity == "error")


def test_stages_reads_what_the_infection_is_doing(scenario):
    w = scenario("metal_fence")
    assert bodies.stages(w.store, w.id("alice")) == []
    name = infect(w, "alice", 200)
    [(pw, st)] = bodies.stages(w.store, w.id("alice"))
    assert (pw, st.name, st.compulsion, st.saliva_infectious) == ("wet", name, 2, True)


# =========================================================================== the shared bottle
def test_drinking_after_a_spreader(scenario):
    """A spreader's mouth marks the bottle (ITEM_CONTAMINATED); whoever drinks from it next is
    exposed ('mouth_contact_item'); a mark older than I.saliva_hours exposes nobody."""
    w = scenario("metal_fence")
    infect(w, "alice", 100)
    b = bottle(w, "alice")
    t0 = now(w)
    drink(w, "alice", b, t0)
    [mark] = events(w, "ITEM_CONTAMINATED")
    assert mark["payload"] == {"item_id": b, "pathway": "wet", "by": w.id("alice"), "lasting": False}, "saliva dries (I1)"
    c = objects.contaminated(w.store, b, t0 + MIN)
    assert c is not None and (c["pathway"], c["by"]) == ("wet", w.id("alice"))
    assert events(w, "INFECTION_EXPOSURE")[-1]["payload"]["body_id"] == w.id("alice"), "her own mouth exposes nobody"
    hand_over(w, b, "pc", t0 + MIN)
    drink(w, "pc", b, t0 + 2 * MIN)
    got = [e["payload"] for e in events(w, "INFECTION_EXPOSURE") if e["payload"]["body_id"] == w.id("pc")]
    assert len(got) == 1 and (got[0]["pathway"], got[0]["exposure"]) == ("wet", "mouth_contact_item")
    late = t0 + int(w.store.rules.infected.saliva_hours * H) + MIN
    assert objects.contaminated(w.store, b, late) is None
    hand_over(w, b, "mara", late)
    drink(w, "mara", b, late + MIN)
    assert not [e for e in events(w, "INFECTION_EXPOSURE") if e["payload"]["body_id"] == w.id("mara")]


def test_before_day_three_the_bottle_stays_clean(scenario):
    w = scenario("metal_fence")
    infect(w, "alice", 48)
    b = bottle(w, "alice")
    drink(w, "alice", b, now(w))
    assert events(w, "ITEM_CONTAMINATED") == [] and objects.contaminated(w.store, b, now(w)) is None


# =========================================================================== what is felt
def test_the_host_feels_it_and_is_not_told_what_it_is(scenario):
    """mind.packet body_lines carry the stage's felt sentence; nothing names the infection."""
    from as_engine.mind.packet import build_packet
    w = scenario("metal_fence")
    name = infect(w, "alice", 200)
    felt = w.canon.find("pathway", "wet").stages[[s.name for s in w.canon.find("pathway", "wet").stages].index(name)].felt
    with w.store.transaction() as tx:
        affs = enumerate_affordances(tx, w.id("alice"), w.canon.all("affordance"), now(w), 0)
        pkt = build_packet(tx, w.id("alice"), LOD.HOT, affs, 0, now(w), reaction=False)
    assert felt in pkt.body_lines and "Unhurt." not in pkt.body_lines
    text = " ".join(pkt.body_lines).lower()
    assert "wet" not in text and "infect" not in text and name not in text


def test_the_pc_feels_it_in_the_story(scenario):
    from as_engine.narration.narrator import build_narrator_packet
    w = scenario("metal_fence")
    infect(w, "pc", 400)
    felt = next(s.felt for s in w.canon.find("pathway", "wet").stages if s.name == "living_spreader_week3")
    with w.store.transaction() as tx:
        pkt = build_narrator_packet(tx, w.id("pc"), 0, now(w), w.session().settings)
    assert felt in pkt.pc_state_lines


# =========================================================================== what shows
def _cues(w, local, at):
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id(local), at, 0)
        return cues_of(tx, w.id(local), 0, at)


def in_plain_view(w):
    """A sign needs a CLEAR look: the sales floor lit, and Alice out from behind the counter, 1.5 m
    from the PC (Mara, at the front window, is more than 5 m away)."""
    from as_engine.physical import space
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 3}, "test", now(w), None, 0)
        tx.commit_event(space.move_event(tx, w.id("alice"), w.id("sales_floor"), None, 7.5, 4.0, now(w), None, 0))


def test_fever_and_spreader_signs_are_seen_close(scenario):
    """A clear sighting within I.sign_range_m of a host gets the stage's signs; farther, or another
    room, gets nothing."""
    w = scenario("metal_fence")
    in_plain_view(w)
    infect(w, "alice", 520)
    t = now(w) + 500
    near = _cues(w, "pc", t)                     # 1.5 m from Alice
    assert {"fever_seen", "spreader_signs"} <= near
    assert not {"fever_seen", "spreader_signs"} & _cues(w, "mara", t), "Mara is almost 6 m away"
    assert not {"fever_seen", "spreader_signs"} & _cues(w, "june", t), "June is in the stockroom"


def test_a_week_one_host_shows_nothing(scenario):
    w = scenario("metal_fence")
    in_plain_view(w)
    infect(w, "alice", 30)
    assert not {"fever_seen", "spreader_signs", "bite_wound_seen"} & _cues(w, "pc", now(w) + 500)


def test_a_bite_is_seen(scenario):
    w = scenario("metal_fence")
    in_plain_view(w)
    with w.store.transaction() as tx:
        cause = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=now(w), turn_index=0,
                                      payload={"what": "a test bite"}))
        bodies.apply_harm(tx, w.id("alice"), WoundSpec("arm_l", "bite", "minor", 3), now(w), cause.event_id, 0, w.rng)
    assert "bite_wound_seen" in _cues(w, "pc", now(w) + 500)
    assert "bite_wound_seen" not in _cues(w, "mara", now(w) + 500)


def test_in_the_dark_nothing_shows(scenario):
    """The same host behind the counter on the unlit sales floor: no clear look, no signs."""
    w = scenario("metal_fence")
    infect(w, "alice", 520)
    assert not {"fever_seen", "spreader_signs"} & _cues(w, "pc", now(w) + 500)


# =========================================================================== the compulsion
def _decide(w, locals_, at):
    from as_engine.turn import cognition
    ids = [w.id(x) for x in locals_]
    s = w.session()
    with w.store.transaction() as tx:
        affs = {a: enumerate_affordances(tx, a, w.canon.all("affordance"), at, 0) for a in ids}
        plan = CognitionPlan(lod={a: LOD.COLD for a in ids}, lane={a: Lane.A for a in ids})
        return asyncio.run(cognition.decide(tx, s, plan, affs, 0, at, reaction=False))


def test_by_week_three_the_bottle_is_offered(scenario):
    """turn.cognition step 3: a week-3 host with water in hand and a person within 1.5 m hands it
    over whatever it had decided (INVOLUNTARY 'compulsion', source 'reflex'); not again inside
    I.compulsion_cooldown_min; then again."""
    w = scenario("metal_fence")
    infect(w, "alice", 400)
    b = bottle(w, "alice")
    t = now(w)
    out = _decide(w, ["alice"], t)
    it = out[w.id("alice")]
    assert (it.bound.def_id, it.bound.target_id, it.bound.item_id, it.source, it.speech) == (
        "give_item", w.id("pc"), b, "reflex", None)
    [inv] = events(w, "INVOLUNTARY")
    assert inv["payload"] == {"actor_id": w.id("alice"), "kind": "compulsion", "pathway": "wet", "act": "give",
                              "item_id": b, "target_id": w.id("pc")} and inv["actor_id"] == w.id("alice")
    again = _decide(w, ["alice"], t + MIN)[w.id("alice")]
    assert again.bound.def_id != "give_item" and len(events(w, "INVOLUNTARY")) == 1
    later = _decide(w, ["alice"], t + w.store.rules.infected.compulsion_cooldown_min * MIN)[w.id("alice")]
    assert later.bound.def_id == "give_item" and len(events(w, "INVOLUNTARY")) == 2


def test_week_two_only_wants_to(scenario):
    """W1 (D-77): week two it only wants to — an 'urge' on record, and holding back costs Resolve;
    what it decided stands."""
    w = scenario("metal_fence")
    infect(w, "alice", 200)
    b = bottle(w, "alice")
    it = _decide(w, ["alice"], now(w))[w.id("alice")]
    assert it.bound.def_id != "give_item" and it.source != "reflex"
    [urge] = events(w, "INVOLUNTARY")
    assert urge["payload"] == {"actor_id": w.id("alice"), "kind": "urge", "pathway": "wet", "act": "give", "item_id": b,
                               "target_id": w.id("pc")}
    [cost] = [e for e in events(w, "RESOLVE_CHANGE") if e["payload"].get("reason") == "resisting_urge"]
    assert cost["cause_event_id"] == urge["event_id"] and cost["actor_id"] == w.id("alice")


def test_nothing_at_hand_nothing_happens_and_alone_it_fouls_its_own_water(scenario):
    """W1: a bottle in the pack is not at hand; alone at the front window with a bottle in her hand,
    Mara spits into it — the supply is fouled for whoever drinks next."""
    w = scenario("metal_fence")
    infect(w, "alice", 400)
    bottle(w, "alice", slot="pack")
    assert _decide(w, ["alice"], now(w))[w.id("alice")].bound.def_id != "give_item"
    assert events(w, "INVOLUNTARY") == []
    infect(w, "mara", 400)
    b = bottle(w, "mara")                            # nobody within 1.5 m of the front window
    it = _decide(w, ["mara"], now(w))[w.id("mara")]
    assert (it.bound.def_id, it.bound.item_id, it.source) == ("spit_into", b, "reflex")
    [inv] = events(w, "INVOLUNTARY")
    assert inv["payload"]["act"] == "spit" and inv["payload"]["target_id"] is None


def test_the_pc_is_never_compelled(scenario):
    """The player's hand on their character is never taken: even in a plan, the PC's intent stands."""
    w = scenario("metal_fence")
    infect(w, "pc", 400)
    with w.store.transaction() as tx:
        objects.transfer(tx, w.id("glock"), Holder(kind="body", id=w.id("pc"), slot="worn"), None, now(w), None, None, 0)
    bottle(w, "pc")
    it = _decide(w, ["pc", "alice"], now(w))[w.id("pc")]
    assert it.bound.def_id != "give_item" and events(w, "INVOLUNTARY") == []
