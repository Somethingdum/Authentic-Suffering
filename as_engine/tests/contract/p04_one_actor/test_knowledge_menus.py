"""A menu built from what the person knows (P4, Actor v2). Rules AFF-11, the duty gate (posts and
known laws are costs, fidelity C05 / Actor Spec AC06, AC07) and the 'owned' tag read from belief
(mind/affordance.py).

Two worlds that differ only in something a person has not seen or been told offer that person the
same options, word for word: a locked door is still a door to try, an owner on record is not an
owner they know of, a law nobody told them about is not a law to them. What they do know shows up
as a cost next to the option, never as a missing option; only their own immutable lines and their
body take options away.

The world here is a small market yard (a dict scenario, like p05's pantry): Dale Pruitt, a
stranger, at the stall; June Okafor, one of the locals, at the well a metre away; a jerky pack
on the stall; a shed door; the Crossing settlement's laws.
"""

from __future__ import annotations

import copy

import pytest

from as_engine.contracts.common import LOD, CallClass
from as_engine.contracts.events import Event, EventType, WriteOp, WriteRecord
from as_engine.kernel.rng import Rng
from as_engine.mind import perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.mind.packet import build_packet
from as_engine.physical import bodies
from as_engine.prompts.render import render

pytestmark = pytest.mark.phase(4)

CURFEW = "core:law/nightfall_curfew"
SHIELD = "core:law/market_shield_peace"
THEFT = "core:law/theft_law"
QUIET = "knowing_laws:law/quiet_well"
SHIELD_VISITORS = "Striking or drawing on anyone inside the shield brings the Warden's people within minutes."
SHIELD_MEMBERS = "A member who draws inside the shield without the Warden's word answers to the Warden, not to the victim."
CURFEW_MEMBERS = "Caught moving after curfew without a watch order draws challenge from the nearest patrol."
THEFT_VISITORS = "A visitor caught taking owned property is escorted out and is unlikely to be let back in."
POST = "It means leaving your post at the well."
NERVE = "It means going against the people in charge."
QUIET_WORDS = "Nobody runs near the well here; running feet carry, and the dead come to the sound."

CROSSING = {
    "schema": "as.scenario.v1", "name": "crossing", "seed": 31, "start": {"day": 400, "time": "12:00"},
    "rules": {"packet": {"max_affordances": 60}},          # every survivor on the menu: nothing hides behind the cap
    "places": [
        {"id": "yard", "name": "Market yard", "kind": "outdoor", "indoor": False, "material": "open_air",
         "width_m": 30, "depth_m": 20, "light": 3,
         "anchors": [{"id": "stall", "name": "stall", "x": 10, "y": 10}, {"id": "well", "name": "well", "x": 11, "y": 10},
                     {"id": "gate", "name": "gate", "x": 28, "y": 10},
                     {"id": "shed_out", "name": "shed door", "kind": "door_side", "x": 12, "y": 19.5}]},
        {"id": "shed", "name": "Tool shed", "width_m": 4, "depth_m": 3,
         "anchors": [{"id": "shed_in", "name": "shed door", "kind": "door_side", "x": 2, "y": 0.3}]},
    ],
    "portals": [{"id": "shed_door", "a": "yard", "b": "shed", "anchor_a": "shed_out", "anchor_b": "shed_in",
                 "kind": "door", "name": "shed door", "w": 90, "h": 200}],
    "bodies": [
        {"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "yard", "anchor": "gate"},
        {"id": "dale", "dossier": "core:actor/dale_pruitt", "place": "yard", "anchor": "stall"},
        {"id": "june", "dossier": "core:actor/june_okafor", "place": "yard", "anchor": "well"},
    ],
    "items": [{"item": "core:item/jerky_pack", "place": "yard", "anchor": "stall", "label": "jerky"}],
    "groups": [{"id": "locals", "name": "Crossing folk", "members": [{"actor": "june", "role": "member"}]}],
    "settlements": [{"id": "crossing", "name": "Crossing", "place": "yard", "group": "locals"}],
}


def told_law(holder, law, text="Nobody draws a weapon or lays a hand on anyone inside the market."):
    """What someone was told about a law of the place: the only way a non-member knows it."""
    return {"holder": holder, "subject_type": "place", "subject": "yard", "predicate": "law", "value": law,
            "text": text, "confidence": 3, "provenance": "told_by:june"}


def owner_belief(holder, owner, believed=True):
    return {"holder": holder, "subject_type": "object", "subject": "jerky", "predicate": "owner", "value": owner,
            "text": "The jerky on the stall is not free for the taking.", "confidence": 2, "provenance": "told_by:june",
            "believed": believed}


@pytest.fixture
def crossing(fixture_packs, core_pack_dir):
    """crossing(change=None) -> a loaded copy of CROSSING after ``change(spec)`` edited it."""
    from as_engine.testing.scenario import load_scenario

    worlds = []

    def _load(change=None):
        spec = copy.deepcopy(CROSSING)
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


def look(w, local):
    """The standing view, the options and the packet at the world's now: (AffordanceSet, prompt)."""
    t = now(w)
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id(local), t, 0)
        aff = enumerate_affordances(tx, w.id(local), w.canon.all("affordance"), t, 0)
        p = build_packet(tx, w.id(local), LOD.HOT, aff, 0, t)
    msgs = render(CallClass.ACTOR_COGNITION, p=p)
    return aff, msgs[0].content + "\n" + msgs[1].content


