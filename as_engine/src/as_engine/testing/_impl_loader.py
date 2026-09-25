"""Implementation of the scenario loader."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from .scenario import (parse_scenario, stub_dossier, ScenarioWorld, MS_PER_DAY, MS_PER_H, MS_PER_MIN, MS_PER_S)
def _deep_merge(a, b):
    out = dict(a)
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _clock_ms(spec_time: str, start_ms: int) -> int:
    if spec_time.startswith("+"):
        import re
        m = re.match(r"^\+(\d+)(ms|s|m|h)$", spec_time)
        n, u = int(m.group(1)), m.group(2)
        return start_ms + n * {"ms": 1, "s": MS_PER_S, "m": MS_PER_MIN, "h": MS_PER_H}[u]
    parts = [int(x) for x in spec_time.split(":")]
    hh, mm, ss = (parts + [0])[:3]
    return (start_ms // MS_PER_DAY) * MS_PER_DAY + hh * MS_PER_H + mm * MS_PER_MIN + ss * MS_PER_S


def load_scenario(path_or_dict: str | Path | dict, *, packs_root: str | Path, core_pack_dir: str | Path,
                  rules: Any = None, transport: Any = None) -> ScenarioWorld:
    import hashlib
    import json as _json
    from ..content.pack import load_canon
    from ..contracts.common import ANATOMY_GROUP, age_band_for
    from ..contracts.dossier import ActorDossier
    from ..contracts.events import Event, EventType, WriteOp, WriteRecord
    from ..contracts.narration import NarratorStyle
    from ..contracts.settings import EngineConfig, RulesConfig, RunSettings
    from ..kernel.jsoncanon import canonical_json
    from ..kernel.rng import Rng
    from ..kernel.store import Store
    from ..kernel import clock as kclock
    from ..kernel.truth import fact_write
    from ..lanes.client import LaneClient
    from ..mind.actor import resolve_max
    from ..physical import bodies as pbodies
    from ..physical import objects as pobjects
    from ..physical.bodies import _wound_values
    from .fake_lm import FakeTransport

    spec = parse_scenario(path_or_dict)
    start = spec.start.ms()
    canon, issues = load_canon([Path(core_pack_dir)] + [Path(packs_root) / p for p in spec.packs])
    errs = [i for i in issues if i.severity == "error"]
    if errs:
        raise ValueError("content errors: " + "; ".join(i.message for i in errs[:5]))
    eff = RulesConfig.model_validate(_deep_merge(_deep_merge(RulesConfig().model_dump(mode="json"), spec.rules),
                                                 (rules.model_dump(mode="json", exclude_unset=True) if rules is not None else {})))
    store = Store.memory(run_id=spec.name, seed=spec.seed, start_ms=start)
    store.attach(canon=canon, rules=eff)
    rng = Rng(spec.seed)
    ids: dict[str, str] = {}

    def E(type_, writer, writes, payload=None, **kw):
        return tx.commit_event(Event(type=type_, writer=writer, at=start, turn_index=0, origin="system",
                                     writes=writes, payload=payload or {}, **kw))

    def W(table, values, op=WriteOp.INSERT, key=None):
        return WriteRecord(op=op, table=table, values=values, key=key or {})

    # dossiers
    doss = {}
    for b in spec.bodies:
        if b.focus and b.task is None:
            raise ValueError(f"body {b.id}: focus without a task")
        if b.dossier:
            if not canon.has(b.dossier):
                raise ValueError(f"body {b.id}: dossier '{b.dossier}' does not exist in the loaded packs")
            rec = canon.get(b.dossier)
            r = rec.days_since_fall_range
            if r is not None and not (r[0] <= spec.start.day <= r[1]):
                raise ValueError(f"body {b.id}: {b.dossier} has days_since_fall_range {list(r)}; day {spec.start.day} is outside it (WG-34)")
            doss[b.id] = (rec, "pack", b.dossier)
        elif b.stub:
            rec = ActorDossier.model_validate(stub_dossier(b.id, b.stub))
            doss[b.id] = (rec, "fixture", None)
    for b in spec.bodies:
        for it in b.inventory:
            if not canon.has(it.item):
                raise ValueError(f"body {b.id}: item '{it.item}' does not exist")
    for b in spec.bodies:
        if b.animal and not canon.has(b.animal):
            raise ValueError(f"body {b.id}: animal '{b.animal}' does not exist")
    for it in spec.items:
        if not canon.has(it.item):
            raise ValueError(f"loose item: '{it.item}' does not exist")
    for s in spec.settlements:
        for l in s.laws:
            if not canon.has(l):
                raise ValueError(f"settlement {s.id}: law '{l}' does not exist")
    for g in spec.groups:
        if g.content_ref and not canon.has(g.content_ref):
            raise ValueError(f"group {g.id}: content_ref '{g.content_ref}' does not exist")
    from ..contracts.dossier import Looks as _Looks
    looks_of_body = {}
    for b in spec.bodies:
        lk = None
        if b.looks is not None:
            lk = _Looks.model_validate(b.looks)
        elif b.dress and b.id in doss:
            lk = doss[b.id][0].appearance.looks
        if b.dress and lk is None:
            raise ValueError(f"body {b.id}: dress without looks: nothing to dress it in")
        if b.looks is not None or b.dress:
            looks_of_body[b.id] = lk
    humans = [b for b in spec.bodies if b.controller == "human"]
    if len(humans) != 1:
        raise ValueError("exactly one human body")

    with store.transaction() as tx:
        # ids up front
        for p in spec.places:
            ids[p.id] = tx.mint("plc")
        for p in spec.places:
            for a in p.anchors:
                ids[a.id] = tx.mint("anc")
        for pt in spec.portals:
            ids[pt.id] = tx.mint("prt")
        for b in spec.bodies:
            ids[b.id] = tx.mint("act")
        item_ids = []
        for b in spec.bodies:
            for it in b.inventory:
                iid = tx.mint("itm")
                item_ids.append((b, it, iid))
                if it.label:
                    ids[it.label] = iid
        loose_ids = []
        for it in spec.items:
            iid = tx.mint("itm")
            loose_ids.append((it, iid))
            for lab in (it.id, it.label):
                if lab:
                    ids[lab] = iid
        task_ids = []
        for b in spec.bodies:
            if b.task:
                task_ids.append((b, tx.mint("tsk")))
        I = lambda x: ids[x] if x is not None else None  # noqa: E731

        # meta
        E(EventType.SETTINGS_CHANGE, "kernel.meta", [
            W("meta", {"value": RunSettings(**spec.settings).model_dump_json()}, WriteOp.UPDATE, {"key": "settings_json"}),
            W("meta", {"value": eff.model_dump_json()}, WriteOp.UPDATE, {"key": "rules_json"}),
            W("meta", {"value": canon.content_hash}, WriteOp.UPDATE, {"key": "content_hash"})], {"source": "scenario"})
        # clock weather
        E(EventType.WEATHER_CHANGE, "kernel.clock", [W("world_clock", {"weather": spec.weather.kind, "wind_level": spec.weather.wind_level}, WriteOp.UPDATE, {"id": 1})],
          {"weather": spec.weather.kind, "wind_level": spec.weather.wind_level})
        # places
        for p in spec.places:
            ws = [W("places", {"place_id": ids[p.id], "parent_id": I(p.parent), "kind": p.kind, "name": p.name, "width_m": p.width_m,
                               "depth_m": p.depth_m, "indoor": int(p.indoor), "material": p.material, "light_level": p.light,
                               "ambient_db": p.ambient_db, "layout_generated": 1, "held": int(p.held), "props": {},
                               "elevation_m": p.elevation_m})]
            for a in p.anchors:
                ws.append(W("anchors", {"anchor_id": ids[a.id], "place_id": ids[p.id], "name": a.name, "kind": a.kind, "x_m": a.x, "y_m": a.y,
                                        "cover": a.cover, "concealment": a.concealment, "capacity": 4}))
            E(EventType.PLACE_DISCOVERED, "physical.space", ws, {"place_id": ids[p.id], "source": "scenario"}, place_id=ids[p.id])
        ws = []
        for pt in spec.portals:
            ws.append(W("portals", {"portal_id": ids[pt.id], "place_a": ids[pt.a], "place_b": ids[pt.b], "anchor_a": I(pt.anchor_a), "anchor_b": I(pt.anchor_b),
                                    "kind": pt.kind, "name": pt.name, "is_open": int(pt.open), "is_locked": int(pt.locked), "lock_quality": pt.lock_quality,
                                    "barricade": pt.barricade, "damage": pt.damage, "aperture_w_cm": pt.w, "aperture_h_cm": pt.h, "seal_db": pt.seal_db,
                                    "open_loss_db": pt.open_loss_db, "transparent": int(pt.transparent), "height_cm": pt.height,
                                    "gap_cm": pt.gap, "below_id": I(pt.below)}))
        if ws:
            E(EventType.PLACE_DISCOVERED, "physical.space", ws, {"portals": len(ws), "source": "scenario"})
        # bodies
        mat_ev = {}
        N = eff.needs
        for b in spec.bodies:
            bid = ids[b.id]
            if b.id in doss:
                rec = doss[b.id][0]
                kind = "lurker" if "lurker" in rec.tags else "human"
                vals = {"kind": kind, "content_ref": doss[b.id][2], "sex": rec.identity.sex, "age_years": rec.identity.age,
                        "age_band": age_band_for(rec.identity.age).value, "height_cm": rec.appearance.height_cm, "mass_kg": rec.appearance.mass_kg,
                        "special": rec.capability.special.model_dump(mode="json")}
            elif b.animal:
                an = canon.get(b.animal)
                vals = {"kind": "animal", "content_ref": b.animal, "sex": None, "age_years": None, "age_band": None,
                        "height_cm": an.height_cm, "mass_kg": an.mass_kg, "special": {}}
            else:
                t = canon.find("infected", b.infected)
                if t.alive:
                    raise ValueError(f"body {b.id}: {b.infected} is alive (a Lurker); Lurkers are people with dossiers")
                vals = {"kind": "infected", "content_ref": None, "sex": None, "age_years": None, "age_band": None, "height_cm": 170,
                        "mass_kg": 65, "special": {k: (v.lo + v.hi) // 2 for k, v in t.special.items()}}
            if b.id in looks_of_body:
                vals["looks"] = {**looks_of_body[b.id].model_dump(mode="json"), "outfit": []}
            if vals["kind"] == "infected":
                vals.update(grime=5, blood=3, gore=5)
            vals.update({"body_id": bid, "awareness": str(b.awareness), "posture": str(b.posture), "blood_loss_pct": b.blood_loss_pct,
                         "pain": b.pain, "impairment": 0, "restrained": 0, "progressed_at": start, "washed_at": start, "origin": "scenario", "alive": 1})
            ws = [W("bodies", vals),
                  W("needs", {"body_id": bid, "thirst_stage": b.needs.thirst, "hunger_stage": b.needs.hunger, "fatigue_stage": b.needs.fatigue,
                              "last_drink_ms": start - int(b.needs.thirst * N.thirst_stage_every_h * MS_PER_H),
                              "last_meal_ms": start - int(b.needs.hunger * N.hunger_stage_every_h * MS_PER_H),
                              "last_sleep_ms": start - int(b.needs.fatigue * N.fatigue_stage_every_h * MS_PER_H)})]
            ev = E(EventType.MATERIALIZE, "physical.bodies", ws, {"body_id": bid, "source": "scenario"}, target_ids=[bid])
            mat_ev[b.id] = ev.event_id
            wws = []
            for w in b.wounds:
                v = _wound_values(eff, w.anatomy, w.type, w.severity, 0, start, ev.event_id, w.treated)
                wws.append(W("wounds", {"wound_id": tx.mint("wnd"), "body_id": bid, **v}))
            if wws:
                pain = min(6, b.pain + sum(x.values["pain"] for x in wws))
                wws.append(W("bodies", {"pain": pain}, WriteOp.UPDATE, {"body_id": bid}))
                E(EventType.MATERIALIZE, "physical.bodies", wws, {"body_id": bid, "wounds": len(b.wounds)}, target_ids=[bid])
            imp = pbodies.impairment(tx, bid)
            if imp:
                E(EventType.IMPAIRMENT_CHANGE, "physical.bodies", [W("bodies", {"impairment": imp}, WriteOp.UPDATE, {"body_id": bid})], {"body_id": bid, "impairment": imp})
        # positions
        place_of = {}
        for b in spec.bodies:
            if b.anchor:
                a = tx.query_one("SELECT x_m, y_m FROM anchors WHERE anchor_id=?", (ids[b.anchor],))
                x, y = a[0], a[1]
            elif b.x is not None:
                x, y = b.x, b.y
            else:
                pl = tx.query_one("SELECT width_m, depth_m FROM places WHERE place_id=?", (ids[b.place],))
                x, y = pl[0] / 2, pl[1] / 2
            place_of[b.id] = ids[b.place]
            E(EventType.MOVE, "physical.space", [W("positions", {"body_id": ids[b.id], "place_id": ids[b.place], "anchor_id": I(b.anchor), "x_m": x, "y_m": y,
                                                                 "facing_deg": 0, "since_ms": start})],
              {"body_id": ids[b.id], "from_place": None, "to_place": ids[b.place], "from_anchor": None, "to_anchor": I(b.anchor), "x_m": x, "y_m": y},
              actor_id=ids[b.id], place_id=ids[b.place])
        # infected
        for b in spec.bodies:
            if b.infected:
                E(EventType.MATERIALIZE, "world.infected", [W("infected_state", {"body_id": ids[b.id], "type_id": b.infected, "states": [], "energy": 50, "quirks": []})],
                  {"body_id": ids[b.id], "type_id": b.infected})
        # actors
        actor_ev = {}
        for b in spec.bodies:
            if b.id not in doss:
                continue
            rec, source, ref = doss[b.id]
            bj = canonical_json(rec.model_dump(mode="json", by_alias=True))
            did = tx.mint("dos")
            sp = rec.capability.special
            rmax = resolve_max(sp.E, sp.C, rec.capability.resolve_trait_mod, eff.resolve)
            ws = [W("dossiers", {"dossier_id": did, "actor_id": ids[b.id], "source": source, "content_ref": ref, "baseline_json": bj,
                                 "content_hash": hashlib.sha256(bj.encode("utf-8")).hexdigest()}),
                  W("actors", {"actor_id": ids[b.id], "dossier_id": did, "controller": b.controller, "display_name": rec.identity.name,
                               "resolve_cur": b.resolve if b.resolve is not None else rmax, "resolve_max": rmax,
                               "goal_text": b.goal or (b.plan.goal if b.plan else ""), "duty_anchor": I(b.duty_anchor),
                               "accepted_authority": [ids[x] for x in b.accepted_authority]})]
            if b.plan:
                ws.append(W("plans", {"actor_id": ids[b.id], "goal_text": b.plan.goal, "steps": b.plan.steps,
                                      "standing_orders": [so.model_dump() for so in b.plan.standing_orders], "updated_at": start}))
            ev = E(EventType.MATERIALIZE, "mind.actor", ws, {"actor_id": ids[b.id], "source": source}, target_ids=[ids[b.id]])
            actor_ev[b.id] = ev.event_id
        # items
        for b, it, iid in item_ids:
            if it.container:
                to = pobjects.Holder("container", ids[it.container])
            else:
                to = pobjects.Holder("body", ids[b.id], it.slot or "pack")
            pobjects._create_with_id(tx, iid, it.item, it.qty, to, "scenario", it.props, start, None, 0, event_origin="system", condition=it.condition)
        for it, iid in loose_ids:
            if it.container:
                to = pobjects.Holder("container", ids[it.container])
            else:
                to = pobjects.Holder("place", ids[it.place], anchor_id=I(it.anchor))
            pobjects._create_with_id(tx, iid, it.item, it.qty, to, "scenario", it.props, start, None, 0, event_origin="system", condition=it.condition)
        for b in spec.bodies:
            if b.dress:
                has = any(canon.get(it.item).clothing is not None and it.slot == "worn" and not it.container for it in b.inventory)
                if not has:
                    pobjects.dress(tx, ids[b.id], looks_of_body[b.id].outfit, start, None, 0, "scenario")
        # tasks
        for b, tid in task_ids:
            t = b.task
            E(EventType.TASK_STEP, "action.tasks", [W("tasks", {"task_id": tid, "actor_id": ids[b.id], "kind": t.kind, "label": t.label,
                "steps_total": t.steps_total, "steps_done": t.steps_done, "step_s": t.step_s,
                "started_at": start - int(t.steps_done * t.step_s * MS_PER_S), "next_due_at": start + int(t.step_s * MS_PER_S),
                "interrupt_on": t.interrupt_on, "target_ids": [ids[x] for x in t.targets], "status": "active", "focus": int(b.focus)})],
              {"task_id": tid, "actor_id": ids[b.id], "kind": t.kind, "label": t.label, "steps_done": t.steps_done,
               "steps_total": t.steps_total, "status": "active", "seed": True}, actor_id=ids[b.id])
        # relationships
        for r in spec.relationships:
            axes = {k: getattr(r, k) for k in ("trust", "fear", "respect", "affection", "resentment", "obligation")}
            E(EventType.RELATION_CHANGE, "mind.mind", [W("relationships", {"from_id": ids[r.from_], "to_id": ids[r.to], "kind": r.kind, **axes,
                                                                          "causes": {}, "updated_at": start})],
              {"from_id": ids[r.from_], "to_id": ids[r.to], "kind": r.kind, "axes": axes, "seed": True})
        # perception seeds per holder
        body_by_local = {b.id: b for b in spec.bodies}
        holders = [b.id for b in spec.bodies if b.id in doss]
        for h in holders:
            ws = []
            # known places
            here = ids[body_by_local[h].place]
            known = {here: 1}
            for r in tx.query("SELECT place_a, place_b, kind FROM portals WHERE (place_a=? OR place_b=?) AND kind NOT IN ('wall','fence') ORDER BY portal_id", (here, here)):
                o = r[1] if r[0] == here else r[0]
                known.setdefault(o, 0)
            for pl, vis in known.items():
                ws.append(W("known_places", {"holder_id": ids[h], "place_id": pl, "first_seen": start, "last_seen": start, "visited": vis}))
            for k in spec.knows:
                if k.holder != h:
                    continue
                if k.description:
                    desc = k.description
                else:
                    srec = doss[k.subject][0] if k.subject in doss else None
                    if srec is None:
                        desc = "infected"
                    else:
                        from ..mind.perception import describe_dossier
                        desc = describe_dossier(srec.model_dump(mode="json", by_alias=True))
                ws.append(W("acquaintance", {"holder_id": ids[h], "subject_id": ids[k.subject], "known_name": k.name, "description": desc,
                                             "first_met": start, "last_seen": start, "last_seen_place": place_of[k.subject]}))
            beliefs = [bl for bl in spec.beliefs if bl.holder == h]
            claim_links = []
            for bl in beliefs:
                pid = tx.mint("prp")
                cid = None
                if bl.true_in_world:
                    cid = tx.mint("clm")
                    subj = ids.get(bl.subject) if bl.subject else None
                    E(EventType.MATERIALIZE, "kernel.truth", [fact_write(cid, bl.subject_type, subj or "", bl.predicate, bl.text, start, "scenario")],
                      {"claim_id": cid, "source": "scenario"})
                prov = bl.provenance
                if prov.startswith("told_by:"):
                    prov = "told_by:" + ids[prov.split(":", 1)[1]]
                claim_links.append((pid, cid, bl, prov))
            for pid, cid, bl, prov in claim_links:
                ws.append(W("propositions", {"prop_id": pid, "subject_type": bl.subject_type, "subject_id": ids.get(bl.subject) if bl.subject else None,
                                             "predicate": bl.predicate, "text": bl.text, "matches_claim": cid, "created_event": "scenario",
                                             "object_value": ids.get(bl.value, bl.value) if bl.value is not None else None}))
            if ws or claim_links:
                ev = tx.commit_event(Event(type=EventType.PERCEIVE, writer="mind.perception", at=start, turn_index=0, origin="system",
                                           writes=ws, payload={"holder_id": ids[h], "seed": True}))
                hw = []
                for pid, cid, bl, prov in claim_links:
                    hw.append(W("claim_holdings", {"holder_id": ids[h], "claim_id": pid, "believed": int(bl.believed), "confidence": bl.confidence,
                                                   "provenance": prov, "fidelity": "exact", "acquired_at": start, "acquired_via": ev.event_id}))
                if hw:
                    E(EventType.PERCEIVE, "mind.perception", hw, {"holder_id": ids[h], "seed": True, "beliefs": len(hw)})
        # lessons
        for b in spec.bodies:
            if b.id not in doss:
                continue
            cues = list(doss[b.id][0].knowledge.cues) + list(b.cues)
            if not cues:
                continue
            ws = []
            for c in cues:
                cd = canon.find("cue", c)
                ws.append(W("lessons", {"lesson_id": tx.mint("lsn"), "holder_id": ids[b.id], "cue_tags": [c], "text": f"Knows: {cd.description}",
                                        "confidence": 3, "source_event": actor_ev[b.id], "at": start}))
            E(EventType.LESSON_LEARNED, "mind.mind", ws, {"holder_id": ids[b.id], "cues": cues, "seed": True})
        # households
        for h in spec.households:
            hid = tx.mint("hh")
            ids[h.id] = hid
            ws = [W("households", {"household_id": hid, "dwelling_place": I(h.dwelling), "shared_stores": {}, "grief_state": 0, "settlement_id": None})]
            for m in h.members:
                ws.append(W("household_members", {"household_id": hid, "actor_id": ids[m.actor], "role": m.role, "guardian_of": [ids[g] for g in m.guardian_of],
                                                  "protection_priority": 0}))
            E(EventType.HOUSEHOLD_CHANGE, "society.household", ws, {"household_id": hid, "seed": True})
        for g in spec.groups:
            gid = tx.mint("grp")
            ids[g.id] = gid
            ws = [W("groups", {"group_id": gid, "kind": g.kind, "name": g.name, "content_ref": g.content_ref, "doctrine": {}, "cohesion": 5, "morale": 5})]
            for m in g.members:
                ws.append(W("group_members", {"group_id": gid, "actor_id": ids[m.actor], "role": m.role, "standing": m.standing, "since": start, "status": "member"}))
            for k, v in g.standing_toward.items():
                ws.append(W("group_standing", {"group_id": gid, "actor_id": ids[k], "standing": v, "reasons": []}))
            E(EventType.MATERIALIZE, "society.group", ws, {"group_id": gid, "seed": True})
        for s in spec.settlements:
            sid = tx.mint("stl")
            ids[s.id] = sid
            ws = [W("settlements", {"settlement_id": sid, "name": s.name, "place_id": ids[s.place], "group_id": I(s.group), "stores": s.stores,
                                    "morale": s.morale, "cohesion": s.cohesion, "ration_level": s.ration_level, "shortages": [], "vacancies": []})]
            for l in s.laws:
                ws.append(W("laws_active", {"settlement_id": sid, "law_ref": l, "since": start}))
            E(EventType.MATERIALIZE, "society.settlement", ws, {"settlement_id": sid, "seed": True})
        for wpk in spec.workplaces:
            wid = tx.mint("wkp")
            ids[wpk.id] = wid
            due = _clock_ms(wpk.first_cycle_at, start) if wpk.first_cycle_at else start + int(wpk.cycle_h * MS_PER_H)
            ws = [W("workplaces", {"workplace_id": wid, "settlement_id": ids[wpk.settlement], "place_id": ids[wpk.place], "site_type": wpk.site_type,
                                   "inputs": wpk.inputs, "outputs": wpk.outputs, "cycle_h": wpk.cycle_h, "required_roles": wpk.required_roles,
                                   "machinery_condition": wpk.machinery_condition, "efficiency": wpk.efficiency, "stall_reasons": [], "next_due_at": due})]
            for a in wpk.assignments:
                ws.append(W("work_assignments", {"workplace_id": wid, "actor_id": ids[a.actor], "role": a.role, "shift_start_hh": a.shift_start_hh,
                                                 "shift_end_hh": a.shift_end_hh, "covering_for": None}))
            E(EventType.MATERIALIZE, "society.work", ws, {"workplace_id": wid, "seed": True})
        for d in spec.events_due:
            due = _clock_ms(d.at, start)
            payload = dict(d.payload)
            if d.place:
                payload["place_id"] = ids[d.place]
            if d.anchor:
                payload["anchor_id"] = ids[d.anchor]
            kclock.schedule(tx, due, d.type, I(d.subject), payload, None, event_origin="system")
        if spec.narrator_state:
            st = NarratorStyle.model_validate({**NarratorStyle().model_dump(mode="json"), **spec.narrator_state})
            E(EventType.SETTINGS_CHANGE, "narration.narrator", [W("narrator_state", {"style_json": canonical_json(st.model_dump(mode="json"))}, WriteOp.UPDATE, {"id": 1})], {"source": "scenario"})
        pc = ids[humans[0].id]
        E(EventType.PC_CONTROL_CHANGE, "kernel.meta", [W("meta", {"value": pc}, WriteOp.UPDATE, {"key": "pc_actor_id"})], {"pc_actor_id": pc})
    cfg = EngineConfig().model_copy(update={"rules": eff})
    tr = transport or FakeTransport()
    return ScenarioWorld(name=spec.name, store=store, canon=canon, rng=rng, config=cfg, transport=tr,
                         client=LaneClient(cfg, tr), pc_id=ids[humans[0].id], spec=spec, ids=ids)
