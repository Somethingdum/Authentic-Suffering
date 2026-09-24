"""Effect handlers (P5). Rules EFF-01..08, INTENT-03 (action/effects.py).

Every action: ACTION_START at the wave time, the landing at start + duration (state changes through
the owning module, a NOISE when loud), then ACTION_COMPLETE — or ACTION_BLOCKED with a cause.
Intents are built straight from the core defs (helpers.make_intent): these tests exercise the
resolver, not the menu. Dice are scripted (helpers.ScriptedRng) wherever a band matters.
"""

from __future__ import annotations

import json
import math

import pytest

import helpers
from as_engine.action import effects
from as_engine.action.intent import barrier
from as_engine.action.resolve import resolve_wave
from as_engine.mind import perception
from as_engine.physical import bodies
from as_engine.physical.bodies import WoundSpec
from as_engine.contracts.events import Event, EventType

pytestmark = pytest.mark.phase(5)

HORIZON = 600_000


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def run(w, *intents, at=None, rng=None, horizon=HORIZON):
    t = now(w) if at is None else at
    with w.store.transaction() as tx:
        return resolve_wave(tx, rng or w.rng, barrier(tx, list(intents)), t, 0, horizon_ms=t + horizon)


def of(evs, type_, actor=None):
    return [e for e in evs if e.type == type_ and (actor is None or e.actor_id == actor)]


def one(evs, type_, actor=None):
    got = of(evs, type_, actor)
    assert len(got) == 1, [(e.type, e.payload) for e in evs]
    return got[0]


def pos(w, local):
    return dict(w.store.query_one("SELECT * FROM positions WHERE body_id = ?", (w.id(local),)))


def item(w, local):
    r = dict(w.store.query_one("SELECT * FROM items WHERE item_id = ?", (w.id(local),)))
    r["props"] = json.loads(r["props"])
    return r


# --------------------------------------------------------------------------- the shape of an action
def test_a_walk_starts_then_lands(scenario):
    w = scenario("metal_fence")
    t = now(w)
    i = helpers.make_intent(w, "june", "go_look", destination="back_door_in")
    evs = run(w, i)
    start = one(evs, "ACTION_START")
    assert start.at == t and start.writer == "action.resolve"
    assert start.payload == {"actor_id": w.id("june"), "def_id": "go_look", "verb": "move", "target_id": None,
                             "destination_id": w.id("back_door_in"), "item_id": None, "est_duration_s": i.bound.est_duration_s,
                             "visible": True, "seen": "goes to look toward {destination}", "continues_task": False,
                             "label": "go_look", "goal": "go_look"}
    land = effects.land_ms(t, i.bound.est_duration_s)
    assert land == t + math.ceil((1 + math.hypot(2, 2.5)) * 1000)
    mv = one(evs, "MOVE")
    assert (mv.at, mv.payload["to_anchor"], mv.cause_event_id) == (land, w.id("back_door_in"), start.event_id)
    nz = one(evs, "NOISE")
    assert (nz.at, nz.payload["source_db"], nz.payload["kind"], nz.payload["place_id"], nz.payload["x_m"], nz.payload["y_m"]) == \
        (land, 25, "move_to_anchor", w.id("storeroom"), 4, 4.5), "footsteps where she arrived"
    done = one(evs, "ACTION_COMPLETE")
    assert done.at == land and done.payload == {"actor_id": w.id("june"), "def_id": "go_look", "result": "done", "band": None,
                                                "visible": False}
    assert [e.type for e in evs] == ["ACTION_START", "MOVE", "NOISE", "ACTION_COMPLETE"]


def test_seen_phrases_cover_every_core_affordance(canon):
    ids = {d.id for d in canon.all("affordance")}
    assert ids <= set(effects.SEEN), sorted(ids - set(effects.SEEN))
    for d in canon.all("affordance"):
        assert d.effect in effects.EFFECT_IDS, d.id
    for eid in effects.EFFECT_IDS:
        assert eid in effects.EFFECTS, f"no handler registered for {eid}"


