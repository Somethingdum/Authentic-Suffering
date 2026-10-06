"""Implementation of narration/narrator.py."""
from __future__ import annotations

import hashlib
import json
import re

CHANNEL_KIND = {"visual": "sight", "auditory": "sound", "speech": "speech", "tactile": "touch", "olfactory": "smell",
                "vibration": "sound"}
BAND_TEXT = {"clean": "It goes cleanly.", "cost": "It works, at a cost.", "fail": "It doesn't work.",
             "break": "It goes badly wrong."}
RESULT_TEXT = {
    "no_progress": "No progress.", "fell": "{pc} falls.", "blocked_by_lock": "It won't open.", "no_key": "There is no key for it.",
    "held": "It holds.", "jammed": "The lock jams.", "click": "A dry click. The gun does not fire.", "hit": "A hit.",
    "miss": "A miss.", "refused_full_hands": "Their hands are full.", "no_ammo": "There is no ammunition for it.",
    "grabbed": "{pc} gets a grip.", "slipped": "The grab slips.", "knocked_down": "They go down.", "disarmed": "The weapon comes free.",
    "stumbled": "{pc} stumbles.", "task_done": "The work is finished.", "surrendered": "{pc} gives up.",
}
BLOCKED_TEXT = {
    "incapable": "{pc} can't manage it.", "target_gone": "What {pc} went for is not there any more.",
    "target_dead": "They are already dead.", "item_gone": "It isn't there any more.",
    "referent_missing": "It isn't where {pc} thought it was.", "portal_closed": "The way is shut.",
    "not_admitted": "{pc} can't fit through.", "out_of_reach": "It's out of reach.", "hands_full": "{pc}'s hands are full.",
    "portal_open": "It's already open.", "wrong_side": "{pc} can't get at it from this side.",
}
TRAILING_PAREN = re.compile(r"\s*\([^()]*\)\s*$")


def _cap1(s):
    return s[:1].upper() + s[1:]


def _row(s, sql, p=()):
    r = s.query_one(sql, p)
    return dict(r) if r is not None else None


def _one_breath(lines, breath):
    # D-283: the pieces of one utterance are one line, at the first piece's place — across what was only seen or
    # smelt meanwhile, never across another voice or a sound (a shot mid-sentence is told where it fell)
    out, last = [], {}
    for ln in lines:
        u = breath.get(id(ln)) if ln.kind == "speech" else None
        i = last.get(u) if u else None
        if i is not None:
            prev = out[i]
            quiet = all(x.kind in ("sight", "smell") for x in out[i + 1:])
            if quiet and prev.words and ln.words and f'"{prev.words}"' in prev.text:
                joined = f"{prev.words} {ln.words}"
                out[i] = prev.model_copy(update={"words": joined, "text": prev.text.replace(f'"{prev.words}"', f'"{joined}"', 1)})
                continue
        if u:
            last[u] = len(out)
        out.append(ln)
    return out


def pc_first_name(tx, pc_id):
    return _row(tx, "SELECT display_name FROM actors WHERE actor_id=?", (pc_id,))["display_name"].split()[0]


def known_names(tx):
    out = set()
    for r in tx.query("SELECT known_name FROM acquaintance WHERE known_name IS NOT NULL"):
        out.add(r[0])
    for r in tx.query("SELECT display_name FROM actors"):
        out.add(r[0])
        out.add(r[0].split()[0])
    for r in tx.query("SELECT name FROM places"):
        out.add(r[0])
    return {n for n in out if n}


def _comprehension(tx, pc_id):
    from ..contracts.common import attr_mod
    sp = json.loads(_row(tx, "SELECT special FROM bodies WHERE body_id=?", (pc_id,))["special"])
    s = attr_mod(sp["P"]) + attr_mod(sp["I"])
    return "low" if s <= 4 else ("high" if s >= 8 else "average")


def _sleep_text(pc, etype, pl):
    from ..mind.affordance import duration_words
    to, frm = pl.get("awareness"), pl.get("from")
    if etype == "POSTURE_CHANGE":
        return f"{pc} fell asleep." if to == "asleep" else None
    if to == "asleep":
        return f"{pc} fell asleep."
    if to == "unconscious":
        return f"{pc} blacked out."
    if to == "awake" and frm == "asleep":
        ms = pl.get("slept_ms") or 0
        return f"{pc} woke after about {duration_words(ms / 1000)} asleep." if ms >= 60_000 else f"{pc} woke."
    if to == "awake" and frm == "unconscious":
        return f"{pc} came to."
    return None


