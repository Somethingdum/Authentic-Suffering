"""The Skull Packet (P4). Rules SKULL-01..09, WILL-00, WILL-C (mind/packet.py).

A packet is everything one mind may know right now, and nothing else. It is built only from that
mind's own body, inventory, records and percepts; handles replace every internal id.
"""

from __future__ import annotations

import re

import pytest

import helpers
from as_engine.contracts.common import LOD, CallClass, Fidelity, Standing, UtteranceForm
from as_engine.contracts.events import Event, EventType
from as_engine.contracts.mind import SkullPacket, UtteranceView
from as_engine.contracts.settings import PacketRules, RulesConfig
from as_engine.kernel.rng import Rng
from as_engine.mind import perception
from as_engine.mind.affordance import AffordanceSet, enumerate_affordances
from as_engine.mind.packet import build_packet, estimate_tokens
from as_engine.physical import bodies, space
from as_engine.physical.bodies import WoundSpec
from as_engine.prompts.render import render

pytestmark = pytest.mark.phase(4)

ID_RE = re.compile(r"\b(evt|act|plc|anc|prt|itm|pct|prp|clm|wnd|tsk|olp|ref|epi)_\d{6}\b")


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def commit(w, **ev):
    with w.store.transaction() as tx:
        return tx.commit_event(Event(turn_index=0, **ev))


def gust(w, at):
    return commit(w, type=EventType.NOISE, writer="action.propagate", at=at,
                  payload={"source_db": 98, "kind": "metal_crash", "text": "a loud metal crash",
                           "place_id": w.id("alley"), "anchor_id": w.id("fence_sheet")})


def say(w, speaker, words, to, at, volume="raised", **extra):
    return commit(w, type=EventType.SPEECH, writer="action.propagate", actor_id=w.id(speaker), at=at,
                  payload={"words": words, "volume": volume, "to": [w.id(t) for t in to] or ["everyone"],
                           "source_db": 70, **extra})


def packet_for(w, local, at, lod=LOD.HOT, reaction=False) -> SkullPacket:
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id(local), at, 0)
        aff = enumerate_affordances(tx, w.id(local), w.canon.all("affordance"), at, 0)
        return build_packet(tx, w.id(local), lod, aff, 0, at, reaction=reaction)


def rendered(p: SkullPacket, reaction=False) -> str:
    msgs = render(CallClass.ACTOR_REACTION if reaction else CallClass.ACTOR_COGNITION, p=p)
    return msgs[0].content + "\n" + msgs[1].content


def crash_and_call(w):
    """metal_fence: the crash, then Mara calls to June from the front window."""
    t = now(w)
    gust(w, t)
    say(w, "mara", "June, stay where you are.", ["june"], t + 1500)
    return t + 2000


# --------------------------------------------------------------------------- SKULL-01 own percepts only
def test_packet_contains_only_own_percepts(scenario):
    w = scenario("metal_fence")
    at = crash_and_call(w)
    p = packet_for(w, "june", at)
    mine = {r["percept_id"] for r in helpers.percepts_of(w.store, w.id("june"), 0)}
    shown = {p.handles[x.handle] for x in p.perceived_now} | {p.handles[u.handle] for u in p.utterances}
    assert shown == mine and shown
    others = {r["percept_id"] for r in w.store.query("SELECT percept_id FROM percept_log WHERE holder_id != ?", (w.id("june"),))}
    assert not shown & others


def test_handles(scenario):
    w = scenario("metal_fence")
    at = crash_and_call(w)
    p = packet_for(w, "june", at)
    rows = helpers.percepts_of(w.store, w.id("june"), 0)
    s_handles = sorted([*p.perceived_now, *p.utterances], key=lambda x: int(x.handle[1:]))
    assert [p.handles[x.handle] for x in s_handles] == [r["percept_id"] for r in rows], "S1..Sn chronological"
    assert p.utterances[0].handle == "S2", "crash first, then the call, then the standing view"
    # entities: Mara (source of the call) first, then Owen (June has a relationships row toward him)
    assert [(e.handle, p.handles[e.handle]) for e in p.entities][:2] == [("P1", w.id("mara")), ("P2", w.id("pc"))]
    assert all(p.handles[e.handle] != w.id("june") for e in p.entities), "never yourself"
    # affordances: A1.. in AffordanceSet order, mapped to signatures
    with w.store.transaction() as tx:
        aff = enumerate_affordances(tx, w.id("june"), w.canon.all("affordance"), at, 0)
    assert [p.handles[a.handle] for a in p.affordances] == [o.signature for o in aff.options]
    assert [a.handle for a in p.affordances] == [f"A{i}" for i in range(1, len(aff.options) + 1)]
    h = helpers.handle_for(p, "go_look", "back_door_in", w)
    assert p.handles[h] == f"go_look:*:{w.id('back_door_in')}:*"