def test_condition_ended_actions_land_at_once(scenario):
    w = scenario("metal_fence")
    t = now(w)
    evs = run(w, helpers.make_intent(w, "pc", "observe_area"), helpers.make_intent(w, "nita", "wait_here"))
    for local in ("pc", "nita"):
        done = one(evs, "ACTION_COMPLETE", w.id(local))
        assert done.at == t and done.payload["result"] == "holding"
    assert not of(evs, "NOISE"), "watching and waiting make no sound"


# --------------------------------------------------------------------------- movement
def test_through_a_portal_to_the_far_side(scenario):
    w = scenario("metal_fence")
    evs = run(w, helpers.make_intent(w, "june", "move_through_portal", target="back_door", destination="alley"))
    mv = one(evs, "MOVE")
    assert (mv.payload["to_place"], mv.payload["to_anchor"]) == (w.id("alley"), w.id("back_door_out"))
    assert pos(w, "june")["place_id"] == w.id("alley")


def test_a_closed_portal_blocks_and_a_tight_one_refuses(scenario):
    w = scenario("metal_fence")
    evs = run(w, helpers.make_intent(w, "pc", "move_through_portal", target="office_door", destination="office"))
    assert one(evs, "ACTION_BLOCKED").payload["cause"] == "portal_closed"
    assert not of(evs, "MOVE") and not of(evs, "NOISE") and not of(evs, "ACTION_COMPLETE")


def test_climbing_the_fence(scenario):
    """Nita: A 7 (mod 4) + athletics 2 vs obstacle class 3 (180 cm). Band decides the outcome."""
    for draws, expect in (((1,), "over"), ((10,), "fell")):
        w = scenario("metal_fence")
        evs = run(w, helpers.make_intent(w, "nita", "climb_obstacle", target="rear_fence", destination="back_lot"),
                  rng=helpers.ScriptedRng(*draws))
        chk = one(evs, "CHECK_RESOLVED").payload
        assert chk["resistance"] == 3
        res = one(evs, "ACTION_COMPLETE").payload
        if expect == "over":
            assert chk["band"] in ("clean", "cost") and res["result"] == "done"
            assert pos(w, "nita")["anchor_id"] == w.id("fence_far")
        else:
            assert chk["band"] == "break" and res["result"] == "fell"
            (wd,) = [dict(r) for r in w.store.query("SELECT * FROM wounds WHERE body_id = ?", (w.id("nita"),))]
            assert (wd["anatomy"], wd["type"], wd["severity"]) == ("leg_l", "blunt", "minor"), "180 cm: a short fall"
            assert w.store.query_one("SELECT posture FROM bodies WHERE body_id = ?", (w.id("nita"),))[0] == "lying"
            assert pos(w, "nita")["place_id"] == w.id("alley")


# --------------------------------------------------------------------------- portals
def test_open_walks_to_the_door_first(scenario):
    w = scenario("metal_fence")
    evs = run(w, helpers.make_intent(w, "pc", "open_portal", target="office_door"))
    mv = one(evs, "MOVE")
    assert mv.payload["to_anchor"] == w.id("office_door_front")
    pc = one(evs, "PORTAL_CHANGE")
    assert pc.payload["changes"] == {"is_open": 1} and pc.at == mv.at
    assert one(evs, "NOISE").payload["source_db"] == 40
    assert w.store.query_one("SELECT is_open FROM portals WHERE portal_id = ?", (w.id("office_door"),))[0] == 1


def test_a_locked_door_is_a_result_not_a_block(scenario):
    w = scenario("metal_fence")
    evs = run(w, helpers.make_intent(w, "pc", "open_portal", target="front_door"))
    assert one(evs, "ACTION_COMPLETE").payload["result"] == "blocked_by_lock"
    assert not of(evs, "PORTAL_CHANGE")


