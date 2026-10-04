"""Everyone knows (D-130). Rules LORE-02 (mind/actor.py seed_lore, create; table lore_held), LORE-03
(mind/retrieval.py lore_lines), mind/packet.py (the packet's lore lines, outside the budget; the ambient
packet's), contracts.content.LoreEntry about / when.

The owner: "The lore needs merged into ever crevice of this." The core pack's lore says what everyone says
("If it's not the head, it's not dead."), what each generation says (a child born after the Fall: "Walkers are
sleepwalking people.") and what a faction says among its own — and nobody held any of it: no loader, no
worldgen, no new person was ever given it. Now everyone holds what their world, their generation and their
people say, and it comes to mind when it bears on the moment — said aloud, seen, or felt — never as a list of
thirty things that would crowd out what this person actually knows.
"""

from __future__ import annotations

import copy

import pytest

from as_engine.contracts.events import Event, EventType
from as_engine.mind import perception
from as_engine.mind.actor import create as actor_create, fused
from as_engine.mind.packet import ambient_packet
from as_engine.mind.retrieval import lore_lines, retrieve
from as_engine.physical import bodies
from as_engine.testing.scenario import load_scenario

pytestmark = pytest.mark.phase(6)

YARD = {
    "schema": "as.scenario.v1", "name": "remnant_yard", "seed": 17, "start": {"day": 2900, "time": "12:00"},
    "places": [{"id": "yard", "name": "Market yard", "kind": "outdoor", "indoor": False, "material": "open_air",
                "width_m": 30, "depth_m": 20, "light": 3,
                "anchors": [{"id": "stall", "name": "stall", "x": 10, "y": 10}, {"id": "gate", "name": "gate", "x": 14, "y": 10}]}],
    "bodies": [
        {"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "yard", "anchor": "gate"},
        {"id": "vito", "stub": {"name": "Vito Russo", "age": 44, "sex": "male"}, "place": "yard", "anchor": "stall"},
        {"id": "mask", "stub": {"name": "Unknown", "age": 30, "sex": "male"}, "place": "yard", "x": 12, "y": 12},
        {"id": "kid", "stub": {"name": "Lu Wen", "age": 7, "sex": "female"}, "place": "yard", "x": 11, "y": 9},
    ],
    "groups": [
        {"id": "remnants", "kind": "faction", "name": "The Remnants", "content_ref": "core:faction/mafia_remnants",
         "members": [{"actor": "vito", "role": "collector", "standing": 1}]},
        {"id": "ghosts", "kind": "faction", "name": "The Ghosts", "content_ref": "core:faction/ghosts",
         "members": [{"actor": "mask", "role": "ghost", "standing": 1}]},
    ],
}


@pytest.fixture
def yard(fixture_packs, core_pack_dir):
    worlds = []

    def _load():
        w = load_scenario(copy.deepcopy(YARD), packs_root=fixture_packs, core_pack_dir=core_pack_dir)
        worlds.append(w)
        return w
    yield _load
    for w in worlds:
        w.store.close()


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def held(w, who):
    return {(r[0], r[1]): r[2] for r in w.store.query("SELECT lore_ref, belief, provenance FROM lore_held WHERE holder_id = ?", (who,))}


def expected(w, who):
    with w.store.transaction() as tx:
        cohort = fused(tx, who).identity.cohort
        cohort = getattr(cohort, "value", cohort)
    groups = {r[0] for r in w.store.query("SELECT g.content_ref FROM group_members m JOIN groups g ON g.group_id = m.group_id "
                                          "WHERE m.actor_id = ?", (who,))}
    out = {}
    for ref in w.canon.refs("lore"):
        for i, b in enumerate(w.canon.get(ref).beliefs):
            if b.held_by == "common":
                out[(ref, i)] = "common"
            elif b.held_by == f"cohort:{cohort}":
                out[(ref, i)] = "childhood" if cohort == "post_fall_born" else "common"
            elif b.held_by in groups:
                out[(ref, i)] = "group"
    return out


def say(w, who, words, to_whom, at):
    with w.store.transaction() as tx:
        ev = tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", actor_id=w.id(who), at=at, turn_index=0,
                                   payload={"words": words, "volume": "normal", "to": ["everyone"], "source_db": 60, "armed": False}))
        for x in to_whom:
            perception.compile_aftermath(tx, w.id(x), [ev], at + 500, 0)


def test_each_holds_what_their_world_their_generation_and_their_people_say(yard):
    w = yard()
    for who in ("pc", "vito", "mask", "kid"):
        assert held(w, w.id(who)) == expected(w, w.id(who)), who
    assert held(w, w.id("vito"))[("core:lore/mafia_remnants_lore", 3)] == "group", "the Remnants' own word is Vito's"
    assert ("core:lore/mafia_remnants_lore", 3) not in held(w, w.id("pc"))
    assert not w.store.query("SELECT 1 FROM propositions WHERE subject_type = 'lore'"), "never a belief or a percept"
    loaded = w.store.query("SELECT COUNT(*) FROM events WHERE type = 'MATERIALIZE' AND json_extract(payload, '$.source') = 'lore'")[0][0]
    assert loaded == 0, "the loader writes it inside each person's own MATERIALIZE: no event more"


