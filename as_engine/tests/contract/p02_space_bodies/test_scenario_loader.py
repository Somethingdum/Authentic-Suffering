"""Scenario loader (P2). testing/scenario.load_scenario — the docstring's "Row details" are the
contract; every fixture must load and pass the 58-bit gate at turn 0."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from as_engine.audit.commit_gate import compute
from as_engine.contracts.common import age_band_for
from as_engine.contracts.dossier import ActorDossier
from as_engine.contracts.settings import RulesConfig
from as_engine.kernel.clock import MS_PER_H, MS_PER_S
from as_engine.kernel.hashing import world_state_hash
from as_engine.kernel.ids import format_id
from as_engine.kernel.jsoncanon import canonical_json
from as_engine.testing.scenario import load_scenario

pytestmark = pytest.mark.phase(2)

SCENARIOS = sorted(p.stem for p in (Path(__file__).resolve().parents[2] / "fixtures" / "scenarios").glob("*.yaml"))


def rows(w, sql, params=()):
    return [dict(r) for r in w.store.query(sql, params)]


def one(w, sql, params=()):
    r = w.store.query_one(sql, params)
    return dict(r) if r is not None else None


# --------------------------------------------------------------------------- every fixture
@pytest.mark.parametrize("name", SCENARIOS)
def test_every_fixture_loads_and_passes_the_gate_at_turn_zero(scenario, spec_of, name):
    w = scenario(name)
    res = compute(w.store, 0)
    assert res.failures == [], f"{name}: gate bits down at turn 0: {res.failures}"
    human = next(b.id for b in spec_of(name).bodies if b.controller == "human")
    assert w.store.meta("pc_actor_id") == w.pc_id == w.id(human)
    evs = rows(w, "SELECT turn_index, origin FROM events")
    assert evs and all(e["turn_index"] == 0 and e["origin"] == "system" for e in evs)


def test_loading_is_deterministic(scenario):
    a, b = scenario("metal_fence"), scenario("metal_fence")
    assert world_state_hash(a.store) == world_state_hash(b.store)
    assert a.ids == b.ids


# --------------------------------------------------------------------------- ids
def test_ids_are_minted_up_front_in_fixture_order(scenario, spec_of):
    spec = spec_of("metal_fence")
    w = scenario("metal_fence")
    for n, p in enumerate(spec.places, 1):
        assert w.id(p.id) == format_id("plc", n)
    anchors = [a.id for p in spec.places for a in p.anchors]
    for n, a in enumerate(anchors, 1):
        assert w.id(a) == format_id("anc", n)
    for n, p in enumerate(spec.portals, 1):
        assert w.id(p.id) == format_id("prt", n)
    for n, b in enumerate(spec.bodies, 1):
        assert w.id(b.id) == format_id("act", n)
    labelled = [i.label for b in spec.bodies for i in b.inventory]
    items = rows(w, "SELECT item_id FROM items ORDER BY item_id")
    assert [r["item_id"] for r in items] == [format_id("itm", n) for n in range(1, len(labelled) + 1)]
    assert w.id("glock") == format_id("itm", 1)  # first inventory item of the first body
    tasks = rows(w, "SELECT task_id, actor_id FROM tasks ORDER BY task_id")
    assert [(t["task_id"], t["actor_id"]) for t in tasks] == [(format_id("tsk", 1), w.id("alice")),
                                                              (format_id("tsk", 2), w.id("june"))]


# --------------------------------------------------------------------------- rows
def test_row_counts_match_the_fixture(scenario, spec_of):
    spec = spec_of("metal_fence")
    w = scenario("metal_fence")
    count = lambda t: w.store.query_one(f"SELECT COUNT(*) AS n FROM {t}")["n"]  # noqa: E731
    assert count("places") == len(spec.places)
    assert count("anchors") == sum(len(p.anchors) for p in spec.places)
    assert count("portals") == len(spec.portals)
    assert count("bodies") == len(spec.bodies) == count("positions") == count("actors") == count("dossiers")
    assert count("items") == sum(len(b.inventory) for b in spec.bodies) + len(spec.items)
    assert count("relationships") == len(spec.relationships)
    assert count("acquaintance") == len(spec.knows)
    assert count("claim_holdings") == len(spec.beliefs)
    assert count("households") == 1 and count("household_members") == 2
    assert count("groups") == 1 and count("group_members") == 5
    assert count("event_queue") == 1


def test_clock_places_and_portals(scenario, spec_of):
    spec = spec_of("metal_fence")
    w = scenario("metal_fence")
    clock = one(w, "SELECT * FROM world_clock")
    assert clock == {"id": 1, "now_ms": spec.start.ms(), "turn_index": 0, "weather": "wind", "wind_level": 2}
    floor = one(w, "SELECT * FROM places WHERE place_id = ?", (w.id("sales_floor"),))
    assert (floor["kind"], floor["width_m"], floor["depth_m"], floor["material"], floor["light_level"],
            floor["ambient_db"], floor["held"], floor["layout_generated"]) == ("room", 14, 9, "brick", 1, 35, 1, 1)
    alley = one(w, "SELECT indoor, held FROM places WHERE place_id = ?", (w.id("alley"),))
    assert alley == {"indoor": 0, "held": 0}
    front = one(w, "SELECT * FROM portals WHERE portal_id = ?", (w.id("front_door"),))
    assert (front["is_open"], front["is_locked"], front["lock_quality"], front["barricade"], front["damage"]) == (0, 1, 2, 2, 0)
    assert (front["place_a"], front["place_b"], front["anchor_a"], front["anchor_b"]) == (
        w.id("sales_floor"), w.id("street"), w.id("front_door_in"), w.id("front_door_out"))
    back = one(w, "SELECT is_open, barricade, aperture_w_cm, aperture_h_cm, seal_db FROM portals WHERE portal_id = ?", (w.id("back_door"),))
    assert back == {"is_open": 1, "barricade": 0, "aperture_w_cm": 90, "aperture_h_cm": 205, "seal_db": 30}
    fence = one(w, "SELECT kind, transparent, aperture_w_cm, height_cm, seal_db FROM portals WHERE portal_id = ?", (w.id("rear_fence"),))
    assert fence == {"kind": "fence", "transparent": 1, "aperture_w_cm": 0, "height_cm": 180, "seal_db": 2}


def test_bodies_come_from_their_dossiers(scenario, canon, spec_of):
    spec = spec_of("metal_fence")
    w = scenario("metal_fence")
    mara_d = canon.get("core:actor/mara_voss")
    mara = one(w, "SELECT * FROM bodies WHERE body_id = ?", (w.id("mara"),))
    assert mara["kind"] == "human" and mara["content_ref"] == "core:actor/mara_voss" and mara["origin"] == "scenario"
    assert (mara["height_cm"], mara["mass_kg"], mara["age_years"], mara["sex"]) == (
        mara_d.appearance.height_cm, mara_d.appearance.mass_kg, mara_d.identity.age, mara_d.identity.sex)
    assert mara["age_band"] == age_band_for(mara_d.identity.age).value
    assert json.loads(mara["special"]) == mara_d.capability.special.model_dump(mode="json")
    assert mara["alive"] == 1 and mara["progressed_at"] == spec.start.ms()
    eli = one(w, "SELECT awareness, posture FROM bodies WHERE body_id = ?", (w.id("eli"),))
    assert eli == {"awareness": "asleep", "posture": "lying"}


def test_needs_are_back_dated_from_their_stage(scenario, spec_of, rules):
    spec = spec_of("metal_fence")
    w = scenario("metal_fence")
    start = spec.start.ms()
    n = one(w, "SELECT * FROM needs WHERE body_id = ?", (w.id("mara"),))
    assert n["fatigue_stage"] == 3 and n["thirst_stage"] == 0
    assert n["last_sleep_ms"] == start - int(3 * rules.needs.fatigue_stage_every_h * MS_PER_H)
    assert n["last_drink_ms"] == start and n["last_meal_ms"] == start
    # fatigue stage 3 -> 1 impairment step (HARM-07); the loader stores the computed value
    assert one(w, "SELECT impairment FROM bodies WHERE body_id = ?", (w.id("mara"),))["impairment"] == 1


def test_positions_use_the_anchor_point(scenario):
    w = scenario("metal_fence")
    pos = one(w, "SELECT * FROM positions WHERE body_id = ?", (w.id("mara"),))
    anc = one(w, "SELECT x_m, y_m FROM anchors WHERE anchor_id = ?", (w.id("front_window"),))
    assert (pos["place_id"], pos["anchor_id"], pos["x_m"], pos["y_m"]) == (w.id("sales_floor"), w.id("front_window"), anc["x_m"], anc["y_m"])


def test_actors_and_full_dossiers(scenario, canon):
    w = scenario("metal_fence")
    june = one(w, "SELECT * FROM actors WHERE actor_id = ?", (w.id("june"),))
    d = one(w, "SELECT * FROM dossiers WHERE dossier_id = ?", (june["dossier_id"],))
    rec = canon.get("core:actor/june_okafor")
    assert d["baseline_json"] == canonical_json(rec.model_dump(mode="json", by_alias=True)), "DOS-01: never trimmed"
    assert d["content_hash"] == hashlib.sha256(d["baseline_json"].encode("utf-8")).hexdigest()
    assert d["source"] == "pack" and d["content_ref"] == "core:actor/june_okafor"
    assert june["display_name"] == rec.identity.name and june["controller"] == "model"
    assert june["resolve_cur"] == 3 and june["resolve_max"] >= 1
    mara = one(w, "SELECT * FROM actors WHERE actor_id = ?", (w.id("mara"),))
    assert mara["resolve_cur"] == mara["resolve_max"]
    assert mara["duty_anchor"] == w.id("front_window") and mara["goal_text"] == "watch the front window"
    plan = one(w, "SELECT * FROM plans WHERE actor_id = ?", (w.id("mara"),))
    assert json.loads(plan["standing_orders"]) == [{"trigger": "loud_noise", "response": "find the source and cover it"}]
    assert one(w, "SELECT goal_text FROM actors WHERE actor_id = ?", (w.id("nita"),))["goal_text"] == "finish the perimeter walk"
    assert one(w, "SELECT controller FROM actors WHERE actor_id = ?", (w.id("pc"),))["controller"] == "human"


def test_resolve_max_formula(rules):
    """mind.actor.resolve_max: base + (E + C) // divisor + trait_mod, never below 1 (built in P2)."""
    from as_engine.mind.actor import resolve_max

    r = rules.resolve
    assert resolve_max(5, 5, 0, r) == r.base + 10 // r.divisor
    assert resolve_max(8, 7, 1, r) == r.base + 15 // r.divisor + 1
    assert resolve_max(1, 1, -2, r) >= 1