def test_forcing_the_front_door(scenario):
    w = scenario("metal_fence")
    evs = run(w, helpers.make_intent(w, "pc", "force_portal", target="front_door"), rng=helpers.ScriptedRng(1))
    chk = one(evs, "CHECK_RESOLVED").payload
    assert chk["resistance"] == 2 + 2, "lock quality 2 + barricade 2"
    door = dict(w.store.query_one("SELECT * FROM portals WHERE portal_id = ?", (w.id("front_door"),)))
    if chk["band"] in ("clean", "cost"):
        assert (door["is_open"], door["is_locked"], door["barricade"], door["damage"]) == (1, 0, 0, 1)
        assert one(evs, "NOISE").payload["source_db"] == 85 + (10 if chk["band"] == "cost" else 0)
    else:
        assert one(evs, "ACTION_COMPLETE").payload["result"] == "held"


# --------------------------------------------------------------------------- items
def test_drop_then_pick_up(scenario):
    w = scenario("metal_fence")
    glock = w.id("glock")
    evs = run(w, helpers.make_intent(w, "pc", "drop_item", item="glock"))
    assert one(evs, "ITEM_TRANSFER").payload["to"] == {"kind": "place", "id": w.id("sales_floor"), "slot": None,
                                                        "anchor_id": w.id("counter")}
    evs = run(w, helpers.make_intent(w, "pc", "pick_up_item", target="glock", destination="counter"))
    assert one(evs, "ITEM_TRANSFER").payload["to"]["slot"] == "hand_r"
    assert item(w, "glock")["holder_body"] == w.id("pc") and glock


def test_equip_and_holster_toggle_the_holster(scenario):
    w = scenario("metal_fence")
    evs = run(w, helpers.make_intent(w, "mara", "equip_item", item="revolver"))
    tr = one(evs, "ITEM_TRANSFER")
    assert tr.payload["to"]["slot"] == "hand_r" and "holstered" not in tr.payload["props_after"]
    assert "holstered" not in item(w, "revolver")["props"]
    evs = run(w, helpers.make_intent(w, "mara", "holster_item", item="revolver"))
    assert item(w, "revolver")["holder_slot"] == "worn" and item(w, "revolver")["props"]["holstered"] is True


def test_give_needs_a_free_hand(scenario):
    """Owen (counter) hands Alice (1.5 m away) his Glock: her right hand is free, her left holds the ledger."""
    w = scenario("metal_fence")
    evs = run(w, helpers.make_intent(w, "pc", "give_item", target="alice", item="glock"))
    assert one(evs, "ITEM_TRANSFER").payload["to"] == {"kind": "body", "id": w.id("alice"), "slot": "hand_r", "anchor_id": None}
    evs = run(w, helpers.make_intent(w, "alice", "give_item", target="pc", item="glock"))
    assert item(w, "glock")["holder_body"] == w.id("pc")


def test_eating_consumes_one_unit_and_resets_hunger(fixture_packs, core_pack_dir):
    from as_engine.testing.scenario import load_scenario

    w = load_scenario({
        "schema": "as.scenario.v1", "name": "pantry", "seed": 9, "start": {"day": 40, "time": "08:00"},
        "places": [{"id": "kitchen", "name": "Kitchen", "anchors": [{"id": "table", "name": "table", "x": 2, "y": 2}]}],
        "bodies": [{"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "kitchen", "anchor": "table",
                    "needs": {"hunger": 4},
                    "inventory": [{"item": "core:item/canned_beans", "qty": 3, "slot": "pack", "label": "beans"}]}],
    }, packs_root=fixture_packs, core_pack_dir=core_pack_dir)
    try:
        imp_before = w.store.query_one("SELECT impairment FROM bodies WHERE body_id = ?", (w.id("pc"),))[0]
        evs = run(w, helpers.make_intent(w, "pc", "eat_food", item="beans"))
        assert one(evs, "ITEM_DESTROYED").payload["qty"] == 1 and item(w, "beans")["qty"] == 2
        ns = one(evs, "NEED_STAGE").payload
        assert ns == {"body_id": w.id("pc"), "need": "hunger", "stage": 0, "refreshed": True}
        assert one(evs, "ACTION_COMPLETE").payload["result"] == "ate"
        n = dict(w.store.query_one("SELECT hunger_stage, last_meal_ms FROM needs WHERE body_id = ?", (w.id("pc"),)))
        assert n["hunger_stage"] == 0 and n["last_meal_ms"] == one(evs, "NEED_STAGE").at
        assert w.store.query_one("SELECT impairment FROM bodies WHERE body_id = ?", (w.id("pc"),))[0] < imp_before
    finally:
        w.store.close()