def _as_one(tx, pc_id, entries):
    """D-265: more than two people holding still the same way keep the first two lines; the rest are one line."""
    from ..contracts.narration import NarratorLine
    from ..mind.memory import QUIET_VERBS
    from .location import NUMBER_WORDS
    groups = {}
    for i, (at, seq, pid, line) in enumerate(entries):
        if not pid or line.kind != "sight":
            continue
        r = _row(tx, "SELECT e.type, e.actor_id, e.payload FROM percept_log p JOIN events e ON e.event_id=p.event_id "
                     "WHERE p.percept_id=?", (pid,))
        if r is None or r["type"] != "ACTION_START" or not r["actor_id"] or r["actor_id"] == pc_id:
            continue
        pl = json.loads(r["payload"]) if isinstance(r["payload"], str) else (r["payload"] or {})
        try:
            d = tx.canon.find("affordance", pl.get("def_id") or "")
        except KeyError:
            continue
        if getattr(d.verb, "value", d.verb) in QUIET_VERBS and "threat_response" not in d.tags:
            groups.setdefault((pl.get("def_id"), pl.get("target_id")), []).append(i)
    drop, add = set(), []
    for idx in groups.values():
        idx = sorted(idx, key=lambda i: entries[i][:3])
        if len(idx) < 4:                                             # two and one more: just say the third
            continue
        rest = idx[2:]
        drop |= set(rest)
        at, seq, pid, line = entries[idx[1]]
        n = len(rest)
        add.append((at, seq, pid + "~", NarratorLine(seconds=line.seconds, kind="sight",
                                                     text=f"{NUMBER_WORDS[n] if n < len(NUMBER_WORDS) else 'Many'} others do the same.")))
    return [e for i, e in enumerate(entries) if i not in drop] + add