def test_items_tasks_and_conservation_payloads(scenario, spec_of):
    spec = spec_of("metal_fence")
    w = scenario("metal_fence")
    glock = one(w, "SELECT * FROM items WHERE item_id = ?", (w.id("glock"),))
    assert (glock["def_ref"], glock["holder_body"], glock["holder_slot"], json.loads(glock["props"])) == (
        "core:item/glock_19", w.id("pc"), "hand_r", {"chambered": True})
    mag = one(w, "SELECT * FROM items WHERE container_id = ?", (w.id("glock"),))
    assert mag["def_ref"] == "core:item/magazine_9mm_15" and json.loads(mag["props"]) == {"rounds": 14}
    assert mag["holder_body"] is None and mag["place_id"] is None
    created = rows(w, "SELECT payload FROM events WHERE type = 'ITEM_CREATED'")
    assert len(created) == len(rows(w, "SELECT item_id FROM items"))
    ammo = [json.loads(e["payload"]) for e in created if json.loads(e["payload"])["def_ref"] == "core:item/ammo_38"]
    assert ammo[0]["qty"] == 11 and ammo[0]["origin"] == "scenario"
    start = spec.start.ms()
    t = one(w, "SELECT * FROM tasks WHERE actor_id = ?", (w.id("june"),))
    assert (t["steps_done"], t["steps_total"], t["status"]) == (41, 60, "active")
    assert t["started_at"] == start - 41 * 10 * MS_PER_S and t["next_due_at"] == start + 10 * MS_PER_S
    assert json.loads(t["interrupt_on"]) == ["loud_noise", "addressed_by_name"] and t["focus"] == 0
    seeds = [json.loads(e["payload"]) for e in rows(w, "SELECT payload FROM events WHERE type = 'TASK_STEP'")]
    june = next(p for p in seeds if p["actor_id"] == w.id("june"))
    assert june == {"task_id": t["task_id"], "actor_id": w.id("june"), "kind": "count_stock", "label": "counting cans",
                    "steps_done": 41, "steps_total": 60, "status": "active", "seed": True}


