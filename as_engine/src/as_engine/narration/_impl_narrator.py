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
    "portal_open": "It's already open.",
}
TRAILING_PAREN = re.compile(r"\s*\([^()]*\)\s*$")


def _row(s, sql, p=()):
    r = s.query_one(sql, p)
    return dict(r) if r is not None else None


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


def build_narrator_packet(tx, pc_id, turn_index, t0, settings):
    from ..contracts.common import ANATOMY_WORDS, SEVERITY_WORDS
    from ..contracts.narration import NarratorLine, NarratorPacket, NarratorStyle
    from ..kernel.clock import format_clock, now, world_time
    from ..mind.perception import place_phrase, to_phrase
    from ..physical.bodies import effective_bleed, impairment
    from .lint import echo_block
    from .location import describe
    at = now(tx)
    pc = pc_first_name(tx, pc_id)
    wt = world_time(at)
    entries = []
    for p in tx.query("SELECT pl.*, e.seq AS ev_seq FROM percept_log pl LEFT JOIN events e ON e.event_id=pl.event_id "
                      "WHERE pl.holder_id=? AND pl.turn_index=? AND pl.event_id NOT LIKE 'scene:%'", (pc_id, turn_index)):
        p = dict(p)
        det = json.loads(p["detail"])
        kind = CHANNEL_KIND[p["channel"]]
        if kind == "speech":
            line = NarratorLine(seconds=max(0, p["at"] - t0) / 1000, kind="speech", text=p["text"],
                                speaker=det.get("speaker_known_as"), words=det.get("words") or None)
        else:
            line = NarratorLine(seconds=max(0, p["at"] - t0) / 1000, kind=kind, text=p["text"])
        entries.append((p["at"], p["ev_seq"] or 0, p["percept_id"], line))
    for e in tx.query("SELECT * FROM events WHERE actor_id=? AND turn_index=? ORDER BY seq", (pc_id, turn_index)):
        e = dict(e)
        pl = json.loads(e["payload"])
        sec = max(0, e["at"] - t0) / 1000
        text = None
        kind = "outcome"
        if e["type"] == "ACTION_START" and pl.get("def_id") != "speak":
            lbl = TRAILING_PAREN.sub("", pl.get("label") or pl.get("def_id", ""))
            text = f"{pc} chose to {lbl[:1].lower() + lbl[1:]}."
        elif e["type"] == "SPEECH":
            entries.append((e["at"], e["seq"], "", NarratorLine(seconds=sec, kind="speech", text=f'{pc} says, "{pl["words"]}"',
                                                                speaker=pc, words=pl["words"])))
            continue
        elif e["type"] == "CHECK_RESOLVED" and pl.get("band") in BAND_TEXT:
            text = BAND_TEXT[pl["band"]]
        elif e["type"] == "ACTION_COMPLETE" and pl.get("result") in RESULT_TEXT:
            text = RESULT_TEXT[pl["result"]].format(pc=pc)
        elif e["type"] == "ACTION_BLOCKED" and pl.get("cause") in BLOCKED_TEXT:
            text = BLOCKED_TEXT[pl["cause"]].format(pc=pc)
        elif e["type"] == "MOVE" and pl.get("from_place") is not None:
            if pl.get("to_anchor"):
                an = _row(tx, "SELECT name FROM anchors WHERE anchor_id=?", (pl["to_anchor"],))["name"]
                text = f"{pc} moves {to_phrase(an)}."
            elif pl["to_place"] != pl["from_place"]:
                nm = _row(tx, "SELECT name FROM places WHERE place_id=?", (pl["to_place"],))["name"]
                text = f"{pc} goes into {place_phrase(nm)}."
        if text:
            entries.append((e["at"], e["seq"], "", NarratorLine(seconds=sec, kind=kind, text=text)))
    entries.sort(key=lambda x: (x[0], x[1], x[2]))
    lines = [x[3] for x in entries]
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
    state = []
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
    allowed = {pc, _row(tx, "SELECT display_name FROM actors WHERE actor_id=?", (pc_id,))["display_name"]}
    for r in tx.query("SELECT DISTINCT a.known_name FROM percept_log p JOIN acquaintance a ON a.holder_id=p.holder_id AND a.subject_id=p.source_id "
                      "WHERE p.holder_id=? AND p.turn_index=? AND a.known_name IS NOT NULL", (pc_id, turn_index)):
        allowed.add(r[0])
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
    style = NarratorStyle.model_validate_json(_row(tx, "SELECT style_json FROM narrator_state WHERE id=1")["style_json"])
    rules = tx.canon.find("style", "narration")
    numbers = tx.rules.style
    return NarratorPacket(
        turn_index=turn_index, world_time_text=f"{format_clock(at)}, day {wt.day} since the Fall ({wt.part_of_day})",
        place_text=place["name"], pc_name=pc, pc_state_lines=state, comprehension=_comprehension(tx, pc_id), lines=lines,
        establish_place=establish, place_details=loc.description_lines if establish else [], people_present=people,
        choice_prompt_hint=hint, allowed_names=sorted(allowed), style=style, length=settings.narration_length,
        person=settings.narration_person, tense=settings.narration_tense, banned_phrases=list(rules.banned_phrases),
        intensity=settings.intensity, player_input_echo_block=echo_block(tx, turn_index, numbers))


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