def build_narrator_packet(tx, pc_id, turn_index, t0, settings):
    from ..contracts.common import ANATOMY_WORDS, SEVERITY_WORDS
    from ..contracts.narration import NarratorLine, NarratorPacket, NarratorStyle
    from ..kernel.clock import format_clock, now, world_time
    from ..mind.perception import place_phrase, retell, to_phrase
    from ..physical.bodies import effective_bleed, impairment
    from .lint import echo_block
    from .location import describe
    at = now(tx)
    pc = pc_first_name(tx, pc_id)
    sex = (_row(tx, "SELECT sex FROM bodies WHERE body_id=?", (pc_id,)) or {"sex": None})["sex"]
    wt = world_time(at)
    entries = []
    breath = {}
    for p in tx.query("SELECT pl.*, e.seq AS ev_seq FROM percept_log pl LEFT JOIN events e ON e.event_id=pl.event_id "
                      "WHERE pl.holder_id=? AND pl.turn_index=? AND pl.event_id NOT LIKE 'scene:%'", (pc_id, turn_index)):
        p = dict(p)
        det = json.loads(p["detail"])
        kind = CHANNEL_KIND[p["channel"]]
        if kind == "speech":
            line = NarratorLine(seconds=max(0, p["at"] - t0) / 1000, kind="speech", text=p["text"],
                                speaker=det.get("speaker_known_as"), words=det.get("words") or None)
            u = tx.query_one("SELECT json_extract(payload,'$.utterance_id') FROM events WHERE event_id=?", (p["event_id"],))
            breath[id(line)] = u[0] if u else None                        # D-283
        else:
            text = p["text"]
            if settings.narration_person == "third_limited":            # D-170: of the PC, as every other line is
                text = _of_pc(text, sex)
            line = NarratorLine(seconds=max(0, p["at"] - t0) / 1000, kind=kind, text=text)
        entries.append((p["at"], p["ev_seq"] or 0, p["percept_id"], line))
    for e in tx.query("SELECT * FROM events WHERE turn_index=? AND (actor_id=? OR (type='AWARENESS_CHANGE' AND "
                      "json_extract(payload,'$.body_id')=?)) ORDER BY seq", (turn_index, pc_id, pc_id)):
        e = dict(e)
        pl = json.loads(e["payload"])
        sec = max(0, e["at"] - t0) / 1000
        text = None
        kind = "outcome"
        if e["type"] in ("AWARENESS_CHANGE", "POSTURE_CHANGE"):               # D-171: the night passed
            text = _sleep_text(pc, e["type"], pl)
        elif e["type"] == "ACTION_START" and pl.get("def_id") == "wonder":     # CHEAT-14: it simply happens
            text = f"{pc} {pl.get('seen') or pl.get('label')}."
        elif e["type"] == "ACTION_START" and pl.get("def_id") != "speak":
            lbl = retell(TRAILING_PAREN.sub("", pl.get("label") or pl.get("def_id", "")), "third", sex)   # TEXT-01 (D-152)
            text = f"{pc} chose to {lbl[:1].lower() + lbl[1:]}."
        elif e["type"] == "SPEECH":
            line = NarratorLine(seconds=sec, kind="speech", text=f'{pc} says, "{pl["words"]}"', speaker=pc, words=pl["words"])
            breath[id(line)] = pl.get("utterance_id")                     # D-283
            entries.append((e["at"], e["seq"], "", line))
            continue
        elif e["type"] == "CHECK_RESOLVED" and pl.get("band") in BAND_TEXT:
            text = BAND_TEXT[pl["band"]]
        elif e["type"] == "ACTION_COMPLETE" and pl.get("result") in RESULT_TEXT:
            text = RESULT_TEXT[pl["result"]].format(pc=pc)
        elif e["type"] == "ACTION_BLOCKED" and pl.get("cause") in BLOCKED_TEXT:
            text = BLOCKED_TEXT[pl["cause"]].format(pc=pc)
        elif e["type"] == "MOVE" and pl.get("from_place") is not None:
            if pl["to_place"] != pl["from_place"]:                         # D-178: into the yard, first
                nm = _row(tx, "SELECT name FROM places WHERE place_id=?", (pl["to_place"],))["name"]
                text = f"{pc} goes into {place_phrase(nm)}."
            elif pl.get("to_anchor"):
                an = _row(tx, "SELECT name FROM anchors WHERE anchor_id=?", (pl["to_anchor"],))["name"]
                text = f"{pc} moves {to_phrase(an)}."
        if text:
            entries.append((e["at"], e["seq"], "", NarratorLine(seconds=sec, kind=kind, text=text)))
    entries = _as_one(tx, pc_id, entries)                             # D-265: the room as one
    entries.sort(key=lambda x: (x[0], x[1], x[2]))
    lines = _one_breath([x[3] for x in entries], breath)                 # D-283: one utterance, one line
    pos = _row(tx, "SELECT place_id FROM positions WHERE body_id=?", (pc_id,))
    place = _row(tx, "SELECT name FROM places WHERE place_id=?", (pos["place_id"],))
    moved = tx.query_one("SELECT 1 FROM events WHERE type='MOVE' AND actor_id=? AND turn_index=? "
                         "AND json_extract(payload,'$.from_place') IS NOT NULL AND json_extract(payload,'$.from_place') != json_extract(payload,'$.to_place')",
                         (pc_id, turn_index))
    establish = turn_index == 1 or moved is not None
    loc = describe(tx, pc_id, at)
    from ._impl_location import latest_view
    view = [p for p in latest_view(tx, pc_id) if p["source_id"] and p["source_id"].startswith("act_") or
            (p["source_id"] is None and json.loads(p["detail"]).get("level") == "silhouette")]
    people = [p["text"] for p in view]
    # NARR-10 (F1a-2): how someone looks, told as they come into the scene
    from ..mind._impl_packet import seen_appearance
    from ..mind.perception import with_article, word_for
    before = {r[0] for r in tx.query("SELECT DISTINCT source_id FROM percept_log WHERE holder_id=? AND turn_index<? AND channel='visual' "
                                     "AND fidelity IN ('exact','partial') AND source_id IS NOT NULL", (pc_id, turn_index))}
    looks_lines, told = [], set()
    for p in view:
        s = p["source_id"]
        if not s or not s.startswith("act_") or s == pc_id or s in told:
            continue
        told.add(s)
        if not establish and s in before:
            continue
        text = seen_appearance(tx, pc_id, s, view, at)
        if text:
            kn = _row(tx, "SELECT known_name FROM acquaintance WHERE holder_id=? AND subject_id=?", (pc_id, s))
            label = kn["known_name"] if kn and kn["known_name"] else with_article(word_for(tx, pc_id, s))
            looks_lines.append(f"{label}: {text}")
    from ..physical.bodies import grips_on, tied
    state = [f"{_cap1(word_for(tx, pc_id, h))} has hold of {pc}." for h in grips_on(tx, pc_id)]   # D-208
    if tied(tx, pc_id):
        state.append(f"{pc}'s hands and feet are tied.")
    for w in tx.query("SELECT * FROM wounds WHERE body_id=? AND healed_at IS NULL ORDER BY created_at, wound_id", (pc_id,)):
        w = dict(w)
        s = f"{SEVERITY_WORDS[w['severity']][:1].upper()}{SEVERITY_WORDS[w['severity']][1:]} {w['type']} wound to the {ANATOMY_WORDS[w['anatomy']]}"
        if effective_bleed(tx, w["wound_id"]) > 0:
            s += ", bleeding"
        state.append(s + ".")
    imp = impairment(tx, pc_id)
    if imp > 0:
        from ._impl_location import impairment_word
        state.append(f"{pc} is {impairment_word(imp)}.")
    from ..physical.bodies import stages
    state += [st.felt for _pw, st in stages(tx, pc_id) if st.felt]
    if tx.query_one("SELECT 1 FROM events WHERE type='INVOLUNTARY' AND actor_id=? AND turn_index=? "
                    "AND json_extract(payload,'$.kind')='compulsion'", (pc_id, turn_index)) is not None:
        from .narrator import URGE_LINE
        state.append(URGE_LINE)
    from ..mind._impl_packet import _f1c_lines
    state += _f1c_lines(tx, pc_id)
    back, back_names = _intrusion(tx, pc_id, turn_index, at)     # NARR-11 (D-145): what comes back
    if back:
        state.append(back)
    if tx.query_one("SELECT 1 FROM events w JOIN events s ON s.event_id=w.cause_event_id WHERE w.type='AWARENESS_CHANGE' AND "
                    "w.turn_index=? AND json_extract(w.payload,'$.body_id')=? AND json_extract(w.payload,'$.awareness')='awake' AND "
                    "s.type IN ('AWARENESS_CHANGE','POSTURE_CHANGE') AND json_extract(s.payload,'$.body_id')=? AND "
                    "json_extract(s.payload,'$.awareness')='asleep'", (turn_index, pc_id, pc_id)) is not None:
        from .narrator import BROKEN_NIGHT_LINE                  # D-146: a night broken
        state.append(BROKEN_NIGHT_LINE)
    allowed = {pc, _row(tx, "SELECT display_name FROM actors WHERE actor_id=?", (pc_id,))["display_name"]}
    named = set(back_names)
    for r in tx.query("SELECT DISTINCT a.known_name FROM percept_log p JOIN acquaintance a ON a.holder_id=p.holder_id AND a.subject_id=p.source_id "
                      "WHERE p.holder_id=? AND p.turn_index=? AND a.known_name IS NOT NULL", (pc_id, turn_index)):
        named.add(r[0])
    allowed |= named | {n.split()[0] for n in named if n and n.split()}            # D-264: a man known by his full name
    for r in tx.query("SELECT pl.name FROM known_places k JOIN places pl ON pl.place_id=k.place_id WHERE k.holder_id=?", (pc_id,)):
        allowed.add(r[0])
    hint = None
    for p in tx.query("SELECT detail FROM percept_log WHERE holder_id=? AND turn_index=? AND channel='speech' AND fidelity IN ('exact','partial') "
                      "ORDER BY at, percept_id", (pc_id, turn_index)):
        d = json.loads(p[0])
        if d.get("addressed_to_me"):
            hint = f"answer {d.get('speaker_known_as') or 'them'}"
    if hint is None:
        from ..mind.cues import cues_of
        if cues_of(tx, pc_id, turn_index, at) & {"threat_seen", "weapon_pointed"}:
            hint = "decide what to do about the threat"
    from .narrator import LONG_TURN_MS
    me = _row(tx, "SELECT alive, awareness FROM bodies WHERE body_id=?", (pc_id,))
    if me["alive"] and me["awareness"] in ("asleep", "unconscious"):      # D-172: asleep at the end
        people, looks_lines = [], []
        hint = f"{pc} asleep" if me["awareness"] == "asleep" else f"{pc} senseless"
    details = loc.description_lines if establish else []
    if settings.narration_person == "third_limited":                   # D-178: the place told of him
        details = [_of_pc(x, sex) for x in details]
        people = [_of_pc(x, sex) for x in people]
    when = f"{format_clock(at)}, day {wt.day} since the Fall ({wt.part_of_day})"
    if at - t0 >= LONG_TURN_MS:
        when = f"{format_clock(t0)} to {when}"
    from ..mind._impl_lore import lore_lines                                     # D-197
    n_lore = tx.rules.packet.max_lore
    heard = {x["text"] for x in lore_lines(tx, pc_id, turn_index - 1, at, n_lore)} if turn_index > 0 else set()
    beliefs = [x["text"] for x in lore_lines(tx, pc_id, turn_index, at, n_lore) if x["text"] not in heard]
    style = NarratorStyle.model_validate_json(_row(tx, "SELECT style_json FROM narrator_state WHERE id=1")["style_json"])
    rules = tx.canon.find("style", "narration")
    numbers = tx.rules.style
    return NarratorPacket(
        turn_index=turn_index, world_time_text=when,
        place_text=place["name"], pc_name=pc, pc_state_lines=state, comprehension=_comprehension(tx, pc_id), lines=lines,
        establish_place=establish, place_details=details, people_present=people,
        people_looks=looks_lines, pc_beliefs=beliefs,
        choice_prompt_hint=hint, allowed_names=sorted(allowed), style=style, length=settings.narration_length,
        person=settings.narration_person, tense=settings.narration_tense, banned_phrases=list(rules.banned_phrases),
        intensity=settings.intensity, player_input_echo_block=_unlicensed(echo_block(tx, turn_index, numbers),
                                                                          [ln for ln in lines if not (ln.kind == "speech" and ln.speaker == pc)],
                                                                          details,
                                                                          people, looks_lines, numbers))


