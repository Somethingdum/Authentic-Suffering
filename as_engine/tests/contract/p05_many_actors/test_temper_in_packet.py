"""What a person knows of their own anger, and what they could do when it is them or you (P5, the
owner's H1). Rules TEMPER-08 (mind/packet.py; prompts/actor_cognition.user.j2), the humanity
paragraph of _actor_core.j2, and the physical and moral gates of shove_toward_dead and shoot_leg
(mind/affordance.py requires.infected_within_m; contracts/common.MoralTag.FEED_TO_DEAD).

A person's packet says how close they are to breaking and how they feel about each person in front
of them; a snap says it is happening. When the dead are right there, shoving someone into them is an
option like any other — unless it is past that person's own line.
"""

from __future__ import annotations

import copy

import pytest

from as_engine.contracts.common import LOD, CallClass
from as_engine.contracts.events import Event, EventType
from as_engine.mind import mind as mindmod, perception, temper
from as_engine.mind.affordance import enumerate_affordances
from as_engine.mind.packet import build_packet
from as_engine.prompts.render import PROMPT_DIR, render
from as_engine.testing.scenario import load_scenario

pytestmark = pytest.mark.phase(5)

YARD = {
    "schema": "as.scenario.v1", "name": "back_lot", "seed": 45, "start": {"day": 400, "time": "13:00"},
    "places": [{"id": "lot", "name": "Back lot", "kind": "outdoor", "indoor": False, "material": "open_air", "light": 3,
                "width_m": 40, "depth_m": 20}],
    "bodies": [
        {"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "lot", "x": 2, "y": 10},
        {"id": "mara", "dossier": "core:actor/mara_voss", "place": "lot", "x": 3, "y": 10},
        {"id": "june", "dossier": "core:actor/june_okafor", "place": "lot", "x": 4, "y": 10},
        {"id": "nita", "dossier": "core:actor/nita_reyes", "place": "lot", "x": 5, "y": 10,
         "inventory": [{"item": "core:item/revolver_38", "slot": "hand_r", "props": {"rounds": 6}}]},
        {"id": "dead", "infected": "ZOMBIE_ARCHETYPE_SHAMBLER01", "controller": "policy", "place": "lot", "x": 30, "y": 10},
    ],
}


@pytest.fixture
def lot(fixture_packs, core_pack_dir):
    worlds = []

    def _load(change=None):
        spec = copy.deepcopy(YARD)
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


def packet(w, local, at):
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id(local), at, 0)
        aff = enumerate_affordances(tx, w.id(local), w.canon.all("affordance"), at, 0)
        return aff, build_packet(tx, w.id(local), LOD.HOT, aff, 0, at)


def provoke(w, holder, toward, kind, n, at):
    with w.store.transaction() as tx:
        for k in range(n):
            temper.provoke(tx, w.id(holder), w.id(toward), kind, f"test:{k}", at, 0)


def strain(w, who, delta, at):
    from as_engine.mind import actor
    with w.store.transaction() as tx:
        c = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=at, turn_index=0, payload={"what": "test"}))
        actor.adjust_stress(tx, w.id(who), delta, c.event_id, at, 0)


def feeling(p, w, local):
    return next(e.feeling for e in p.entities if p.handles[e.handle] == w.id(local))


# --------------------------------------------------------------------------- TEMPER-08
def test_a_person_knows_how_close_they_are_to_breaking(lot):
    w = lot()
    t = now(w)
    _, calm = packet(w, "mara", t)
    assert not any("breaking" in ln or "end of your rope" in ln for ln in calm.body_lines)
    strain(w, "mara", 6, t)
    _, six = packet(w, "mara", t + 500)
    assert not any("breaking" in ln or "end of your rope" in ln for ln in six.body_lines), "6 is not yet close"
    strain(w, "mara", 1, t + 500)
    _, close = packet(w, "mara", t + 1000)
    assert "You are close to breaking." in close.body_lines
    strain(w, "mara", 2, t + 1000)
    _, done = packet(w, "mara", t + 2000)
    assert "You are at the end of your rope." in done.body_lines and "You are close to breaking." not in done.body_lines