def test_relationships_are_seeded_without_deltas(scenario):
    w = scenario("metal_fence")
    r = one(w, "SELECT * FROM relationships WHERE from_id = ? AND to_id = ?", (w.id("mara"), w.id("eli")))
    assert (r["kind"], r["trust"], r["affection"]) == ("child", 3, 3), "kind = what the target is to the holder"
    for e in rows(w, "SELECT payload FROM events WHERE type = 'RELATION_CHANGE'"):
        p = json.loads(e["payload"])
        assert "delta" not in p and p["seed"] is True


def test_acquaintance_names_and_descriptions(scenario, canon):
    w = scenario("metal_fence")
    a = one(w, "SELECT * FROM acquaintance WHERE holder_id = ? AND subject_id = ?", (w.id("nita"), w.id("stranger")))
    assert a["known_name"] is None and a["description"] == "the thin man who watches the back fence"
    assert a["last_seen_place"] == w.id("back_lot")
    from as_engine.mind.perception import describe_dossier

    b = one(w, "SELECT * FROM acquaintance WHERE holder_id = ? AND subject_id = ?", (w.id("pc"), w.id("mara")))
    mara = canon.get("core:actor/mara_voss")
    assert b["known_name"] == "Mara" and b["description"] == describe_dossier(mara.model_dump(mode="json", by_alias=True))
    kid = one(w, "SELECT * FROM acquaintance WHERE holder_id = ? AND subject_id = ?", (w.id("pc"), w.id("eli")))
    assert kid["description"] == "thin boy"  # 132 cm, 26 kg: BMI 14.9 (describe_dossier)
    assert describe_dossier(canon.get("core:pc/owen_marsh").model_dump(mode="json", by_alias=True)) == "tall, heavyset man"