# --------------------------------------------------------------------------- shooting (INTENT-03)
def test_an_empty_gun_clicks(scenario):
    """INTENT-03: Reggie believes it is loaded and pulls the trigger; nothing is chambered."""
    w = scenario("empty_gun")
    t = now(w)
    evs = run(w, helpers.make_intent(w, "reggie", "shoot_center_mass", target="carl", item="pistol"))
    cond = one(evs, "ITEM_CONDITION")
    assert cond.payload["result"] == "click"
    nz = one(evs, "NOISE")
    assert (nz.payload["kind"], nz.payload["source_db"]) == ("click", 20)
    assert one(evs, "ACTION_COMPLETE").payload["result"] == "click"
    assert not of(evs, "CHECK_RESOLVED") and not of(evs, "HARM"), "a click is never a shot"
    with w.store.transaction() as tx:
        perception.compile_aftermath(tx, w.id("carl"), evs, t + 5000, 0)
    texts = [r["text"] for r in helpers.percepts_of(w.store, w.id("carl"), 0)]
    assert "Reggie raises a Glock 19 toward you." in texts


def test_a_trained_shot_that_lands(scenario):
    """twin_a (P 5 -> 3, firearms 3) at the shambler 4.6 m away in a lit garage: target 6. Draw 1 ->
    margin 5 CLEAN; anatomy index 0 (chest); 9 mm is medium -> severe."""
    w = scenario("two_skills")
    evs = run(w, helpers.make_intent(w, "twin_a", "shoot_center_mass", target="shambler", item="gun_a"),
              rng=helpers.ScriptedRng(1, 0))
    assert one(evs, "ITEM_CONDITION").payload["result"] == "fired"
    nz = one(evs, "NOISE")
    assert nz.payload["kind"] == "shoot" and nz.payload["source_db"] == w.canon.get("core:item/glock_19").firearm.noise_db
    chk = one(evs, "CHECK_RESOLVED").payload
    assert (chk["target"], chk["resistance"], chk["margin"], chk["band"]) == (6, 0, 5, "clean")
    harm = one(evs, "HARM").payload
    assert (harm["body_id"], harm["anatomy"], harm["type"], harm["severity"], harm["contamination"]) == \
        (w.id("shambler"), "chest", "gunshot", "severe", 1)
    assert one(evs, "ACTION_COMPLETE").payload["result"] == "hit"


def test_a_miss_harms_nobody(scenario):
    w = scenario("two_skills")
    evs = run(w, helpers.make_intent(w, "twin_a", "shoot_center_mass", target="shambler", item="gun_a"),
              rng=helpers.ScriptedRng(8))
    assert one(evs, "CHECK_RESOLVED").payload["band"] == "fail" and not of(evs, "HARM")
    assert one(evs, "ACTION_COMPLETE").payload["result"] == "miss"


# --------------------------------------------------------------------------- melee and holds
def _brawl(fixture_packs, core_pack_dir):
    from as_engine.testing.scenario import load_scenario

    return load_scenario({
        "schema": "as.scenario.v1", "name": "brawl", "seed": 5, "start": {"day": 40, "time": "12:00"},
        "places": [{"id": "yard", "name": "Yard", "light": 3, "anchors": [{"id": "gate", "name": "gate", "x": 2, "y": 2}]}],
        "bodies": [
            {"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "yard", "anchor": "gate",
             "inventory": [{"item": "core:item/claw_hammer", "slot": "hand_r", "label": "hammer"}]},
            {"id": "tom", "stub": {"name": "Tom Keel", "age": 30, "sex": "male", "skills": {"brawling": 1}}, "place": "yard",
             "x": 2.5, "y": 2, "inventory": [{"item": "core:item/kitchen_knife", "slot": "hand_r", "label": "knife"}]},
        ],
    }, packs_root=fixture_packs, core_pack_dir=core_pack_dir)