def packet_of(w, local):
    t = now(w)
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id(local), t, 0)
        aff = enumerate_affordances(tx, w.id(local), w.canon.all("affordance"), t, 0)
        return build_packet(tx, w.id(local), LOD.HOT, aff, 0, t)


def menu(w, aff):
    """Everything an option says, with ids as fixture-local names (two loads mint the same way,
    but a variant may mint one id more)."""
    def loc(x):
        return w.local(x) if x else None
    return [(o.def_id, loc(o.target_id), loc(o.destination_id), loc(o.item_id), o.label, o.ui_label, o.cost_note,
             o.risk_note, tuple(o.tags), round(o.est_duration_s, 6)) for o in aff.options]


def notes(aff, def_id, target=None, w=None):
    return {o.cost_note for o in aff.options if o.def_id == def_id and (target is None or o.target_id == w.id(target))}


# --------------------------------------------------------------------------- AFF-11 paired worlds
def _locked(spec):
    spec["portals"][0]["locked"] = True


def _laws_nobody_told_him(spec):
    spec["settlements"][0]["laws"] = [CURFEW, SHIELD, THEFT]


def _knife_in_her_pack(spec):
    spec["bodies"][2]["inventory"] = [{"item": "core:item/kitchen_knife", "slot": "pack", "label": "knife"}]


HIDDEN = {
    "a locked door": (_locked, lambda w: w.store.query_one(
        "SELECT is_locked FROM portals WHERE portal_id = ?", (w.id("shed_door"),))[0] == 1),
    "laws he was never told": (_laws_nobody_told_him, lambda w: w.store.query_one(
        "SELECT COUNT(*) FROM laws_active")[0] == 3),
    "a knife in someone's pack": (_knife_in_her_pack, lambda w: w.store.query_one(
        "SELECT COUNT(*) FROM items WHERE holder_body = ? AND holder_slot = 'pack'", (w.id("june"),))[0] == 1),
}


@pytest.mark.parametrize("what", sorted(HIDDEN))
def test_aff_11_what_he_cannot_know_changes_nothing_he_is_offered(crossing, what):
    """AFF-11: the same options in the same order with the same words, and the same prompt."""
    change, differs = HIDDEN[what]
    plain, hidden = crossing(), crossing(change)
    assert differs(hidden) and not differs(plain), "the two worlds really differ"
    (a1, p1), (a2, p2) = look(plain, "dale"), look(hidden, "dale")
    assert menu(plain, a1) == menu(hidden, a2), what
    assert p1 == p2, what


def test_aff_11_an_owner_on_record_is_not_an_owner_he_knows(crossing):
    """props.owner is a record Dale never learned: no 'steal' on the jerky, and nothing else moves."""
    plain = crossing()
    june = plain.id("june")

    def owned(spec):
        spec["items"][0]["props"] = {"owner": june}
    hidden = crossing(owned)
    assert '"owner"' in hidden.store.query_one("SELECT props FROM items WHERE item_id = ?", (hidden.id("jerky"),))[0]
    (a1, p1), (a2, p2) = look(plain, "dale"), look(hidden, "dale")
    assert menu(plain, a1) == menu(hidden, a2) and p1 == p2
    (pick,) = [o for o in a2.options if o.def_id == "pick_up_item"]
    assert "steal" not in pick.tags