# --------------------------------------------------------------------------- WILL-00 utterances
def test_speech_arrives_as_a_labelled_utterance(scenario):
    w = scenario("metal_fence")
    at = crash_and_call(w)
    p = packet_for(w, "june", at)
    (u,) = p.utterances
    assert (u.words, u.speaker_handle, u.addressed_to_me, u.fidelity) == ("June, stay where you are.", "P1", True, Fidelity.EXACT)
    assert u.standing == Standing.PEER, "June knows Mara; Mara is not in her accepted authority"
    assert u.form == UtteranceForm.DEMAND, "an imperative without authority is a demand, not an order"
    assert all(x.channel.value != "speech" for x in p.perceived_now)
    for model in (SkullPacket, UtteranceView):
        for name in model.model_fields:
            assert not re.search(r"request|order|task|ask", name), f"{model.__name__}.{name}"


def test_form_and_standing_come_from_the_receiver(scenario):
    w = scenario("request_firewall")
    t = now(w)
    say(w, "ray", "Keep boarding.", ["mara"], t, volume="normal")
    say(w, "pc", "Put the hammer down.", ["mara"], t + 3000, volume="normal")
    say(w, "pc", "Put the hammer down or I'll shoot.", ["mara"], t + 6000, armed=True)
    say(w, "pc", "Open the door.", ["mara"], t + 9000, volume="normal", armed=True)
    p = packet_for(w, "mara", t + 10000)
    got = [(u.words, u.form, u.standing) for u in p.utterances]
    assert got == [
        ("Keep boarding.", UtteranceForm.ORDER, Standing.VALID_ORDER),
        ("Put the hammer down.", UtteranceForm.DEMAND, Standing.STRANGER),
        ("Put the hammer down or I'll shoot.", UtteranceForm.THREAT, Standing.STRANGER),
        ("Open the door.", UtteranceForm.THREAT, Standing.STRANGER),   # imperative with a weapon in hand
    ]


# --------------------------------------------------------------------------- WILL-C cost presence
def test_an_addressed_mind_always_sees_what_it_would_cost(scenario):
    w = scenario("request_firewall")
    t = now(w)
    say(w, "pc", "Put the hammer down.", ["mara"], t, volume="normal")
    p = packet_for(w, "mara", t + 500)
    assert p.commitments.current_task == "boarding up the window (5 of 12 done)"
    assert p.stakes.dependents == ["Eli (near you)"], "she can see him asleep on the mattress"
    assert p.stakes.would_lose == ["Nothing you can name."]
    assert p.resources == ["You have: a claw hammer (in your right hand), a .38 revolver (holstered)."]


def _awake_eli(scenario):
    w = scenario("request_firewall")
    with w.store.transaction() as tx:
        bodies.wake(tx, w.id("eli"), now(w), None, 0)
    return w


def test_the_fill_lines_when_there_is_nothing(scenario):
    """Eli (awake now) carries nothing and is doing nothing: silence while nobody talks to him,
    explicit 'nothing' lines the moment someone does (WILL-C)."""
    w = _awake_eli(scenario)
    t = now(w)
    p0 = packet_for(w, "eli", t)
    assert p0.commitments.current_task is None and p0.resources == [] and p0.stakes.would_lose == []
    w = _awake_eli(scenario)
    say(w, "pc", "Eli, come here.", ["eli"], t + 1000, volume="normal")
    p = packet_for(w, "eli", t + 1500)
    assert any(u.addressed_to_me for u in p.utterances)
    assert p.commitments.current_task == "You are not in the middle of anything."
    assert p.resources == ["You carry nothing."] and p.stakes.would_lose == ["Nothing you can name."]


# --------------------------------------------------------------------------- the fields, in words
def test_identity_time_and_place(scenario, canon):
    w = scenario("metal_fence")
    at = crash_and_call(w)
    p = packet_for(w, "june", at)
    d = canon.get("core:actor/june_okafor")
    assert p.identity_text == f"You are {d.identity.name}, {d.identity.age}. {d.identity.one_line}"
    assert p.world_time_text == "23:14, day 18 since the Fall (night)"
    assert p.position_text == "at the shelves in the stockroom"
    assert p.voice_exemplars == [d.voice.exemplars.low_stakes, d.voice.exemplars.under_pressure, d.voice.exemplars.at_the_limit]
    assert p.writers_notes == d.writers_notes
    assert p.motive_lines[0] == f"What you want most: {d.motive.motive}"
    assert p.moral_lines[1] == "You won't: " + "; ".join(d.motive.moral_line.wont) + "."
    assert p.decision_lines[0] == "What comes first, in order: " + "; ".join(d.decision_stack.layers) + "."
    assert p.active_traits == [f"{t.tag.replace('_', ' ')}: {t.manifests}" for t in d.traits]