def test_known_places_are_home_ground(scenario):
    """W09 at turn 0: own place + places adjacent through a non-wall, non-fence portal."""
    w = scenario("metal_fence")

    def known(local):
        return {r["place_id"]: r["visited"] for r in rows(w, "SELECT place_id, visited FROM known_places WHERE holder_id = ?", (w.id(local),))}

    assert known("pc") == {w.id("sales_floor"): 1, w.id("storeroom"): 0, w.id("office"): 0, w.id("street"): 0}
    assert known("stranger") == {w.id("back_lot"): 1}, "a fence is not a way in"
    assert known("nita") == {w.id("alley"): 1, w.id("storeroom"): 0, w.id("office"): 0}
    assert not rows(w, "SELECT 1 FROM percept_log"), "seeded knowledge is not a percept"


def test_beliefs_true_false_and_told_by(scenario):
    w = scenario("metal_fence")
    held = rows(w, "SELECT h.*, p.text, p.matches_claim FROM claim_holdings h JOIN propositions p ON p.prop_id = h.claim_id "
                   "WHERE h.holder_id = ? ORDER BY p.text", (w.id("nita"),))
    assert [h["text"] for h in held] == ["A thin man has been watching the back fence at night.", "The alley was clear at eleven."]
    watching, clear = held
    preds = {r["text"]: r["predicate"] for r in rows(w, "SELECT text, predicate FROM propositions")}
    assert preds[watching["text"]] == "watching" and preds[clear["text"]] == "status"
    claim = one(w, "SELECT * FROM claims WHERE claim_id = ?", (watching["matches_claim"],))
    assert claim["subject_type"] == "body" and claim["subject_id"] == w.id("stranger") and claim["predicate"] == "watching"
    assert clear["matches_claim"] is None
    assert (watching["fidelity"], watching["confidence"], watching["provenance"]) == ("exact", 2, "witnessed")
    mara = one(w, "SELECT provenance, believed FROM claim_holdings WHERE holder_id = ?", (w.id("mara"),))
    assert mara == {"provenance": f"told_by:{w.id('nita')}", "believed": 1}