def test_aff_11_an_infection_nobody_can_see_changes_nothing(crossing):
    """June was bitten an hour ago, in this world only; nothing shows yet (the wet strain's
    incubation has no signs), so Dale is offered exactly what he is offered in the world where
    she was not."""
    plain, hidden = crossing(), crossing()
    t = now(hidden)
    with hidden.store.transaction() as tx:
        ev = bodies.expose(tx, Rng(1), hidden.id("june"), "wet", "bite", t, None, 0)   # seed 1 infects (p 0.9)
    assert ev is not None and ev.payload["infected"] is True
    assert hidden.store.query_one("SELECT COUNT(*) FROM infections WHERE body_id = ?", (hidden.id("june"),))[0] == 1
    (a1, p1), (a2, p2) = look(plain, "dale"), look(hidden, "dale")
    assert menu(plain, a1) == menu(hidden, a2) and p1 == p2


def test_a_locked_door_is_still_offered_and_fails_when_tried(crossing):
    """AFF-11: the lock is not seen, so opening the door is on the menu either way (the attempt is
    what finds the lock); the standing view never says 'locked'."""
    w = crossing(_locked)
    aff, prompt = look(w, "dale")
    assert [o.target_id for o in aff.options if o.def_id == "open_portal"] == [w.id("shed_door")]
    assert "locked" not in prompt.lower()


def _cellar(pipe, light=0):
    """A cellar: Alice Tran (her line: never attack the unarmed) and Carl a metre away, known to her
    by name. At light 0 she sees a figure, at 1 'a man' (no hands to see, VIS-03), at 3 Carl."""
    carl = {"id": "carl", "stub": {"name": "Carl Ames", "age": 44, "sex": "male"}, "place": "cellar", "x": 3, "y": 2}
    if pipe:
        carl["inventory"] = [{"item": "core:item/steel_pipe", "slot": "hand_r"}]
    return {
        "schema": "as.scenario.v1", "name": "cellar", "seed": 5, "start": {"day": 400, "time": "02:00"},
        "places": [{"id": "cellar", "name": "Cellar", "material": "concrete", "light": light, "width_m": 6, "depth_m": 4},
                   {"id": "stairs", "name": "Stairwell", "light": 1, "width_m": 2, "depth_m": 4}],
        "bodies": [{"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "stairs", "x": 1, "y": 2},
                   {"id": "alice", "dossier": "core:actor/alice_tran", "place": "cellar", "x": 2, "y": 2}, carl],
        "knows": [{"holder": "alice", "subject": "carl", "name": "Carl"}],
    }


def _speaks(w):
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", actor_id=w.id("carl"), at=now(w),
                              turn_index=0, payload={"words": "It's me. It's Carl.", "volume": "normal",
                                                     "to": [w.id("alice")], "source_db": 60}))


@pytest.mark.parametrize("light", [0, 1])
def test_what_a_hand_holds_unseen_is_not_known(fixture_packs, core_pack_dir, light):
    """AFF-11 and attack_unarmed: a weapon in a hand counts only when it is seen clearly. In the dark
    (a figure and a voice) or by a poor light ('A man stands.'), Carl with a pipe and Carl without one
    give Alice the same menu, and none of it raises a hand to him — she will not risk striking
    someone who may be unarmed."""
    from as_engine.testing.scenario import load_scenario

    looks = []
    for pipe in (True, False):
        w = load_scenario(_cellar(pipe, light), packs_root=fixture_packs, core_pack_dir=core_pack_dir)
        try:
            _speaks(w)
            aff, prompt = look(w, "alice")
            carl = w.id("carl")
            assert any(r.target_id == carl and r.gate == "moral" and "attack_unarmed" in r.detail for r in aff.rejected)
            assert not [o for o in aff.options if "attack" in o.tags and o.target_id == carl]
            assert "pipe" not in prompt
            looks.append((menu(w, aff), prompt))
        finally:
            w.store.close()
    assert looks[0] == looks[1]


def test_a_weapon_seen_clearly_is_known(fixture_packs, core_pack_dir):
    """In good light the pipe is in plain view: striking an armed man is not her line."""
    from as_engine.testing.scenario import load_scenario

    for pipe in (True, False):
        w = load_scenario(_cellar(pipe, 3), packs_root=fixture_packs, core_pack_dir=core_pack_dir)
        try:
            aff, _ = look(w, "alice")
            hands_on = [o for o in aff.options if "attack" in o.tags and o.target_id == w.id("carl")]
            assert bool(hands_on) is pipe, pipe
        finally:
            w.store.close()