def test_capability_lines(scenario, canon):
    w = scenario("metal_fence")
    p = packet_for(w, "june", now(w))
    d = canon.get("core:actor/june_okafor")
    words = {1: "trained", 2: "skilled", 3: "expert"}
    want = [f"{s.domain.value.capitalize()}: {words[s.rank]}." for s in d.capability.skills]
    if d.capability.tags:
        want.append("You are good at: " + ", ".join(t.replace("_", " ") for t in d.capability.tags) + ".")
    assert p.capability_lines == want + ["Untrained in everything else."]


def test_body_lines(scenario):
    w = scenario("metal_fence")
    t = now(w)
    assert packet_for(w, "june", t).body_lines == ["Unhurt."]
    assert packet_for(w, "mara", t).body_lines == ["You are tired.", "Everything is harder than it should be."], "fatigue 3"
    with w.store.transaction() as tx:
        cause = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=t, turn_index=0, payload={"why": "test"}))
        bodies.apply_harm(tx, w.id("june"), WoundSpec("arm_l", "stab", "severe"), t, cause.event_id, 0, Rng(5))
    lines = packet_for(w, "june", t + 1000).body_lines
    assert lines[0] == "A deep stab wound to your left arm, bleeding."
    assert lines[1] in ("It hurts.", "The pain is bad.", "The pain is almost more than you can take.")


def test_relationships_and_entities(scenario):
    w = scenario("metal_fence")
    at = crash_and_call(w)
    j = packet_for(w, "june", at)
    ent = {j.handles[e.handle]: e for e in j.entities}
    rel = {j.handles[r.handle]: r.text for r in j.relationships}
    assert ent[w.id("mara")].description == "Mara" and ent[w.id("mara")].relation_summary == "your friend"
    assert ent[w.id("pc")].relation_summary is None, "an acquaintance is not a named relation"
    assert rel[w.id("mara")] == "You trust them; you care about them."
    assert rel[w.id("pc")] == "You trust them."
    m = packet_for(w, "mara", at)
    ment = {m.handles[e.handle]: e for e in m.entities}
    assert ment[w.id("eli")].relation_summary == "your child"
    assert {m.handles[r.handle]: r.text for r in m.relationships}[w.id("eli")] == "You trust them; you love them."
    a = packet_for(w, "alice", at)
    assert {a.handles[r.handle]: r.text for r in a.relationships}[w.id("pc")] == "No strong feelings."


def test_beliefs_say_where_they_came_from(scenario):
    w = scenario("metal_fence")
    t = now(w)
    (b,) = packet_for(w, "mara", t).beliefs
    assert (b.text, b.provenance_text, b.age_text) == ("Nita walks the alley at eleven; it's clear.", "Nita told you", "just now")
    later = packet_for(w, "mara", t + 2 * 3_600_000 + 5)
    assert later.beliefs[0].age_text == "2 hours ago"
    nb = packet_for(w, "nita", t).beliefs
    assert [x.provenance_text for x in nb] == ["you saw it", "you saw it"]


def test_commitments_and_standing_orders(scenario):
    w = scenario("metal_fence")
    t = now(w)
    assert packet_for(w, "june", t).commitments.current_task == "counting cans (41 of 60 done)"
    m = packet_for(w, "mara", t)
    assert m.commitments.current_task is None
    assert m.commitments.standing_orders == ["On loud noise: find the source and cover it."]
    assert m.stakes.dependents == ["Eli (not with you)"], "he is asleep in the office, out of her sight"
    assert m.resources == ["You have: a .38 revolver (holstered), 11 .38 rounds."]


def test_uncertainty_names_what_was_missed(scenario):
    """Nita hears June's call from the storeroom doorway only partly (P3)."""
    w = scenario("metal_fence")
    t = now(w)
    with w.store.transaction() as tx:
        tx.commit_event(space.move_event(tx, w.id("june"), w.id("storeroom"), w.id("doorway"), 7.5, 0.5, t + 800, None, 0))
    say(w, "june", "What was that?", [], t + 900)
    p = packet_for(w, "nita", t + 1500)
    partial = [x for x in [*p.perceived_now, *p.utterances] if x.fidelity in (Fidelity.PARTIAL, Fidelity.TONE_ONLY)]
    assert partial
    assert p.uncertainty == [f"You did not catch all of {x.handle}." for x in sorted(partial, key=lambda x: int(x.handle[1:]))]
    (u,) = p.utterances
    assert u.speaker_handle is None and u.standing == Standing.STRANGER, "an unplaced voice has no standing"