def _of_pc(text, sex):
    """D-170: a percept the PC had, told of the PC ('grabs at you' -> 'grabs at him'); quoted words are left as said."""
    from ..mind.perception import retell
    parts = text.split('"')
    return '"'.join(retell(x, "third", sex) if i % 2 == 0 else x for i, x in enumerate(parts))


def _unlicensed(block, lines, details, people, looks, numbers):
    """D-169: the player's word runs the packet's own words do not hold — the world's words are the narrator's."""
    from .lint import content_ngrams
    own = set()
    texts = [ln.text for ln in lines] + [ln.words or "" for ln in lines] + list(details) + list(people) + list(looks)
    for t in texts:
        if t:
            own |= content_ngrams(t, numbers.echo_n, numbers.echo_min_content_tokens)
    return [g for g in block if g not in own]


def packet_hash(packet):
    from ..kernel.jsoncanon import canonical_json
    return hashlib.sha256(canonical_json(packet.model_dump(mode="json")).encode("utf-8")).hexdigest()


def code_render(packet):
    parts = []
    if packet.establish_place:
        parts.extend(packet.place_details)
    for l in packet.lines:
        if l.kind == "speech" and l.words:
            parts.append(f'{l.speaker or "Someone"}: "{l.words}"')
        else:
            parts.append(l.text)
    return " ".join(parts) or f"{packet.place_text}. Nothing changes."


