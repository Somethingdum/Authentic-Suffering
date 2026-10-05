"""Implementation: mind.packet.build_packet."""
from __future__ import annotations

import json

from ..contracts.common import ANATOMY_WORDS, LOD, SEVERITY_WORDS, CallClass, Channel, Fidelity, Standing
from ..contracts.mind import (AffordanceOption, BeliefLine, Commitments, LoopLine, PacketEntity, PerceivedItem,
                              RelationshipLine, SkullPacket, Stakes, UtteranceView)


def _row(s, sql, p=()):
    r = s.query_one(sql, p)
    return dict(r) if r is not None else None


def _cap(s):
    return s[:1].upper() + s[1:]


def _sp(s):
    return s.replace("_", " ")


_PROV = {"witnessed": "you saw it", "overheard": "you overheard it", "common": "everyone says so",
         "childhood": "since you were small", "rumour": "a rumour", "inferred": "your own guess",
         "group": "your people say so"}                                     # D-130


def _age(ms):
    s = ms / 1000
    if s < 60:
        return "just now"
    if s < 3600:
        n = int(s // 60)
        return f"{n} minute{'s' if n != 1 else ''} ago"
    if s < 86400:
        n = int(s // 3600)
        return f"{n} hour{'s' if n != 1 else ''} ago"
    n = int(s // 86400)
    return f"{n} day{'s' if n != 1 else ''} ago"


def known_elsewhere(tx, holder, listed):
    """SKULL-11 (D-153): people the holder knows by name, not yet listed and not seen dead — last seen first."""
    out = []
    for r in tx.query("SELECT a.subject_id, b.alive, b.dead_at FROM acquaintance a JOIN bodies b ON b.body_id = a.subject_id WHERE "
                      "a.holder_id=? AND a.known_name IS NOT NULL AND a.subject_id != ? ORDER BY a.last_seen DESC, a.subject_id",
                      (holder, holder)):
        if len(out) >= tx.rules.packet.max_known_elsewhere:
            break
        if r[0] in listed or (not r[1] and r[2] is not None and tx.query_one(      # D-224: only the dead were seen dead —
                "SELECT 1 FROM events e WHERE e.at=? AND +e.type='DEATH' AND json_extract(e.payload,'$.body_id')=? AND EXISTS "
                "(SELECT 1 FROM percept_log p WHERE p.event_id=e.event_id AND p.holder_id=?) LIMIT 1",   # their death, by its time
                (r[2], r[0], holder)) is not None):
            continue
        out.append(r[0])
    return out


def whereabouts(tx, holder, body, rows, at):
    """PacketEntity.whereabouts (mind.packet; Actor Spec AC14)."""
    from .perception import place_phrase
    mine = [p for p in rows if p["source_id"] == body]
    for p in mine:
        det = json.loads(p["detail"]) if isinstance(p["detail"], str) else (p["detail"] or {})
        if p["channel"] == "visual" and det.get("level") in ("clear", "partial"):
            return "here"
    if any(p["channel"] in ("auditory", "speech") for p in mine):
        return "heard, not seen"
    a = _row(tx, "SELECT last_seen, last_seen_place FROM acquaintance WHERE holder_id=? AND subject_id=?", (holder, body))
    if a and a["last_seen"] is not None and a["last_seen_place"]:
        pl = _row(tx, "SELECT name FROM places WHERE place_id=?", (a["last_seen_place"],))
        if pl:
            return f"last seen in {place_phrase(pl['name'])} {_age(at - a['last_seen'])}"
    return "not seen"


def seen_appearance(tx, holder, body, rows, at):
    """PacketEntity.appearance (F1a LOOK-06)."""
    import json as _j
    from ..physical.space import point_distance
    from .perception import appearance_text
    best = None
    for p in rows:
        if p["source_id"] != body or p["channel"] != "visual":
            continue
        det = _j.loads(p["detail"]) if isinstance(p["detail"], str) else (p["detail"] or {})
        lv = det.get("level")
        if lv == "clear" or (lv == "partial" and best is None):
            best = lv
    if best is None:
        return ""
    from .perception import smell_text
    d = point_distance(tx, holder, body)
    parts = [appearance_text(tx, holder, body, best, 999.0 if d is None else d), smell_text(tx, holder, body, at)]
    return " ".join(x for x in parts if x)


def cut_heard(words, limit):
    if len(words) <= limit:
        return words
    head = words[:limit]
    sp = head.rfind(" ")
    return (head[:sp] if sp > 0 else head) + " …"


def _has_timepiece(tx, actor_id):
    from ..physical.objects import inventory_tree
    canon = tx.canon if getattr(tx, "canon", None) is not None else tx.store.canon

    def walk(nodes):
        for n in nodes:
            if "timepiece" in canon.get(n["def_ref"]).tags or walk(n["contents"]):
                return True
        return False
    return walk(inventory_tree(tx, actor_id))


def _name_or_desc(tx, holder, body):
    from .perception import describe, with_article
    r = _row(tx, "SELECT known_name FROM acquaintance WHERE holder_id=? AND subject_id=?", (holder, body))
    if r and r["known_name"]:
        return r["known_name"]
    return with_article(describe(tx, holder, body))


REL_WORDS = {                                                     # D-165: how much, not only which way
    "trust": {3: "you would trust them with your life", 2: "you trust them", 1: "you mostly trust them",
              -1: "you are wary of them", -2: "you distrust them", -3: "you do not trust them at all"},
    "fear": {1: "they make you uneasy", 2: "you fear them", 3: "you are terrified of them"},
    "respect": {1: "you think well of them", 2: "you respect them", 3: "you look up to them",
                -1: "you think little of them", -2: "you look down on them", -3: "you despise them"},
    "affection": {1: "you like them", 2: "you care about them", 3: "you love them",
                  -1: "you dislike them", -2: "you can't stand them", -3: "you hate them"},
    "resentment": {1: "something they did still rankles", 2: "you resent them", 3: "you will not forgive them"},
    "obligation": {1: "you owe them", 2: "you owe them a great deal", 3: "you owe them your life",
                   -1: "they owe you", -2: "they owe you a great deal", -3: "they owe you their life"},
}


def _rel_text(r):
    parts = []
    for axis, words in REL_WORDS.items():
        v = max(-3, min(3, int(r[axis] or 0)))
        if v:
            parts.append(words[v])
    return _cap("; ".join(parts)) + "." if parts else "No strong feelings."


def _body_lines(tx, actor_id):
    from ..physical.bodies import effective_bleed, grips_on, tied
    from .perception import word_for
    H = tx.rules.harm
    out = [f"{_cap(word_for(tx, actor_id, h))} has hold of you." for h in grips_on(tx, actor_id)]   # D-208
    if tied(tx, actor_id):
        out.append("Your hands and feet are tied.")
    for w in tx.query("SELECT * FROM wounds WHERE body_id=? AND healed_at IS NULL ORDER BY created_at, wound_id", (actor_id,)):
        bleed = ", bleeding" if effective_bleed(tx, w["wound_id"]) > 0 else ""
        out.append(f"{_cap(SEVERITY_WORDS[w['severity']])} {w['type']} wound to your {ANATOMY_WORDS[w['anatomy']]}{bleed}.")
    b = _row(tx, "SELECT pain, blood_loss_pct, impairment FROM bodies WHERE body_id=?", (actor_id,))
    if 1 <= b["pain"] <= 2: out.append("It hurts.")
    elif 3 <= b["pain"] <= 4: out.append("The pain is bad.")
    elif b["pain"] >= 5: out.append("The pain is almost more than you can take.")
    th = sorted(t for t, _ in H.impairment_from_blood_loss)
    if len(th) >= 2 and b["blood_loss_pct"] >= th[1]:
        out.append("You have lost a lot of blood and feel light-headed.")
    elif th and b["blood_loss_pct"] >= th[0]:
        out.append("You have lost some blood.")
    n = _row(tx, "SELECT * FROM needs WHERE body_id=?", (actor_id,))
    if n:
        for col, mild, strong in (("thirst_stage", "You are thirsty.", "You are desperately thirsty."),
                                  ("hunger_stage", "You are hungry.", "You are starving."),
                                  ("fatigue_stage", "You are tired.", "You are exhausted.")):
            if 2 <= n[col] <= 3: out.append(mild)
            elif n[col] >= 4: out.append(strong)
    out += _f1c_lines(tx, actor_id)
    i = b["impairment"]
    if 1 <= i <= 2: out.append("Everything is harder than it should be.")
    elif 3 <= i <= 4: out.append("You are struggling to function.")
    elif i >= 5: out.append("You can barely function.")
    from ..physical.bodies import mind_of, stages
    out += [st.felt for _pw, st in stages(tx, actor_id) if st.felt]
    m = mind_of(tx, actor_id)
    if m is not None:   # D-107
        from .packet import MIND_LINES
        out.append(MIND_LINES[m])
    out = out or ["Unhurt."]
    st = _row(tx, "SELECT stress FROM actors WHERE actor_id=?", (actor_id,))
    s = st["stress"] if st else 0
    if 7 <= s <= 8:
        out.append("You are close to breaking.")
    elif s >= 9:
        out.append("You are at the end of your rope.")
    return out


def _temper_feeling(tx, holder, body, at):
    import json as _j
    from . import temper
    h = temper.heat(tx, holder, body, at)
    th = temper.threshold(tx, holder)
    if h >= th:
        return "you are furious with them"
    if 0 < h and h >= th // 2:
        return "they are getting under your skin"
    lk = tx.query_one("SELECT last_kind FROM tempers WHERE holder_id=? AND toward_id=?", (holder, body))
    if lk is not None and lk[0] == "wish_forgiven":                                          # TEMPER-10
        return ("they asked you for a wonder as if you were a genie; you let it pass this once — tell them, "
                "seriously and without harm, never again")
    for r in tx.query("SELECT subject_ids FROM open_loops WHERE holder_id=? AND kind='grudge' AND status='open'", (holder,)):
        if body in _j.loads(r[0]):
            return "you hold a grudge against them"
    return ""


def _outburst_line(tx, holder, ph, at):
    import json as _j
    r = tx.query_one("SELECT payload FROM events WHERE type='INVOLUNTARY' AND actor_id=? AND at=? "
                     "AND json_extract(payload,'$.kind')='outburst' ORDER BY seq DESC LIMIT 1", (holder, at))
    if r is None:
        return None
    pl = _j.loads(r[0])
    if pl.get("outlet") != "words" or pl.get("toward_id") not in ph:
        return None
    return f"You snap. You are going to have it out with {ph[pl['toward_id']]} — now, to their face."


_RANK = {1: "trained", 2: "skilled", 3: "expert"}


def _resources(tx, actor_id):
    from ..physical.objects import inventory_tree
    from .perception import thing_phrase, with_article
    parts = []

    def walk(node, container=None):
        p = with_article(node["name"]) if node["qty"] == 1 else f"{node['qty']} {node['name']}"
        if node["slot"] == "hand_r": p += " (in your right hand)"
        if node["slot"] == "hand_l": p += " (in your left hand)"
        if node["props"].get("holstered"): p += " (holstered)"
        if container is not None: p += f" (in {thing_phrase(container)})"
        parts.append(p)
        for c in node["contents"]:
            walk(c, node["name"])
    for n in inventory_tree(tx, actor_id):
        walk(n)
    return [f"You have: {', '.join(parts)}."] if parts else []


def _assemble(tx, actor_id, lod, affordances, turn_index, at, reaction=False, consulted=None):
    from ..kernel.clock import format_clock, world_time
    from .actor import fused, recent_lines
    from .identity import compile_identity
    from .firewall import classify_form, classify_standing, effective_form
    from .perception import at_phrase, place_phrase, thing_phrase
    from .memory import unprocessed
    if lod == LOD.COLD:
        raise ValueError("COLD actors get no packet")
    unprocessed_raw = unprocessed(tx, actor_id)
    if not affordances.options:
        raise ValueError("empty affordance set")
    PR = tx.rules.packet
    d = fused(tx, actor_id)
    act = _row(tx, "SELECT * FROM actors WHERE actor_id=?", (actor_id,))
    handles = {}
    percepts = [dict(r) for r in tx.query("SELECT * FROM percept_log WHERE holder_id=? AND turn_index=? AND at<=? "
                                          "ORDER BY at, percept_id", (actor_id, turn_index, at))]   # SKULL-10
    scene_at = max((p["at"] for p in percepts if str(p["event_id"]).startswith("scene:")), default=None)
    percepts = [p for p in percepts if not str(p["event_id"]).startswith("scene:") or p["at"] == scene_at]
    body_ids = {r[0] for r in tx.query("SELECT body_id FROM bodies")}
    ents = []

    def add(b):
        if b and b != actor_id and b in body_ids and b not in ents:
            ents.append(b)
    for p in percepts:
        add(p["source_id"])
    present = set(ents)
    rels = {r["to_id"]: dict(r) for r in tx.query("SELECT * FROM relationships WHERE from_id=? ORDER BY to_id", (actor_id,))}
    for t in rels:
        add(t)
    hh = [r[0] for r in tx.query("SELECT household_id FROM household_members WHERE actor_id=?", (actor_id,))]
    for h in hh:
        for r in tx.query("SELECT actor_id FROM household_members WHERE household_id=? ORDER BY actor_id", (h,)):
            add(r[0])
    for b in known_elsewhere(tx, actor_id, set(ents)):              # SKULL-11 (D-153)
        add(b)
    ph = {}
    entities = []
    for i, b in enumerate(ents, 1):
        h = f"P{i}"
        ph[b] = h
        handles[h] = b
        kn = _row(tx, "SELECT known_name FROM acquaintance WHERE holder_id=? AND subject_id=?", (actor_id, b))
        kn = kn["known_name"] if kn else None
        rs = rels.get(b)
        entities.append(PacketEntity(handle=h, description=kn or _name_or_desc(tx, actor_id, b), known_name=kn,
                                     relation_summary=f"your {_sp(rs['kind'])}" if rs and rs["kind"] != "acquaintance" else None,
                                     whereabouts=whereabouts(tx, actor_id, b, percepts, at),
                                     appearance=seen_appearance(tx, actor_id, b, percepts, at),
                                     feeling=_temper_feeling(tx, actor_id, b, at)))
    perceived, utts, unc = [], [], []
    for i, p in enumerate(percepts, 1):
        h = f"S{i}"
        handles[h] = p["percept_id"]
        det = json.loads(p["detail"]) if isinstance(p["detail"], str) else (p["detail"] or {})
        if p["fidelity"] in ("partial", "tone_only"):                  # D-158: a sighting is made out, a sound caught
            unc.append(f"You could not make out all of {h}." if p["channel"] == "visual" else f"You did not catch all of {h}.")
        if p["channel"] == "speech":
            words = det.get("words", "")
            st = classify_standing(tx, p["source_id"], actor_id, words) if p["source_id"] else Standing.STRANGER
            form = effective_form(classify_form(words, weapon_pointed_at_receiver=bool(det.get("armed_at_me"))), st)
            utts.append(UtteranceView(handle=h, speaker_handle=ph.get(p["source_id"]), words=cut_heard(words, PR.max_heard_chars),
                                      fidelity=p["fidelity"],
                                      form=form, standing=st, addressed_to_me=bool(det.get("addressed_to_me")),
                                      volume=det.get("volume", "normal")))
        else:
            perceived.append(PerceivedItem(handle=h, channel=p["channel"], fidelity=p["fidelity"], text=p["text"],
                                           source_handle=ph.get(p["source_id"]), seconds_ago=(at - p["at"]) / 1000))
    rel_lines = [RelationshipLine(handle=ph[b], text=_rel_text(rels[b])) for b in ents if b in rels]
    from .retrieval import retrieve
    from ..contracts.mind import MemoryLine
    R = retrieve(tx, actor_id, turn_index, at, max_beliefs=PR.max_beliefs, max_memories=PR.max_memories, max_loops=PR.max_open_loops)
    beliefs = []
    for r in R.beliefs:
        prov = r["provenance"]
        if prov.startswith("told_by:"):
            pt = f"{_name_or_desc(tx, actor_id, prov.split(':', 1)[1])} told you"
        elif prov.startswith("read:"):
            pt = "you read it"
        elif prov.startswith("rumour"):
            pt = "a rumour"
        else:
            pt = _PROV.get(prov, "you are not sure where from")
        beliefs.append(BeliefLine(text=r["text"], confidence=r["confidence"], provenance_text=pt, age_text=_age(at - r["acquired_at"])))
    loops = []
    for i, r in enumerate(R.loops, 1):
        handles[f"L{i}"] = r["loop_id"]
        from .promise import suffix as _psuffix
        loops.append(LoopLine(handle=f"L{i}", kind=r["kind"], text=r["text"] + _psuffix(tx, r["loop_id"])))
    memories = []
    for i, e in enumerate(R.episodes, 1):
        handles[f"E{i}"] = e["episode_id"]
        memories.append(MemoryLine(handle=f"E{i}", text=e["summary"], age_text=_age(at - e["at"])))
    lessons = [f"Experience taught you: {l['text']}" for l in R.lessons]
    lore = [f"{r['text']} ({_PROV.get(r['provenance'], 'everyone says so')})" for r in R.lore]     # D-130 (LORE-03)
    refusal_rows = [{"request_summary": r["summary"], "created_at": r["created_at"], "requester_id": r["requester_id"]}
                    for r in R.refusals]
    task = None
    if act["current_task"]:
        task = _row(tx, "SELECT * FROM tasks WHERE task_id=?", (act["current_task"],))
    if task is None:
        task = _row(tx, "SELECT * FROM tasks WHERE actor_id=? AND status='active' ORDER BY started_at, task_id", (actor_id,))
    put_down = False
    if task is None:                                   # D-118: the work put down last is still theirs to pick up
        from ..action.tasks import put_down
        task = put_down(tx, actor_id)
        put_down = task is not None
    plan = _row(tx, "SELECT * FROM plans WHERE actor_id=?", (actor_id,))
    steps = json.loads(plan["steps"]) if plan else []
    orders = json.loads(plan["standing_orders"]) if plan else []
    com = Commitments(current_task=(f"{task['label']} ({task['steps_done']} of {task['steps_total']} done"
                                    + (", put down for now)" if put_down else ")")) if task else None,
                      plan_step=steps[0] if steps else None,
                      standing_orders=[f"On {_sp(o['trigger'])}: {o['response']}." for o in orders])
    deps = []
    srcs = {p["source_id"] for p in percepts}
    for h in hh:
        g = _row(tx, "SELECT guardian_of FROM household_members WHERE household_id=? AND actor_id=?", (h, actor_id))
        for dep in json.loads(g["guardian_of"]):
            deps.append(f"{_name_or_desc(tx, actor_id, dep)} ({'near you' if dep in srcs else 'not with you'})")
    obl = [r["text"] for r in tx.query("SELECT text FROM open_loops WHERE holder_id=? AND status='open' AND kind IN ('promise_made','debt_owing') ORDER BY created_at, loop_id", (actor_id,))]
    stakes = Stakes(dependents=deps, obligations=obl, would_lose=[])
    resources = _resources(tx, actor_id)
    if any(u.addressed_to_me for u in utts):
        if com.current_task is None:
            com = com.model_copy(update={"current_task": "You are not in the middle of anything."})
        if not stakes.would_lose:
            stakes = stakes.model_copy(update={"would_lose": ["Nothing you can name."]})
        if not resources:
            resources = ["You carry nothing."]
    opts = []
    extra = list(consulted.options) if consulted is not None else []
    for i, o in enumerate(list(affordances.options) + extra, 1):
        handles[f"A{i}"] = o.signature
        opts.append(AffordanceOption(handle=f"A{i}", verb=o.verb, label=o.label, cost_note=o.cost_note, risk_note=o.risk_note))
    if reaction or consulted is not None:
        fams, kinds = [], []
    else:
        from .consult import families as _families
        fams = _families(affordances, {d.id: d for d in tx.canon.all("affordance")})
        kinds = ["recall"] + (["more_actions"] if fams else [])
    pos = _row(tx, "SELECT * FROM positions WHERE body_id=?", (actor_id,))
    place = _row(tx, "SELECT name FROM places WHERE place_id=?", (pos["place_id"],))["name"]
    if pos["anchor_id"]:
        an = _row(tx, "SELECT name FROM anchors WHERE anchor_id=?", (pos["anchor_id"],))["name"]
        position = f"{at_phrase(an)} in {place_phrase(place)}"
    else:
        position = f"in {place_phrase(place)}"
    from ..contracts.mind import ExpressionOption
    from ..physical.bodies import capacity as _cap_of
    hf = _cap_of(tx, actor_id).hands_free
    gests, pts = [], []
    if not reaction:
        from ..action.effects import GESTURES
        here = [e for e in entities if e.whereabouts == "here"]
        gi = 0
        for gid, g in GESTURES.items():
            if g.hands > hf:
                continue
            targets = [(handles[e.handle], e.description) for e in here][:3] if g.targeted else [(None, None)]
            for bid, desc in targets:
                gi += 1
                handles[f"G{gi}"] = f"{gid}:{bid or '*'}"
                gests.append(ExpressionOption(handle=f"G{gi}", label=g.label.format(target=desc) if g.targeted else g.label,
                                              hands=g.hands))
        fi = 0
        for e in here:
            fi += 1
            handles[f"F{fi}"] = handles[e.handle]
            pts.append(ExpressionOption(handle=f"F{fi}", label=f"Keep your eyes on {e.description}"))
        seen_portals = sorted({p["source_id"] for p in percepts if p["channel"] == "visual" and str(p["source_id"] or "").startswith("prt_")})
        for pid in seen_portals:
            pr = _row(tx, "SELECT name, place_a, place_b FROM portals WHERE portal_id=?", (pid,))
            if pr is None or pos["place_id"] not in (pr["place_a"], pr["place_b"]):
                continue
            fi += 1
            handles[f"F{fi}"] = pid
            pts.append(ExpressionOption(handle=f"F{fi}", label=f"Watch {thing_phrase(pr['name'])}"))   # D-237
    wt = world_time(at)
    fields = dict(
        actor_id=actor_id, turn_index=turn_index, lod=lod,
        world_time_text=(f"{format_clock(at)}, day {wt.day} since the Fall ({wt.part_of_day})" if _has_timepiece(tx, actor_id)
                         else f"Day {wt.day} since the Fall ({wt.part_of_day})"),
        identity=compile_identity(d, minimum=reaction), recent_lines=recent_lines(tx, actor_id, PR.max_recent_lines),
        body_lines=_body_lines(tx, actor_id),
        resolve_cur=act["resolve_cur"], resolve_max=act["resolve_max"], position_text=position,
        perceived_now=perceived, utterances=utts, entities=entities, beliefs=beliefs, relationships=rel_lines,
        memories=memories, lessons=lessons, lore=lore, open_loops=loops, refusals=[f"You refused: {r['request_summary']}." for r in refusal_rows],
        commitments=com, stakes=stakes, resources=resources,
        affordances=opts, uncertainty=unc, handles=handles, gestures=gests, attention_points=pts, hands_free=hf,
        unprocessed=[t for _tix, lines in unprocessed_raw for t in lines],
        families=fams, consult_kinds=kinds, looked_up=list(consulted.lines) if consulted is not None else [],
        outburst=_outburst_line(tx, actor_id, ph, at), portrayal_note=_portrayal_note(tx, actor_id, turn_index),
        voice_examples=choose_examples(d.voice.examples, reaction=reaction, rules=PR),
        thread=thread_lines(tx, actor_id, turn_index, at, lambda b: ph.get(b) or _name_or_desc(tx, actor_id, b), PR))
    return fields, present, refusal_rows, unprocessed_raw


def _portrayal_note(tx, actor_id, turn_index):
    from ..audit.portrayal import note_for
    return note_for(tx, actor_id, turn_index)


def _tokens(packet, reaction):
    from ..prompts.render import render
    from .packet import estimate_tokens
    msgs = render(CallClass.ACTOR_REACTION if reaction else CallClass.ACTOR_COGNITION, p=packet)
    return estimate_tokens(msgs[0].content + "\n" + msgs[1].content)


def build_packet(tx, actor_id, lod, affordances, turn_index, at, *, reaction=False, consulted=None):
    f, present, refusal_rows, unprocessed_raw = _assemble(tx, actor_id, LOD(lod), affordances, turn_index, at, reaction, consulted)
    budget = tx.rules.packet.token_budget["reaction" if reaction else LOD(lod).value]
    f["omitted"] = []
    # SKULL-09 (B5b): the raw lines of every unsettled turn but the latest may go, oldest first
    older_left = sum(len(lines) for _t, lines in unprocessed_raw[:-1])
    pkt = SkullPacket(**f)
    # AC16: a refusal of someone here or speaking now is pinned, whatever its age
    old = [i for i, r in enumerate(refusal_rows) if r["created_at"] < at - 7 * 86_400_000 and r["requester_id"] not in present]
    alive = list(range(len(refusal_rows)))
    while _tokens(pkt, reaction) > budget:
        om = f["omitted"]
        if f["voice_examples"]:                       # D-116: how someone sounds gives way first
            om.append(f"example: {f['voice_examples'][-1].they_say}")
            f["voice_examples"] = f["voice_examples"][:-1]
        elif f["memories"]:
            om.append(f"memory: {f['memories'][-1].text}")
            f["memories"] = f["memories"][:-1]
        elif f["lessons"]:
            om.append(f"lesson: {f['lessons'][-1]}")
            f["lessons"] = f["lessons"][:-1]
        elif f["thread"]:                             # D-117: the oldest of what was said here goes next
            om.append(f"thread: {f['thread'][0].words}")
            f["thread"] = f["thread"][1:]
        elif f["beliefs"]:
            om.append(f"belief: {f['beliefs'][-1].text}")
            f["beliefs"] = f["beliefs"][:-1]
        elif any(f["handles"][r.handle] not in present for r in f["relationships"]):
            idx = max(i for i, r in enumerate(f["relationships"]) if f["handles"][r.handle] not in present)
            r = f["relationships"][idx]
            om.append(f"relationship: {r.handle}: {r.text}")
            f["relationships"] = f["relationships"][:idx] + f["relationships"][idx + 1:]
        elif old:
            i = old.pop(0)
            alive.remove(i)
            om.append(f"refusal: You refused: {refusal_rows[i]['request_summary']}.")
            f["refusals"] = [f"You refused: {refusal_rows[k]['request_summary']}." for k in alive]
        elif older_left:
            om.append(f"unprocessed: {f['unprocessed'][0]}")
            f["unprocessed"] = f["unprocessed"][1:]
            older_left -= 1
        elif f["uncertainty"]:
            om.append(f"uncertainty: {f['uncertainty'][-1]}")
            f["uncertainty"] = f["uncertainty"][:-1]
        else:
            break
        pkt = SkullPacket(**f)
    return pkt


def thread_lines(tx, holder_id, turn_index, at, names, rules):
    from ..contracts.common import UtteranceForm
    from ..contracts.mind import ThreadLine
    from .firewall import classify_form
    since = at - rules.thread_window_min * 60_000
    moved = tx.query_one("SELECT MAX(at) FROM events WHERE type='MOVE' AND actor_id=? AND "
                         "json_extract(payload, '$.to_place') IS NOT json_extract(payload, '$.from_place')", (holder_id,))
    if moved and moved[0] is not None:
        since = max(since, moved[0])
    rows = []
    for r in tx.query("SELECT p.percept_id, p.at, p.fidelity, p.source_id, p.detail, "
                      "(SELECT seq FROM events e WHERE e.event_id = p.event_id) AS seq FROM percept_log p "
                      "WHERE p.holder_id=? AND p.channel='speech' AND p.turn_index<? AND p.at>=? AND p.at<=? "
                      "AND (p.source_id IS NULL OR p.source_id<>?)", (holder_id, turn_index, since, at, holder_id)):
        det = json.loads(r["detail"]) if isinstance(r["detail"], str) else (r["detail"] or {})
        words = "" if r["fidelity"] == "tone_only" else cut_heard(det.get("words", ""), rules.max_heard_chars)
        rows.append((r["at"], r["seq"] or 0, r["percept_id"], {
            "speaker": names(r["source_id"]) if r["source_id"] else "Someone", "to_me": bool(det.get("addressed_to_me")),
            "words": words}))
    for r in tx.query("SELECT v.line_id, v.at, v.text, (SELECT MIN(e.seq) FROM events e WHERE e.type='SPEECH' AND "
                      "e.cause_event_id = v.event_id AND e.actor_id = v.actor_id AND e.at = v.at) AS seq FROM voice_lines v "
                      "WHERE v.actor_id=? AND v.at>=? AND v.at<?", (holder_id, since, at)):
        rows.append((r["at"], r["seq"] or 0, r["line_id"], {"speaker": "you", "to_me": False, "words": r["text"]}))
    rows.sort(key=lambda x: (x[0], x[1], x[2]))
    out = []
    for i, (t, _k, _id, f) in enumerate(rows):
        ans = (f["to_me"] and f["words"] and classify_form(f["words"]) == UtteranceForm.QUESTION
               and not any(x[3]["speaker"] == "you" and x[0] > t for x in rows[i + 1:]))
        out.append(ThreadLine(speaker=f["speaker"], to_me=f["to_me"], words=f["words"], ago_text=_age(at - t),
                              unanswered=bool(ans)))
    return out[-rules.max_thread_lines:] if rules.max_thread_lines > 0 else []


def choose_examples(examples, *, reaction, rules):
    from .packet import estimate_tokens
    pool = [e for e in (examples or []) if not reaction or e.pressure in ("pressure", "limit")]
    if reaction:
        pool = pool[:rules.voice_examples_reaction]
    out, used = [], 0
    for e in pool:
        cost = estimate_tokens(e.situation + e.by + e.said_to_them + e.they_say) + 8
        if used + cost > rules.voice_example_tokens:
            break
        out.append(e)
        used += cost
    return out


def _f1c_lines(tx, actor_id):
    from ..physical.objects import coverage
    from .packet import BARE_LINES, COLD_LINES
    out = []
    n = tx.query_one("SELECT cold_stage FROM needs WHERE body_id=?", (actor_id,))
    if n is not None and n[0] >= 1:
        out.append(COLD_LINES[min(6, n[0])])
    lk = tx.query_one("SELECT looks FROM bodies WHERE body_id=?", (actor_id,))
    if lk is not None and lk[0] is not None:
        cov = coverage(tx, actor_id)
        if "torso" not in cov and "groin" not in cov:
            out.append(BARE_LINES[0])
        elif "torso" not in cov:
            out.append(BARE_LINES[1])
    return out


_SWEARS = {"none": "You do not swear.", "rare": "You rarely swear.", "frequent": "You swear often.",
           "constant": "You swear all the time."}


def ambient_packet(tx, actor_id, turn_index, at, *, doing="", idle=False):
    # AMB-01 (D-128): what a COLD person has to go on to say one thing — their own records only
    from ..contracts.mind import AmbientPacket, AmbientPerson
    from .actor import fused
    from .perception import place_phrase, word_for
    last = tx.query_one("SELECT MAX(at) FROM events WHERE type='SPEECH' AND actor_id=? AND at<=?", (actor_id, at))[0]
    rows = [dict(r) for r in tx.query(
        "SELECT * FROM percept_log WHERE holder_id=? AND turn_index BETWEEN ? AND ? AND at<=? AND at>? AND "
        "event_id NOT LIKE 'scene:%' AND (source_id IS NULL OR source_id != ?) ORDER BY at DESC, percept_id DESC LIMIT 4",
        (actor_id, turn_index - 1, turn_index, at, -1 if last is None else last, actor_id))]
    if not rows and not idle:
        return None
    PR = tx.rules.packet
    reached = []
    for p in reversed(rows):
        if p["channel"] == "speech":
            det = json.loads(p["detail"]) if isinstance(p["detail"], str) else (p["detail"] or {})
            who = word_for(tx, actor_id, p["source_id"]) if p["source_id"] else "Someone"
            reached.append(f"{_cap(who)} said{' to you' if det.get('addressed_to_me') else ''}: "
                           f"\"{cut_heard(det.get('words', ''), PR.max_heard_chars)}\"")
        else:
            reached.append(p["text"])
    v = fused(tx, actor_id).voice
    from .identity import end
    held = (v.capsule or "").lower()
    voice = [v.capsule, "How you talk: " + " ".join(_cap(t if t.rstrip().endswith((".", "!", "?", '"')) else t.rstrip() + ".")
                                                   for t in v.speech_tendencies),
             f"Easy: \"{v.exemplars.low_stakes}\"", f"Under pressure: \"{v.exemplars.under_pressure}\"",
             f"At the limit: \"{v.exemplars.at_the_limit}\"",
             "You would never say: " + "; ".join(f"\"{x}\"" for x in v.would_never_say), _SWEARS[v.profanity]]
    if all(t.lower().rstrip(".") in held for t in v.speech_tendencies):          # D-244: said once
        voice.pop(1)
    if v.dialect_notes.strip():
        voice.append(f"How you sound: {end(v.dialect_notes)}")                  # D-244: as the card says it
    pl = _row(tx, "SELECT p.name FROM positions s JOIN places p ON p.place_id = s.place_id WHERE s.body_id=?", (actor_id,))
    said = [r[0] for r in tx.query("SELECT text FROM voice_lines WHERE actor_id=? AND at<=? ORDER BY at DESC, line_id DESC "
                                   "LIMIT 3", (actor_id, at))][::-1]
    people, handles = [], {}
    for (b,) in tx.query("SELECT p.source_id FROM percept_log p JOIN bodies b ON b.body_id = p.source_id WHERE "
                         "p.holder_id=? AND p.turn_index=? AND p.at<=? AND p.source_id != ? AND b.alive=1 AND "
                         "b.kind='human' GROUP BY p.source_id ORDER BY MIN(p.at), MIN(p.percept_id) LIMIT 6",
                         (actor_id, turn_index, at, actor_id)):
        h = f"P{len(people) + 1}"
        handles[h] = b
        rel = _row(tx, "SELECT * FROM relationships WHERE from_id=? AND to_id=?", (actor_id, b))
        parts = [_temper_feeling(tx, actor_id, b, at)]
        if rel is not None and _rel_text(rel) != "No strong feelings.":
            t = _rel_text(rel).rstrip(".")
            parts.append(t[:1].lower() + t[1:])
        people.append(AmbientPerson(handle=h, word=word_for(tx, actor_id, b), feeling="; ".join(x for x in parts if x)))
    if not rows and not tx.query_one(                             # D-150: a quiet moment needs someone to talk to
            "SELECT 1 FROM positions a JOIN positions b ON b.place_id = a.place_id WHERE a.body_id=? AND b.body_id IN (%s)"
            % ",".join("?" * len(handles)), (actor_id, *handles.values())) if handles else not rows:
        return None
    name = _row(tx, "SELECT display_name FROM actors WHERE actor_id=?", (actor_id,))["display_name"]
    from .retrieval import lore_lines
    knows = [r["text"] for r in lore_lines(tx, actor_id, turn_index, at, min(2, tx.rules.packet.max_lore))]   # D-130
    from ..kernel.clock import format_clock, world_time
    wt = world_time(at)                                          # D-159: the time as they know it
    when = (f"{format_clock(at)}, day {wt.day} since the Fall ({wt.part_of_day})" if _has_timepiece(tx, actor_id)
            else f"Day {wt.day} since the Fall ({wt.part_of_day})")
    return AmbientPacket(actor_id=actor_id, name=name, voice=voice, where=place_phrase(pl["name"]) if pl else "",
                         when=when, doing=doing, state=[x for x in _body_lines(tx, actor_id) if x != "Unhurt."][:3],
                         reached=reached, said=said, knows=knows, people=people, handles=handles)