def test_cues_become_lessons(scenario, canon):
    w = scenario("metal_fence")
    for local, ref in (("mara", "core:actor/mara_voss"), ("pc", "core:pc/owen_marsh")):
        cues = canon.get(ref).knowledge.cues
        got = rows(w, "SELECT cue_tags, confidence FROM lessons WHERE holder_id = ? ORDER BY lesson_id", (w.id(local),))
        assert [json.loads(r["cue_tags"]) for r in got] == [[c] for c in cues]
        assert all(r["confidence"] == 3 for r in got)


def test_due_events_and_society_rows(scenario, spec_of):
    spec = spec_of("metal_fence")
    w = scenario("metal_fence")
    q = one(w, "SELECT * FROM event_queue")
    assert (q["type"], q["due_at"], q["status"]) == ("NOISE", spec.start.ms(), "pending")
    p = json.loads(q["payload"])
    assert p["source_db"] == 98 and p["place_id"] == w.id("alley") and p["anchor_id"] == w.id("fence_sheet")
    hm = rows(w, "SELECT actor_id, role, guardian_of FROM household_members ORDER BY role")
    assert [(r["actor_id"], r["role"]) for r in hm] == [(w.id("eli"), "child"), (w.id("mara"), "head")]
    assert json.loads([r for r in hm if r["role"] == "head"][0]["guardian_of"]) == [w.id("eli")]
    g = one(w, "SELECT * FROM groups")
    assert g["content_ref"] == "core:faction/delgados_crew" and g["kind"] == "group"


def test_settlement_workplaces_and_stubs(scenario, spec_of):
    spec = spec_of("pump_settlement")
    w = scenario("pump_settlement")
    s = one(w, "SELECT * FROM settlements")
    assert json.loads(s["stores"])["water"] == 192 and s["ration_level"] == 3 and s["group_id"] is not None
    laws = {r["law_ref"] for r in rows(w, "SELECT law_ref FROM laws_active")}
    assert laws == {"core:law/ration_law", "core:law/nightfall_curfew", "core:law/contamination_quarantine"}
    pump = one(w, "SELECT * FROM workplaces WHERE site_type = 'water_pump'")
    six = spec.start.day * 24 * MS_PER_H + 6 * MS_PER_H
    assert pump["next_due_at"] == six and json.loads(pump["outputs"]) == {"water": 31}
    shifts = rows(w, "SELECT actor_id, shift_start_hh, shift_end_hh FROM work_assignments WHERE workplace_id = ? ORDER BY actor_id", (pump["workplace_id"],))
    assert len(shifts) == 4 and {(r["shift_start_hh"], r["shift_end_hh"]) for r in shifts} == {(6, 18), (18, 6)}
    hal = one(w, "SELECT d.* FROM dossiers d JOIN actors a ON a.dossier_id = d.dossier_id WHERE a.actor_id = ?", (w.id("hal"),))
    assert hal["source"] == "fixture" and hal["content_ref"] is None
    ActorDossier.model_validate_json(hal["baseline_json"])
    assert one(w, "SELECT content_ref, kind FROM bodies WHERE body_id = ?", (w.id("hal"),)) == {"content_ref": None, "kind": "human"}