def test_an_opposed_strike(fixture_packs, core_pack_dir):
    w = _brawl(fixture_packs, core_pack_dir)
    try:
        evs = run(w, helpers.make_intent(w, "pc", "strike_melee", target="tom", item="hammer"),
                  rng=helpers.ScriptedRng(1, 10, 0))   # attacker d10 1, defender d10 10, anatomy chest
        a, b = of(evs, "CHECK_RESOLVED")
        assert a.payload["def_id"] == "strike_melee" and b.payload["def_id"] == "strike_melee:defend"
        assert b.actor_id == w.id("tom")
        harm = one(evs, "HARM").payload
        assert (harm["anatomy"], harm["type"], harm["severity"]) == ("chest", "blunt", "significant"), "light weapon, clean win"
        assert one(evs, "ACTION_COMPLETE").payload["result"] == "hit"
    finally:
        w.store.close()


def test_grapple_then_break_free(fixture_packs, core_pack_dir):
    w = _brawl(fixture_packs, core_pack_dir)
    try:
        evs = run(w, helpers.make_intent(w, "tom", "grapple", target="pc"), rng=helpers.ScriptedRng(1, 10))
        est = one(evs, "CONTROL_ESTABLISH")
        assert est.payload == {"holder_id": w.id("tom"), "target_id": w.id("pc")}
        assert bodies.grips_on(w.store, w.id("pc")) == [w.id("tom")]
        assert w.store.query_one("SELECT restrained FROM bodies WHERE body_id = ?", (w.id("pc"),))[0] == 1
        evs = run(w, helpers.make_intent(w, "pc", "break_grip", target="tom"), rng=helpers.ScriptedRng(1, 10))
        one(evs, "CONTROL_RELEASE")
        assert bodies.grips_on(w.store, w.id("pc")) == []
        assert w.store.query_one("SELECT restrained FROM bodies WHERE body_id = ?", (w.id("pc"),))[0] == 0
    finally:
        w.store.close()


def test_disarm_puts_the_weapon_on_the_ground(fixture_packs, core_pack_dir):
    w = _brawl(fixture_packs, core_pack_dir)
    try:
        evs = run(w, helpers.make_intent(w, "pc", "disarm", target="tom"), rng=helpers.ScriptedRng(1, 10))
        assert one(evs, "ACTION_COMPLETE").payload["result"] == "disarmed"
        knife = item(w, "knife")
        assert knife["holder_body"] is None and knife["place_id"] == w.id("yard")
    finally:
        w.store.close()


# --------------------------------------------------------------------------- cover and hiding
def test_hiding_sets_hidden_only_on_a_good_margin(scenario, fixture_packs, core_pack_dir):
    """Alone in a shed, a trained hider (A 8 -> 4, stealth 3) faces no observer (resistance 0):
    target 7, draw 1 -> margin 6 -> hidden. In the lit-by-nothing sales floor Alice (A 4, untrained)
    has Owen and Mara looking: whatever the margin, hidden == (margin >= 1)."""
    from as_engine.testing.scenario import load_scenario

    w = load_scenario({
        "schema": "as.scenario.v1", "name": "shed", "seed": 2, "start": {"day": 40, "time": "12:00"},
        "places": [{"id": "shed", "name": "Shed", "anchors": [{"id": "sacks", "name": "feed sacks", "x": 1, "y": 1,
                                                                 "cover": 2, "concealment": 3}]}],
        "bodies": [{"id": "pc", "stub": {"name": "Kit Vale", "age": 25, "sex": "female", "skills": {"stealth": 3},
                                         "special": {"A": 8}}, "controller": "human", "place": "shed", "x": 2, "y": 2}],
    }, packs_root=fixture_packs, core_pack_dir=core_pack_dir)
    try:
        evs = run(w, helpers.make_intent(w, "pc", "hide", destination="sacks"), rng=helpers.ScriptedRng(1))
        chk = one(evs, "CHECK_RESOLVED").payload
        assert (chk["target"], chk["resistance"], chk["margin"], chk["ladder"]) == (7, 0, 6, "ghost_protocol")
        assert one(evs, "MOVE").payload["hidden"] is True and pos(w, "pc")["hidden"] == 1
    finally:
        w.store.close()
    for draw in (1, 10):
        w = scenario("metal_fence")
        evs = run(w, helpers.make_intent(w, "alice", "hide", destination="behind_counter"), rng=helpers.ScriptedRng(draw))
        chk = one(evs, "CHECK_RESOLVED").payload
        assert pos(w, "alice")["hidden"] == (1 if chk["margin"] >= 1 else 0)
        assert w.store.query_one("SELECT posture FROM bodies WHERE body_id = ?", (w.id("alice"),))[0] == "crouched"