# --------------------------------------------------------------------------- the duty gate: costs, never walls
def test_a_law_he_was_told_is_a_cost_not_a_wall(crossing):
    """Told the market's peace, Dale still sees every way to lay hands on June; each carries what
    it would cost a visitor. A 'forbid' law removes nothing (C05)."""
    untold = crossing(lambda s: s["settlements"][0].update(laws=[SHIELD]))

    def told(spec):
        spec["settlements"][0]["laws"] = [SHIELD]
        spec["beliefs"] = [told_law("dale", SHIELD)]
    w = crossing(told)
    before, _ = look(untold, "dale")
    after, prompt = look(w, "dale")
    hands_on = [o for o in after.options if "attack" in o.tags and o.target_id == w.id("june")]
    assert {o.def_id for o in hands_on} >= {"punch", "shove", "grapple"}
    assert all(o.cost_note == SHIELD_VISITORS for o in hands_on)
    assert [(o.def_id, o.target_id) for o in after.options] == [(o.def_id, o.target_id) for o in before.options], \
        "knowing the law adds a cost; it takes nothing away"
    assert not any(r.gate == "duty" for r in after.rejected)
    assert all(o.cost_note is None for o in before.options if "attack" in o.tags)
    assert f"({SHIELD_VISITORS})" in prompt
    assert notes(after, "wait_here") == {None} and notes(after, "move_to_anchor") == {None}, "only what the law is about"


def test_a_member_knows_the_laws_of_home(crossing):
    """June belongs to the settlement's group: she knows its laws untold, under the members' terms."""
    w = crossing(lambda s: s["settlements"][0].update(laws=[SHIELD, CURFEW]))
    aff, _ = look(w, "june")
    assert notes(aff, "punch", "dale", w) == {SHIELD_MEMBERS}
    assert notes(aff, "move_to_anchor") == {CURFEW_MEMBERS}
    left = crossing(lambda s: s["settlements"][0].update(laws=[SHIELD]))
    june, group = left.id("june"), left.id("locals")
    with left.store.transaction() as tx:     # she walked out (world.worldmove OPS-06 writes this)
        tx.commit_event(Event(type=EventType.DEFECTION, writer="society.group", actor_id=june, at=now(left), turn_index=0,
                              payload={"actor_id": june, "group_id": group, "loop_id": None},
                              writes=[WriteRecord(op=WriteOp.UPDATE, table="group_members",
                                                  key={"group_id": group, "actor_id": june}, values={"status": "departed"})]))
    gone, _ = look(left, "june")
    assert notes(gone, "punch", "dale", left) == {None}, "no longer one of them, and nobody told her the rules as a visitor"


def test_every_cost_is_said_the_post_first_then_the_laws_then_nerve(crossing):
    """June keeps the well (duty anchor), lives under the curfew and the fixture pack's quiet-well
    rule (an effect with no note of its own: the locals' words), and has little nerve left (Resolve
    2): slipping away past the gate carries all of it, in that order."""
    def keeper(spec):
        spec["packs"] = ["knowing_laws"]
        spec["settlements"][0]["laws"] = [QUIET, CURFEW]
        spec["bodies"][2].update(duty_anchor="well", resolve=2)
    w = crossing(keeper)
    aff, prompt = look(w, "june")
    assert notes(aff, "slip_off") >= {f"{POST} {CURFEW_MEMBERS} {NERVE}"}
    (run,) = [o for o in aff.options if o.def_id == "run_to_anchor" and o.destination_id == w.id("gate")]
    assert run.cost_note == f"{POST} {CURFEW_MEMBERS} {QUIET_WORDS}"
    (near,) = [o for o in aff.options if o.def_id == "move_to_anchor" and o.destination_id == w.id("stall")]
    assert near.cost_note == CURFEW_MEMBERS, "the stall is a metre from the well: no post left behind"
    assert QUIET_WORDS in prompt


# --------------------------------------------------------------------------- 'owned' is what he believes
@pytest.mark.parametrize("belief,steal", [
    (None, False),
    (owner_belief("dale", "june"), True),
    (owner_belief("dale", "dale"), False),
    (owner_belief("dale", "june", believed=False), False),
])
def test_owned_is_what_he_believes(crossing, belief, steal):
    """The 'owned' target kind — and so 'steal' — comes from a live, believed owner belief naming
    someone who is not him, his household or his group. Dale draws no line at stealing, so the
    option stays either way; what changes is what it is."""
    w = crossing((lambda s: s.update(beliefs=[belief])) if belief else None)
    aff, _ = look(w, "dale")
    (pick,) = [o for o in aff.options if o.def_id == "pick_up_item"]
    assert ("steal" in pick.tags) is steal