# --------------------------------------------------------------------------- SKULL-06 no ids
def test_no_internal_id_reaches_the_prompt(scenario):
    for name, who in (("metal_fence", ("june", "mara", "pc", "nita", "eli")), ("request_firewall", ("mara", "ray")),
                      ("empty_gun", ("reggie",)), ("two_skills", ("twin_a",))):
        w = scenario(name)
        at = crash_and_call(w) if name == "metal_fence" else now(w)
        for local in who:
            p = packet_for(w, local, at)
            text = rendered(p)
            assert not ID_RE.search(text), (name, local, ID_RE.search(text).group(0))
            assert p.handles and all(k[0] in "PSAEL" for k in p.handles)


# --------------------------------------------------------------------------- SKULL-09 budget
def _budget_world(scenario, n):
    return scenario("metal_fence", rules=RulesConfig(packet=PacketRules(token_budget={"hot": n, "warm": n, "reaction": n})))


def test_the_budget_drops_the_weakest_belief_first(scenario):
    w = scenario("metal_fence")
    full = packet_for(w, "nita", now(w))
    assert len(full.beliefs) == 2
    size = estimate_tokens(rendered(full))
    w2 = _budget_world(scenario, size - 1)
    cut = packet_for(w2, "nita", now(w2))
    assert [b.text for b in cut.beliefs] == [full.beliefs[0].text]
    assert estimate_tokens(rendered(cut)) <= size - 1
    assert cut.relationships == full.relationships and cut.affordances == full.affordances


def test_the_budget_never_drops_the_protected_fields(scenario):
    w = scenario("metal_fence")
    full = packet_for(w, "nita", now(w))
    w2 = _budget_world(scenario, 10)
    p = packet_for(w2, "nita", now(w2))
    assert p.beliefs == [] and p.memories == [] and p.uncertainty == []
    present = {p.handles[x.source_handle] for x in p.perceived_now if x.source_handle}
    assert all(p.handles[r.handle] in present for r in p.relationships), "only people in the scene keep their line"
    for f in ("identity_text", "voice_capsule", "voice_exemplars", "body_lines", "capability_lines", "position_text",
              "perceived_now", "utterances", "entities", "affordances", "commitments", "stakes", "resources"):
        assert getattr(p, f) == getattr(full, f), f


def test_reaction_packets_use_the_reaction_budget(scenario):
    w = scenario("metal_fence", rules=RulesConfig(packet=PacketRules(token_budget={"hot": 99_999, "warm": 99_999, "reaction": 10})))
    t = now(w)
    assert len(packet_for(w, "nita", t).beliefs) == 2
    assert packet_for(w, "nita", t, reaction=True).beliefs == []


# --------------------------------------------------------------------------- refusals of construction
def test_cold_actors_and_empty_menus_get_no_packet(scenario):
    w = scenario("metal_fence")
    t = now(w)
    with w.store.transaction() as tx:
        aff = enumerate_affordances(tx, w.id("june"), w.canon.all("affordance"), t, 0)
        with pytest.raises(ValueError):
            build_packet(tx, w.id("june"), LOD.COLD, aff, 0, t)
        with pytest.raises(ValueError):
            build_packet(tx, w.id("june"), LOD.HOT, AffordanceSet(actor_id=w.id("june")), 0, t)


def test_building_a_packet_writes_nothing(scenario):
    w = scenario("metal_fence")
    t = now(w)
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id("june"), t, 0)
        aff = enumerate_affordances(tx, w.id("june"), w.canon.all("affordance"), t, 0)
    n = w.store.query_one("SELECT COUNT(*) FROM events")[0]
    with w.store.transaction() as tx:
        build_packet(tx, w.id("june"), LOD.WARM, aff, 0, t)
    assert w.store.query_one("SELECT COUNT(*) FROM events")[0] == n


def test_a_room_described_twice_is_shown_once(scenario):
    """Two compiles in one turn (two waves): the packet shows only the latest standing view."""
    w = scenario("metal_fence")
    t = now(w)
    first = packet_for(w, "pc", t)
    second = packet_for(w, "pc", t + 5_000)
    assert len(second.perceived_now) == len(first.perceived_now)
    assert all(x.seconds_ago == 0 for x in second.perceived_now), "the latest look, not the earlier one"