def test_posture_changes(scenario):
    w = scenario("metal_fence")
    evs = run(w, helpers.make_intent(w, "pc", "go_prone"))
    pc = one(evs, "POSTURE_CHANGE")
    assert pc.payload == {"body_id": w.id("pc"), "posture": "prone", "from": "standing", "awareness": None}
    run(w, helpers.make_intent(w, "pc", "stand_up"))
    assert w.store.query_one("SELECT posture FROM bodies WHERE body_id = ?", (w.id("pc"),))[0] == "standing"


# --------------------------------------------------------------------------- talk, care, giving up
def test_calming_changes_stress(scenario):
    w = scenario("metal_fence")
    evs = run(w, helpers.make_intent(w, "june", "calm_person", target="mara"), rng=helpers.ScriptedRng(1))
    band = one(evs, "CHECK_RESOLVED").payload["band"]
    stress = [e for e in of(evs, "RESOLVE_CHANGE") if "stress_delta" in e.payload]
    if band in ("clean", "cost"):
        assert stress and stress[0].payload["stress_delta"] == (-2 if band == "clean" else -1)
    assert one(evs, "ACTION_COMPLETE").payload["result"] == "said"


def test_bandaging_a_wound(scenario):
    w = scenario("metal_fence")
    with w.store.transaction() as tx:
        cause = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=now(w), turn_index=0))
        bodies.apply_harm(tx, w.id("alice"), WoundSpec("arm_l", "cut", "significant"), now(w), cause.event_id, 0, w.rng)
    wid = w.store.query_one("SELECT wound_id FROM wounds WHERE body_id = ?", (w.id("alice"),))[0]
    evs = run(w, helpers.make_intent(w, "pc", "bandage_wound", target=wid))
    tr = one(evs, "TREATMENT")
    assert tr.payload["method"] == "bandage" and tr.payload["by_actor"] == w.id("pc")


def test_surrender_drops_what_is_held(scenario):
    w = scenario("metal_fence")
    evs = run(w, helpers.make_intent(w, "pc", "surrender"))
    assert item(w, "glock")["place_id"] == w.id("sales_floor")
    assert w.store.query_one("SELECT posture FROM bodies WHERE body_id = ?", (w.id("pc"),))[0] == "crouched"
    assert one(evs, "ACTION_COMPLETE").payload["result"] == "surrendered"


def test_throw_makes_noise_where_it_lands(scenario):
    w = scenario("metal_fence")
    evs = run(w, helpers.make_intent(w, "alice", "throw_distraction", destination="rear_cover", item="alice_ledger"))
    nz = one(evs, "NOISE").payload
    assert (nz["source_db"], nz["anchor_id"], nz["x_m"], nz["y_m"]) == (70, w.id("rear_cover"), 12.5, 8.0)


# --------------------------------------------------------------------------- legality (EFF-02)
def test_legality_causes(scenario):
    w = scenario("metal_fence")
    cases = [
        (helpers.make_intent(w, "pc", "follow_body", target="june"), "target_gone"),       # June is in the stockroom
        (helpers.make_intent(w, "pc", "punch", target="mara"), "out_of_reach"),          # 5 m away
        (helpers.make_intent(w, "eli", "stand_up"), "incapable"),                        # asleep
    ]
    for intent, cause in cases:
        evs = run(w, intent)
        assert one(evs, "ACTION_BLOCKED").payload["cause"] == cause, cause