def test_infected_bodies(scenario, canon):
    w = scenario("two_skills")
    inf = rows(w, "SELECT b.*, i.type_id, i.states, i.energy FROM bodies b JOIN infected_state i ON i.body_id = b.body_id")
    assert inf, "two_skills has a shambler"
    t = canon.find("infected", inf[0]["type_id"])
    b = inf[0]
    assert b["kind"] == "infected" and b["sex"] is None and (b["height_cm"], b["mass_kg"]) == (170, 65)
    assert json.loads(b["special"]) == {k: (v.lo + v.hi) // 2 for k, v in t.special.items()}
    assert (json.loads(b["states"]), b["energy"]) == ([], 50)
    assert not rows(w, "SELECT 1 FROM actors WHERE actor_id = ?", (b["body_id"],)), "infected bodies have no mind row"


def test_rules_deep_merge(scenario, spec_of, tmp_path, fixture_packs, core_pack_dir):
    data = yaml.safe_load((Path(__file__).resolve().parents[2] / "fixtures" / "scenarios" / "three_rooms_gunshot.yaml").read_text())
    data["rules"] = {"acoustics": {"exact_margin_db": 14.0}}
    w = load_scenario(data, packs_root=fixture_packs, core_pack_dir=core_pack_dir,
                      rules=RulesConfig(harm={"death_at_blood_loss_pct": 45.0}))
    try:
        eff = RulesConfig.model_validate_json(w.store.meta("rules_json"))
        assert eff.acoustics.exact_margin_db == 14.0 and eff.harm.death_at_blood_loss_pct == 45.0
        assert eff.acoustics.partial_margin_db == RulesConfig().acoustics.partial_margin_db, "deep merge keeps the rest"
        assert w.store.rules == eff and w.config.rules == eff
        assert w.store.meta("content_hash") == w.canon.content_hash
    finally:
        w.store.close()


@pytest.mark.parametrize("mutate,needle", [
    (lambda d: d["bodies"][1].update(dossier="core:actor/mara_vos"), "mara_vos"),
    (lambda d: d["bodies"][1]["inventory"].append({"item": "core:item/laser_rifle", "slot": "pack"}), "laser_rifle"),
    (lambda d: d.update(start={"day": 900, "time": "23:14:03"}), "days_since_fall_range"),
    (lambda d: d["bodies"].append({"id": "lurk", "infected": "ZOMBIE_VARIANT_ID_LURKER01", "controller": "policy",
                                   "place": "back_lot"}), "ZOMBIE_VARIANT_ID_LURKER01"),
    (lambda d: d["settlements"].append({"id": "s", "name": "S", "place": "alley", "laws": ["core:law/no_such_law"]}), "no_such_law"),
    (lambda d: d["bodies"][1].update(focus=True), "focus"),     # Mara has no task to focus on
])
def test_bad_fixtures_are_refused_with_a_named_reason(fixture_packs, core_pack_dir, mutate, needle):
    data = yaml.safe_load((Path(__file__).resolve().parents[2] / "fixtures" / "scenarios" / "metal_fence.yaml").read_text())
    data.setdefault("settlements", [])
    mutate(data)
    with pytest.raises(ValueError) as ei:
        load_scenario(data, packs_root=fixture_packs, core_pack_dir=core_pack_dir)
    assert needle in str(ei.value)