@pytest.mark.parametrize("owner,steal", [("pc", True), ("locals", False), ("okafors", False), ("june", False)])
def test_what_is_ours_is_not_stolen(crossing, owner, steal):
    """June believes the jerky is Owen's, her group's, her household's or her own: only Owen's
    makes taking it stealing. (A fixture belief cannot name a household or group by its local id —
    those are minted after the beliefs are written — so the first load tells us the real id.)"""
    def home(spec):
        spec["households"] = [{"id": "okafors", "members": [{"actor": "june", "role": "head"}]}]
        spec["bodies"][2]["anchor"] = "stall"
    real = crossing(home).id(owner)

    def hers(spec):
        home(spec)
        spec["beliefs"] = [owner_belief("june", real)]
    w = crossing(hers)
    assert w.id(owner) == real
    aff, _ = look(w, "june")
    (pick,) = [o for o in aff.options if o.def_id == "pick_up_item"]
    assert ("steal" in pick.tags) is steal


def test_a_known_theft_law_prices_a_known_theft(crossing):
    def told(spec):
        spec["settlements"][0]["laws"] = [THEFT]
        spec["beliefs"] = [told_law("dale", THEFT, "Taking what belongs to a household here is theft."),
                           owner_belief("dale", "june")]
    w = crossing(told)
    aff, _ = look(w, "dale")
    (pick,) = [o for o in aff.options if o.def_id == "pick_up_item"]
    assert "steal" in pick.tags and pick.cost_note == THEFT_VISITORS
    unknown_owner = crossing(lambda s: (s["settlements"][0].update(laws=[THEFT]),
                                        s.update(beliefs=[told_law("dale", THEFT)])))
    a2, _ = look(unknown_owner, "dale")
    (pick2,) = [o for o in a2.options if o.def_id == "pick_up_item"]
    assert pick2.cost_note is None, "the law is about taking what is someone's; he does not know it is"


def test_his_own_line_is_the_only_thing_that_takes_an_option_away(crossing):
    """A stub settler will not steal (wont_tags [steal]): once she believes the jerky is June's,
    the moral gate removes the option — her line, not the law."""
    def settler(spec):
        spec["bodies"].append({"id": "tam", "stub": {"name": "Tam Voss", "age": 30, "sex": "female"},
                               "place": "yard", "anchor": "stall"})
        spec["beliefs"] = [owner_belief("tam", "june")]
    w = crossing(settler)
    aff, _ = look(w, "tam")
    assert not [o for o in aff.options if o.def_id == "pick_up_item"]
    assert any(r.def_id == "pick_up_item" and r.gate == "moral" and "steal" in r.detail for r in aff.rejected)


# --------------------------------------------------------------------------- AC14 who is where
def test_a_tie_never_seen_is_not_seen(crossing):
    """Actor Spec AC14: Dale's partner waits in the shed he has never looked into — no sighting,
    so 'not seen', however close the tie; June, a metre away in daylight, is 'here'."""
    def partner(spec):
        spec["bodies"].append({"id": "sal", "stub": {"name": "Sal Pruitt", "age": 40, "sex": "male"},
                               "place": "shed", "anchor": "shed_in"})
        spec["relationships"] = [{"from": "dale", "to": "sal", "kind": "partner", "trust": 3, "affection": 3}]
    w = crossing(partner)
    p = packet_of(w, "dale")
    where = {w.local(p.handles[e.handle]): e.whereabouts for e in p.entities}
    assert where["sal"] == "not seen" and where["june"] == "here"


def test_a_figure_that_knocks_something_over_is_heard_not_seen(fixture_packs, core_pack_dir):
    """AC14: in the black cellar Alice sees only a figure; the bucket it knocks over is Carl's noise
    to her (she can make out who made it) — so Carl is heard, not seen, not 'last seen'."""
    from as_engine.testing.scenario import load_scenario

    w = load_scenario(_cellar(False, 0), packs_root=fixture_packs, core_pack_dir=core_pack_dir)
    try:
        with w.store.transaction() as tx:
            tx.commit_event(Event(type=EventType.NOISE, writer="action.propagate", actor_id=w.id("carl"), at=now(w),
                                  turn_index=0, payload={"source_db": 65, "kind": "knock", "text": "a bucket going over",
                                                         "place_id": w.id("cellar")}))
        p = packet_of(w, "alice")
        heard = [x for x in p.perceived_now if x.channel.value == "auditory"]
        assert heard and p.handles[heard[0].source_handle] == w.id("carl")
        (carl,) = [e for e in p.entities if p.handles[e.handle] == w.id("carl")]
        assert carl.whereabouts == "heard, not seen"
    finally:
        w.store.close()