def test_hands_full(scenario):
    """Owen holds the Glock (right) and takes out his axe (left): no hand is left for the ledger
    Alice put down behind the counter."""
    w = scenario("metal_fence")
    run(w, helpers.make_intent(w, "pc", "equip_item", item="axe"))
    assert item(w, "axe")["holder_slot"] == "hand_l"
    run(w, helpers.make_intent(w, "alice", "drop_item", item="alice_ledger"))
    evs = run(w, helpers.make_intent(w, "pc", "pick_up_item", target="alice_ledger", destination="behind_counter"))
    assert one(evs, "ACTION_BLOCKED").payload["cause"] == "hands_full"
    assert item(w, "alice_ledger")["place_id"] == w.id("sales_floor")


def test_the_first_to_land_gets_the_item(scenario):
    """Two hands reach for one axe on the counter: Owen stands at it, Alice 1.5 m away walks —
    Owen's landing comes first, Alice's finds it gone (never silently dropped)."""
    w = scenario("metal_fence")
    run(w, helpers.make_intent(w, "pc", "equip_item", item="axe"))
    run(w, helpers.make_intent(w, "pc", "drop_item", item="axe"))
    evs = run(w, helpers.make_intent(w, "pc", "pick_up_item", target="axe", destination="counter"),
              helpers.make_intent(w, "alice", "pick_up_item", target="axe", destination="counter"))
    assert item(w, "axe")["holder_body"] == w.id("pc")
    assert one(evs, "ACTION_BLOCKED", w.id("alice")).payload["cause"] == "item_gone"


def _armory(fixture_packs, core_pack_dir):
    from as_engine.testing.scenario import load_scenario

    return load_scenario({
        "schema": "as.scenario.v1", "name": "armory", "seed": 4, "start": {"day": 40, "time": "12:00"},
        "places": [{"id": "room", "name": "Back room", "anchors": [{"id": "bench", "name": "bench", "x": 1, "y": 1}]}],
        "bodies": [{"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "room", "anchor": "bench",
                    "inventory": [
                        {"item": "core:item/glock_19", "slot": "hand_r", "label": "glock", "props": {"chambered": False}},
                        {"item": "core:item/magazine_9mm_15", "container": "glock", "label": "empty_mag", "props": {"rounds": 0}},
                        {"item": "core:item/magazine_9mm_15", "slot": "pocket", "label": "full_mag", "props": {"rounds": 15}},
                        {"item": "core:item/revolver_38", "slot": "hand_l", "label": "revolver", "props": {"rounds": 1}},
                        {"item": "core:item/ammo_38", "qty": 11, "slot": "pocket", "label": "loose"}]}],
    }, packs_root=fixture_packs, core_pack_dir=core_pack_dir)


def test_reload_swaps_the_magazine_and_chambers(fixture_packs, core_pack_dir):
    w = _armory(fixture_packs, core_pack_dir)
    try:
        evs = run(w, helpers.make_intent(w, "pc", "reload_firearm", item="glock"))
        assert item(w, "empty_mag")["holder_slot"] == "pack" and item(w, "full_mag")["container_id"] == w.id("glock")
        cond = one(evs, "ITEM_CONDITION").payload
        assert cond == {"firearm_id": w.id("glock"), "result": "chambered", "rounds_left": 15}
        assert item(w, "glock")["props"]["chambered"] is True and item(w, "full_mag")["props"]["rounds"] == 14
    finally:
        w.store.close()


def test_reload_a_revolver_round_by_round(fixture_packs, core_pack_dir):
    w = _armory(fixture_packs, core_pack_dir)
    try:
        t = now(w)
        i = helpers.make_intent(w, "pc", "reload_firearm", item="revolver")
        evs = run(w, i)
        cap = w.canon.get("core:item/revolver_38").firearm.capacity
        loaded = cap - 1
        assert one(evs, "ITEM_DESTROYED").payload["qty"] == loaded and item(w, "loose")["qty"] == 11 - loaded
        assert one(evs, "ITEM_CONDITION").payload == {"firearm_id": w.id("revolver"), "result": "loaded", "rounds_left": cap}
        land = effects.land_ms(t, i.bound.est_duration_s)
        assert one(evs, "ACTION_COMPLETE").at == land + max(0, loaded * 2000 - (land - t)), "two seconds a round"
    finally:
        w.store.close()