def test_thirty_things_everyone_says_never_crowd_out_what_you_know(yard):
    w = yard()
    t = now(w)
    with w.store.transaction() as tx:
        R = retrieve(tx, w.id("vito"), 0, t, max_beliefs=12, max_memories=6, max_loops=8)
    assert R.beliefs == [] and R.lore == [], "nothing in the moment brings any of it to mind"
    say(w, "pc", "Is there a cure for a bite?", ["vito"], t)
    with w.store.transaction() as tx:
        R = retrieve(tx, w.id("vito"), 0, t + 1000, max_beliefs=12, max_memories=6, max_loops=8)
    assert R.beliefs == [] and len(R.lore) == 3, "it comes to mind as what people say, never as something he knows"


def test_said_aloud_it_comes_to_mind(yard):
    w = yard()
    t = now(w)
    say(w, "pc", "Is there a cure for a bite?", ["vito"], t)
    with w.store.transaction() as tx:
        got = [x["text"] for x in lore_lines(tx, w.id("vito"), 0, t + 1000, 3)]
    assert got[0] == "There's no cure. Anybody selling one is selling you a grave."
    assert "The Clean Clinics can't fix a bite. What they can do is tell you fast, and keep it from spreading." in got, \
        "and what his own people say about it"


def test_seen_it_comes_to_mind(yard):
    """Vito sees a Ghost standing in the yard: what everyone says about the Ghosts, and what the Remnants say."""
    w = yard()
    t = now(w)
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id("vito"), t, 0)
        got = [x["text"] for x in lore_lines(tx, w.id("vito"), 0, t, 3)]
    assert got == ["Ghosts don't talk. They say 'Keep moving' once, and you keep moving.",
                   "If you find a body with a smile cut into it, somebody crossed the Ghosts.",
                   "Ghost business goes to the Steward. Nobody else touches it."]


def test_the_packet_says_where_it_comes_from(yard):
    w = yard()
    t = now(w)
    say(w, "pc", "Ever hear the screaming at the end?", ["vito", "kid"], t)
    with w.store.transaction() as tx:
        vito = lore_lines(tx, w.id("vito"), 0, t + 1000, 3)
        kid = lore_lines(tx, w.id("kid"), 0, t + 1000, 3)
        amb = ambient_packet(tx, w.id("kid"), 0, t + 1000, doing="Wait here")
    assert {x["provenance"] for x in vito} <= {"common", "group"}
    if any(x["text"] == "Everybody screams at the end. That's what dying is." for x in kid):
        assert next(x for x in kid if x["text"].startswith("Everybody screams"))["provenance"] == "childhood"
    assert amb is not None and amb.knows and amb.knows[0] == kid[0]["text"]


def test_someone_new_knows_it_too(yard):
    """A person made mid-game (mind.actor.create) holds what everyone says and what their card says they know."""
    w = yard()
    t = now(w)
    d = w.canon.get("core:actor/mara_voss").model_dump(mode="json", by_alias=True)
    with w.store.transaction() as tx:
        b = bodies.create(tx, kind="human", sex="female", age_years=d["identity"]["age"], height_cm=170, mass_kg=64,
                          special=dict(d["capability"]["special"]), at=t, turn_index=0, origin="materialize", cause_event_id=None)
        actor_create(tx, b, d, "generated", t, 0)
    assert held(w, b) == expected(w, b)
    cues = sorted(c for r in w.store.query("SELECT cue_tags FROM lessons WHERE holder_id = ?", (b,)) for c in __import__("json").loads(r[0]))
    assert cues == sorted(w.canon.get("core:actor/mara_voss").knowledge.cues)


def test_a_scream_heard_brings_it_to_mind(yard):
    """No word said: the scream people make before they die (DOOM-04's NOISE) is the moment cue 'scream'."""
    w = yard()
    t = now(w)
    with w.store.transaction() as tx:
        pos = tx.query_one("SELECT place_id, x_m, y_m FROM positions WHERE body_id = ?", (w.id("kid"),))
        ev = tx.commit_event(Event(type=EventType.NOISE, writer="action.propagate", actor_id=w.id("kid"), at=t, turn_index=0,
                                   payload={"source_db": 95, "kind": "screaming", "text": "the scream people make before they die",
                                            "place_id": pos[0], "x_m": pos[1], "y_m": pos[2]}))
        perception.compile_aftermath(tx, w.id("vito"), [ev], t + 300, 0)
        got = [x["text"] for x in lore_lines(tx, w.id("vito"), 0, t + 500, 3)]
    assert "Since the Fall, people scream before they die. Nobody knows why." in got
    assert "Noise brings them. Always." in got, "a scream is a noise too: each thing once before any twice"