async def narrate(client, packet, style_rules, numbers, *, config, all_known_names, turn_index):
    """Returns (prose, findings_of_kept_draft, attempts, passed)."""
    from ..contracts.calls import LintContext
    from ..contracts.common import CallClass
    from ..contracts.narration import LintFinding, RenderLintJudgement
    from ..lanes.parse import split_sentences
    from ..lanes.requests import build_request
    from ..lanes.schemas import to_lm_schema
    from .lint import lint_prose
    words = numbers.narration_words[packet.length]
    fix = []
    best = None
    attempts = 0
    for i in range(numbers.max_narration_attempts):
        attempts += 1
        req = build_request(config, CallClass.NARRATION, turn_index=turn_index, context=packet, k=packet, words=words, fix=fix)
        resp = await client.call(req)
        if resp.parse_status != "ok" or not resp.text.strip():
            continue
        prose = resp.text.strip()
        rep = lint_prose(prose, packet, style_rules, numbers, all_known_names)
        findings = list(rep.findings)
        if rep.passed:
            sents = split_sentences(prose)
            lc = LintContext(packet=packet, prose=prose, sentences=sents)
            jq = build_request(config, CallClass.RENDER_LINT, turn_index=turn_index, context=lc,
                               json_schema=to_lm_schema(RenderLintJudgement), ctx=lc)
            jr = await client.call(jq, RenderLintJudgement)
            if jr.parse_status == "ok":
                for u in RenderLintJudgement.model_validate(jr.parsed).unsupported:
                    if u.sentence_index < len(sents):
                        findings.append(LintFinding(rule="DISC-JUDGE", detail=f"{u.reason}: {sents[u.sentence_index]}",
                                                    sentence_index=u.sentence_index))
        errors = [f for f in findings if f.severity == "error"]
        if best is None or len(errors) < best[2]:
            best = (prose, findings, len(errors))
        if not errors:
            return prose, findings, attempts, True
        fix = [f"{f.rule}: {f.detail}" for f in errors]
    if best is None:
        return code_render(packet), [LintFinding(rule="NARR-FALLBACK", detail="no draft came back; the moment is told plainly",
                                                 severity="warning")], attempts, False
    return best[0], best[1], attempts, False