def test_how_they_feel_about_each_person_in_front_of_them(lot):
    """Mara's breaking point is 6 (fuse 3): June at 3 heat gets under his skin, the player at 6 has
    her furious; Nita she holds a grudge against."""
    w = lot()
    t = now(w)
    provoke(w, "mara", "june", "ordered_about", 3, t)
    provoke(w, "mara", "pc", "insulted", 3, t)
    with w.store.transaction() as tx:
        mindmod.open_loop(tx, w.id("mara"), "grudge", "She keeps asking for a gun.", [w.id("nita")], 1, "test:g", t, 0)
    _, p = packet(w, "mara", t)
    assert feeling(p, w, "june") == "they are getting under your skin"
    assert feeling(p, w, "pc") == "you are furious with them"
    assert feeling(p, w, "nita") == "you hold a grudge against them"
    user = render(CallClass.ACTOR_COGNITION, p=p)[1].content
    june = next(e.handle for e in p.entities if p.handles[e.handle] == w.id("june"))
    [line] = [ln for ln in user.splitlines() if ln.startswith(f"- {june}:")]
    assert "; they are getting under your skin)" in line or "(they are getting under your skin)" in line


def test_a_snap_is_said_first(lot):
    w = lot()
    t = now(w)
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.INVOLUNTARY, writer="mind.temper", actor_id=w.id("mara"), at=t, turn_index=0,
                              payload={"actor_id": w.id("mara"), "kind": "outburst", "outlet": "words",
                                       "toward_id": w.id("june")}))
    _, p = packet(w, "mara", t)
    june = next(e.handle for e in p.entities if p.handles[e.handle] == w.id("june"))
    assert p.outburst == f"You snap. You are going to have it out with {june} — now, to their face."
    user = render(CallClass.ACTOR_COGNITION, p=p)[1].content
    assert user.index(p.outburst) < user.index("What reaches you")
    _, later = packet(w, "mara", t + 1000)
    assert later.outburst is None, "a snap belongs to its moment"
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.INVOLUNTARY, writer="mind.temper", actor_id=w.id("mara"), at=t + 2000,
                              turn_index=0, payload={"actor_id": w.id("mara"), "kind": "outburst", "outlet": "fists",
                                                     "toward_id": w.id("june")}))
    _, fists = packet(w, "mara", t + 2000)
    assert fists.outburst is None, "a fist is thrown, not said: only a snap in words asks her for words"


def test_a_person_not_a_planner():
    core = (PROMPT_DIR / "_actor_core.j2").read_text(encoding="utf-8")
    assert "You are a person, not a planner." in core
    assert "hold a grudge that is not fair" in core
    assert "Getting along is something you manage on a good day, not something you always do." in core


# --------------------------------------------------------------------------- when it is them or you
def offered(aff, w, def_id):
    """Who the person could do it to (the pool: every option that passed the gates)."""
    return sorted(w.local(o.target_id) for o in aff.pool if o.def_id == def_id)


def test_shoving_someone_to_the_dead_is_offered_only_with_the_dead_right_there(lot):
    w = lot()
    t = now(w)
    aff, _ = packet(w, "mara", t)
    assert offered(aff, w, "shove_toward_dead") == [], "the dead are 27 m off"
    with w.store.transaction() as tx:
        from as_engine.physical import space
        tx.commit_event(space.move_event(tx, w.id("dead"), w.id("lot"), None, 9.0, 10.0, t, None, 0))
    aff, p = packet(w, "mara", t + 1000)
    assert offered(aff, w, "shove_toward_dead") == ["june", "pc"], "6 m: she could shove whoever is in reach"
    shown = [o for o in aff.options if o.def_id == "shove_toward_dead"]
    assert shown, "with the dead that close it is on her mind, not buried (AFF-07: right after running)"
    assert any(o.label.startswith("Shove ") and o.label.endswith(" toward the dead") for o in p.affordances)


def test_a_person_s_own_line_takes_it_away(lot):
    """June will not feed anyone to the dead (wont_tags feed_to_dead, kill_human); Mara has no such line."""
    w = lot()
    t = now(w)
    with w.store.transaction() as tx:
        from as_engine.physical import space
        tx.commit_event(space.move_event(tx, w.id("dead"), w.id("lot"), None, 9.0, 10.0, t, None, 0))
    aff, _ = packet(w, "june", t)
    assert offered(aff, w, "shove_toward_dead") == []
    assert any(r.def_id == "shove_toward_dead" and r.gate == "moral" for r in aff.rejected)


def test_a_gun_in_hand_can_be_aimed_at_a_leg(lot):
    w = lot()
    aff, _ = packet(w, "nita", now(w))
    assert set(offered(aff, w, "shoot_leg")) >= {"pc", "mara", "june"}, "nothing in Nita's line stops her"