def write_narration(tx, turn_index, prose, packet, passed, attempts):
    from ..contracts.events import Event, EventType, WriteOp, WriteRecord
    from ..kernel.clock import now
    h = packet_hash(packet)
    return tx.commit_event(Event(type=EventType.NARRATION, writer="narration.narrator", at=now(tx), turn_index=turn_index,
                                 payload={"turn_index": turn_index, "packet_hash": h, "lint_passed": bool(passed), "attempts": attempts},
                                 writes=[WriteRecord(op=WriteOp.INSERT, table="narration",
                                                     values={"turn_index": turn_index, "text": prose, "packet_hash": h,
                                                             "lint_passed": int(bool(passed)), "attempts": attempts})]))


def _intrusion(tx, pc_id, turn_index, at):
    """NARR-11 (D-145): the worst thing the PC saw lately comes back unasked, oftener the worse the strain."""
    from .narrator import INTRUSION_LINE, INTRUSION_MS, INTRUSION_STRESS
    r = tx.query_one("SELECT stress FROM actors WHERE actor_id=?", (pc_id,))
    stress = int(r[0]) if r and r[0] is not None else 0
    if stress < INTRUSION_STRESS or turn_index % max(1, 11 - stress):
        return None, set()
    for text, typ, pl, src in tx.query(
            "SELECT p.text, e.type, e.payload, p.source_id FROM percept_log p JOIN events e ON e.event_id=p.event_id WHERE p.holder_id=? "
            "AND p.channel='visual' AND p.fidelity IN ('exact','partial') AND p.turn_index<? AND p.at>=? AND "
            "e.type IN ('DEATH','HARM','ACTION_START') ORDER BY p.at DESC, p.percept_id DESC", (pc_id, turn_index, at - INTRUSION_MS)):
        pl = json.loads(pl)
        if typ == "DEATH":
            k = tx.query_one("SELECT kind FROM bodies WHERE body_id=?", (pl.get("body_id"),))
            if not (k and k[0] == "human"):
                continue
        elif typ == "HARM" and pl.get("type") != "bite":
            continue
        elif typ == "ACTION_START" and pl.get("def_id") != "butcher_human":
            continue
        names = set()
        for b in {src, pl.get("body_id"), pl.get("target_id"), pl.get("actor_id")} - {None}:
            kn = tx.query_one("SELECT known_name FROM acquaintance WHERE holder_id=? AND subject_id=?", (pc_id, b))
            if kn and kn[0]:
                names.add(kn[0])
        return INTRUSION_LINE.format(text=text), names
    return None, set()
