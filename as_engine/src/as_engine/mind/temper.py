"""Breaking points (P5, the owner's H1). Rules TEMPER-01..08. docs/as/05_ACTORS.md §7.1.
Owner 'mind.temper' (tempers). R = RulesConfig().temper.

The owner: people here are smart, but human smart. Hunger, grief, the daily dread of turning, of
being eaten alive, exhaustion and old grudges wear everyone down, and everybody has a breaking
point: disrespect the wrong person too much and you get decked in the jaw. A person can be furious
for a reason that is not fair and mean it with their whole heart; not every consequence is violence
(a cold shoulder, a grudge, a word to the leader, a door shut in your face).

Nothing here tells a mind to make trouble (Actor Spec §10). This module keeps the pressures true —
the anger each person carries toward each other person, and how close they are to breaking — and
makes the snap, when it comes, a caused, code-owned act (05_ACTORS §7: an involuntary act is caused,
timed and owned by code), the way a trained response is. What a person says when they snap is
still their own words (TEMPER-06 'words').

TEMPER-01 temper_of(store, actor_id) -> Temper: the actor's fused dossier temper
  (mind.actor.fused(store, actor_id).temper), else Temper() — fuse 3, outlet 'words', grudge 1.
TEMPER-02 Heat is anger at one person, now: tempers (holder_id, toward_id, heat 0..20, updated_at,
  last_kind). heat(store, holder_id, toward_id, at) -> int = the row's heat minus one per
  R.heat_decay_min minutes since updated_at (floor division), never below 0 — nor below the
  strength of an open 'grudge' loop of the holder whose subject_ids contain toward_id (a grudge
  keeps it warm); no row -> that floor (0 without a grudge).
  threshold(store, actor_id) -> int = max(1, temper_of(actor).fuse x 2 - actors.stress // 3): the
  more strained a person is, the shorter their fuse.
TEMPER-03 provocations(tx, holder_id, turn_index, at) -> list[Provocation]: read from the
  holder's OWN percept rows (percept_log) of this turn or the one before (turn_index - 1: what
  reached it after the last wave of the last turn), at <= ``at`` (SKULL-10), at fidelity exact or
  partial, in (at, percept_id) order; a percept whose event_id already has a
  TEMPER_CHANGE of this holder is skipped (each event provokes once). Provocation(toward_id,
  kind, event_id = the percept's event_id); toward_id is the percept's source_id — a body other
  than the holder (someone it can tell did it) — except for harmed_bonded. Kinds, each at most once
  per event, in this order:
    struck         a tactile percept (the holder was hurt by the source)
    shoved         a visual percept of an ACTION_START by the source whose payload target_id is the
                   holder and whose payload def_id is 'shove'; grabbed: def_id 'grapple' or 'disarm'
    threatened     a speech percept with detail.addressed_to_me whose form
                   (mind.firewall.classify_form(detail.words, weapon_pointed_at_receiver =
                   detail.armed_at_me)) is THREAT
    ordered_about  the same, form ORDER or DEMAND, when the source is not in the holder's
                   actors.accepted_authority
    insulted       a speech percept with detail.addressed_to_me whose words contain an entry of
                   INSULT_WORDS as whole words (case-insensitive) — a hint, never proof of motive
                   (Actor Spec §10); how the person reads it later (writeback) is what lasts
    harmed_bonded  a visual percept of a HARM (its source is the one hurt) whose payload body_id is
                   a body the holder has affection >= 2 toward (relationships from the holder) and
                   whose payload actor_id is set, is not the holder, and is the source of a visual
                   percept of the holder in the same window (it saw who did it): toward_id = that
                   actor_id
    stole_from     a visual percept of an ITEM_TRANSFER by the source of an item the holder
                   believes it owns (a live believed 'owner' claim holding of the holder whose
                   object_value is the holder — as mind.affordance reads ownership)
  ('quarreled' is society.settlement STL-15's kind: a row off-screen, provoked directly.)
TEMPER-04 provoke(tx, holder_id, toward_id, kind, event_id, at, turn_index) -> Event:
  heat = min(20, heat(tx, holder, toward, at) + R.provocation_heat[kind]); TEMPER_CHANGE
  {holder_id, toward_id, kind, event_id, heat} (writer 'mind.temper', actor_id = holder,
  cause_event_id = kernel.events.committed_or_none(tx, event_id)) upserting tempers {holder_id,
  toward_id, heat, updated_at = at, last_kind = kind}; then, when R.stress_from has the kind,
  mind.actor.adjust_stress(tx, holder, that amount, the TEMPER_CHANGE's id, at, turn_index).
  Returns the TEMPER_CHANGE.
TEMPER-05 take_in(tx, rng, holder_id, turn_index, at) -> Outburst | None   (turn.pipeline stage 3b:
  every conscious perceiver of the wave, sorted, the PC included)
  provoke() for each provocation (TEMPER-03, in order, then TEMPER-09's). None when there were none, or when the holder
  is the PC (meta pc_actor_id: its anger is real and on record, but the player's hand is never
  taken). Otherwise T =
  the provoked person with the highest heat now (ties: the one provoked last); heat(T) <
  threshold(holder) -> None. Else the breaking point:
    hold it in: rng.chance(tx, 'mind', f"hold:{holder_id}:{E}", min(R.hold_max, R.hold_per_resolve
      x actors.resolve_cur)), E = the event_id of the last provocation by T -> it swallows it:
      mind.resolve.drain(tx, holder, 'held_temper', E, at, turn_index) and None;
    else it snaps: INVOLUNTARY {actor_id: holder, kind: 'outburst', outlet: temper_of(holder).outlet,
      toward_id: T} (writer 'mind.temper', actor_id = holder, cause = E, at); the heat is halved
      (TEMPER_CHANGE kind 'vented', heat = heat // 2) and adjust_stress(-1); TEMPER-07; returns
      Outburst(toward_id = T, outlet, event_id = E).
TEMPER-06 What an outburst does — turn.cognition applies it (its step 4). Like a reflex or the
  wet strain's compulsion it is code's act: it replaces what the actor would have decided this
  wave, it is built from a core affordance def rather than picked from the menu (no resolve gate —
  a snap is the moment nerve runs out; a person who swears they never hit an unarmed man can still
  deck one), and the resolver resolves it like any intent:
    fists   punch T when T is within R.fists_reach_m and a hand is free — never a child, never
            someone in the person's care; otherwise as 'words'
    words   the actor thinks this wave (turn.select SEL-02: an outburst is mandatory); its packet
            says it has snapped (TEMPER-08) and its answer must carry speech to T at volume
            'raised' or 'shout' — else the one repair, and after that 'flight'. The words are the
            person's own.
    cold    walk out ('leave_place'), else to the far end of the place from T ('move_to_anchor')
    flight  as cold
    tears   sit down and break down ('rest')
TEMPER-07 A breaking point leaves a grudge unless temper.grudge is 0: the first open 'grudge' loop
  of the holder naming T (by created_at, loop_id) deepens — mind.mind.strengthen_loop(tx, it, +1,
  the outburst) (max 3); with none, mind.mind.open_loop(tx, holder, 'grudge',
  f"{perception.word_for(holder, T)} pushed me too far", [T], strength = temper.grudge, the
  outburst). And mind.mind.relate(tx, holder, T, 'resentment', +1, the outburst) (the axis clamps).
TEMPER-08 What the person knows of their own state goes into their packet (mind.packet):
  body_lines gains, by actors.stress, as its last line (after 'Unhurt.' when that is the only
  other): 7-8 "You are close to breaking."; 9-10 "You are at the end of your rope.";
  PacketEntity.feeling, per entity (h = heat toward it, th = threshold(holder)):
  h >= th -> "you are furious with them"; 0 < h and h >= th // 2 -> "they are getting under your
  skin"; else an open grudge loop naming it -> "you hold a grudge against them"; else ''. An
  outburst of outlet 'words' this wave (TEMPER-05, INVOLUNTARY at ``at``) -> SkullPacket.outburst =
  f"You snap. You are going to have it out with {the P-handle of T} — now, to their face."; else
  None.
TEMPER-09 (F1c, D-86) What people cannot stand to be near — the owner: smeared in the dead "I'm going
  to smell like hell, look like hell. And people aren't gonna want to be around me for very long
  till I shower"; and walking around naked "should be an issue for most people. Like 'What the
  fuck?'". exposures(tx, holder_id, turn_index, at) -> list[Provocation]: for a holder of kind
  'human', per other living body S of kind 'human' (sorted by body_id), each kind at most once:
    reeked  sense.olfaction.smells(tx, holder, S, at) == 'exact' and odour_of(S, at).kind == 'dead'
            (the reek of the dead on a living person, close enough to gag on)
    bared   a visual percept of the holder, of this turn or the one before (as TEMPER-03), at <=
            ``at``, fidelity exact or partial, whose source_id is S, where S's age_years >= 18,
            bodies.looks is not NULL and physical.objects.coverage(S) has neither 'torso' nor
            'groin' — a naked adult in plain sight (mind.cues 'naked')
  event_id None. A kind is skipped when a TEMPER_CHANGE of this holder toward S of that kind was
  committed at > at - C.reek_every_min ('reeked') / C.bared_every_min ('bared') minutes (C =
  RulesConfig().condition): standing next to it grates again every few minutes, and the reek
  builds heat faster than it fades. provoke() takes event_id None (cause None). What they do with
  it is theirs (the packet already says how the person looks and smells, and how they feel about
  them, TEMPER-08) — until it boils over like any heat.
Off-screen friction between the people of a settlement is society.settlement STL-15 (P9).

INSULT_WORDS is implemented data (a routing hint, TEMPER-03).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..contracts.dossier import Temper
    from ..contracts.events import Event
    from ..kernel.rng import Rng
    from ..kernel.store import Store, Tx

INSULT_WORDS: tuple[str, ...] = (
    "idiot", "moron", "stupid", "dumbass", "coward", "useless", "pathetic", "worthless", "loser", "freak",
    "shut up", "screw you", "fuck you", "fuck off", "asshole", "bastard", "bitch", "prick", "piece of shit",
)


@dataclass(frozen=True)
class Provocation:
    toward_id: str
    kind: str        # struck | shoved | grabbed | threatened | ordered_about | insulted | harmed_bonded | stole_from | reeked | bared
    event_id: str | None     # None for TEMPER-09's (what they are, not something they did)


@dataclass(frozen=True)
class Outburst:
    toward_id: str
    outlet: str      # fists | words | cold | flight | tears
    event_id: str


def temper_of(store: "Store | Tx", actor_id: str) -> "Temper":
    from ..contracts.dossier import Temper
    from .actor import fused
    d = fused(store, actor_id)
    return d.temper if getattr(d, "temper", None) is not None else Temper()


def _grudge_floor(store, holder_id, toward_id):
    import json as _j
    best = 0
    for r in store.query("SELECT subject_ids, strength FROM open_loops WHERE holder_id=? AND kind='grudge' AND status='open'",
                         (holder_id,)):
        if toward_id in _j.loads(r[0]):
            best = max(best, int(r[1]))
    return best


def heat(store: "Store | Tx", holder_id: str, toward_id: str, at: int) -> int:
    R = store.rules.temper
    floor = _grudge_floor(store, holder_id, toward_id)
    r = store.query_one("SELECT heat, updated_at FROM tempers WHERE holder_id=? AND toward_id=?", (holder_id, toward_id))
    if r is None:
        return floor
    mins = max(0, at - r[1]) // 60_000
    return max(floor, r[0] - mins // R.heat_decay_min, 0)


def threshold(store: "Store | Tx", actor_id: str) -> int:
    s = store.query_one("SELECT stress FROM actors WHERE actor_id=?", (actor_id,))
    stress = s[0] if s else 0
    return max(1, temper_of(store, actor_id).fuse * 2 - stress // 3)


def _words_have(words, entry):
    import re
    return re.search(r"(?<![a-z])" + re.escape(entry) + r"(?![a-z])", words.lower()) is not None


def provocations(tx: "Tx", holder_id: str, turn_index: int, at: int) -> list[Provocation]:
    import json as _j
    from ..contracts.common import UtteranceForm
    from .firewall import classify_form
    rows = [dict(r) for r in tx.query(
        "SELECT * FROM percept_log WHERE holder_id=? AND turn_index IN (?, ?) AND at<=? AND fidelity IN ('exact','partial') "
        "ORDER BY at, percept_id", (holder_id, turn_index - 1, turn_index, at))]
    done = {r[0] for r in tx.query("SELECT json_extract(payload,'$.event_id') FROM events WHERE type='TEMPER_CHANGE' AND actor_id=?",
                                    (holder_id,))}
    seen_sources = {r["source_id"] for r in rows if r["channel"] == "visual" and r["source_id"]}
    aa = tx.query_one("SELECT accepted_authority FROM actors WHERE actor_id=?", (holder_id,))
    authority = set(_j.loads(aa[0])) if aa else set()
    rels = {r[0]: r[1] for r in tx.query("SELECT to_id, affection FROM relationships WHERE from_id=?", (holder_id,))}
    out = []
    got = set()

    def add(toward, kind, eid):
        if (kind, eid) in got or eid in done:
            return
        got.add((kind, eid))
        out.append(Provocation(toward, kind, eid))

    evcache = {}

    def ev(eid):
        if eid not in evcache:
            r = tx.query_one("SELECT type, actor_id, payload FROM events WHERE event_id=?", (eid,))
            evcache[eid] = None if r is None else (r[0], r[1], _j.loads(r[2]) if isinstance(r[2], str) else r[2])
        return evcache[eid]

    for p in rows:
        eid = p["event_id"]
        if not eid or eid.startswith("scene:") or eid in done:
            continue
        e = ev(eid)
        if e is None:
            continue
        typ, _actor, pl = e
        src = p["source_id"]
        det = _j.loads(p["detail"]) if isinstance(p["detail"], str) else (p["detail"] or {})
        human_src = bool(src) and src != holder_id and src.startswith("act_")
        ch = p["channel"]
        if ch == "tactile" and human_src:
            add(src, "struck", eid)
        if ch == "visual" and typ == "ACTION_START" and human_src and pl.get("target_id") == holder_id:
            if pl.get("def_id") == "shove":
                add(src, "shoved", eid)
            elif pl.get("def_id") in ("grapple", "disarm"):
                add(src, "grabbed", eid)
        if ch == "speech" and human_src and det.get("addressed_to_me"):
            words = det.get("words", "") or ""
            form = classify_form(words, weapon_pointed_at_receiver=bool(det.get("armed_at_me")))
            if form == UtteranceForm.THREAT:
                add(src, "threatened", eid)
            if form in (UtteranceForm.ORDER, UtteranceForm.DEMAND) and src not in authority:
                add(src, "ordered_about", eid)
            if any(_words_have(words, x) for x in INSULT_WORDS):
                add(src, "insulted", eid)
        if ch == "visual" and typ == "HARM":
            who = pl.get("actor_id")
            if (pl.get("body_id") and rels.get(pl["body_id"], 0) >= 2 and who and who != holder_id
                    and who in seen_sources):
                add(who, "harmed_bonded", eid)
        if ch == "visual" and typ == "ITEM_TRANSFER" and human_src:
            item = pl.get("item_id")
            owners = [r[0] for r in tx.query(
                "SELECT p.object_value FROM claim_holdings h JOIN propositions p ON p.prop_id=h.claim_id WHERE h.holder_id=? "
                "AND h.superseded_by IS NULL AND h.believed=1 AND p.subject_type='object' AND p.subject_id=? AND p.predicate='owner'",
                (holder_id, item))] if item else []
            if holder_id in owners:
                add(src, "stole_from", eid)
    order = {k: i for i, k in enumerate(("struck", "shoved", "grabbed", "threatened", "ordered_about", "insulted",
                                          "harmed_bonded", "stole_from"))}
    # per event, kinds in the documented order; events in percept order
    firsts = {}
    for i, pv in enumerate(out):
        firsts.setdefault(pv.event_id, i)
    return sorted(out, key=lambda pv: (firsts[pv.event_id], order[pv.kind]))


def provoke(tx: "Tx", holder_id: str, toward_id: str, kind: str, event_id: str, at: int,
            turn_index: int) -> "Event":
    from ..contracts.events import Event, EventType, WriteOp, WriteRecord
    from ..kernel.events import committed_or_none
    from .actor import adjust_stress
    R = tx.rules.temper
    h = min(20, heat(tx, holder_id, toward_id, at) + R.provocation_heat[kind])
    exists = tx.query_one("SELECT 1 FROM tempers WHERE holder_id=? AND toward_id=?", (holder_id, toward_id)) is not None
    vals = {"heat": h, "updated_at": at, "last_kind": kind}
    w = (WriteRecord(op=WriteOp.UPDATE, table="tempers", key={"holder_id": holder_id, "toward_id": toward_id}, values=vals)
         if exists else WriteRecord(op=WriteOp.INSERT, table="tempers", values={"holder_id": holder_id, "toward_id": toward_id, **vals}))
    ev = tx.commit_event(Event(type=EventType.TEMPER_CHANGE, writer="mind.temper", at=at, turn_index=turn_index,
                               actor_id=holder_id, cause_event_id=committed_or_none(tx, event_id), writes=[w],
                               payload={"holder_id": holder_id, "toward_id": toward_id, "kind": kind, "event_id": event_id,
                                        "heat": h}))
    if kind in R.stress_from:
        adjust_stress(tx, holder_id, R.stress_from[kind], ev.event_id, at, turn_index)
    return ev


def _set_heat(tx, holder_id, toward_id, h, kind, event_id, cause, at, turn_index):
    from ..contracts.events import Event, EventType, WriteOp, WriteRecord
    return tx.commit_event(Event(type=EventType.TEMPER_CHANGE, writer="mind.temper", at=at, turn_index=turn_index,
                                 actor_id=holder_id, cause_event_id=cause,
                                 writes=[WriteRecord(op=WriteOp.UPDATE, table="tempers",
                                                     key={"holder_id": holder_id, "toward_id": toward_id},
                                                     values={"heat": h, "updated_at": at, "last_kind": kind})],
                                 payload={"holder_id": holder_id, "toward_id": toward_id, "kind": kind, "event_id": event_id,
                                          "heat": h}))


def take_in(tx: "Tx", rng: "Rng", holder_id: str, turn_index: int, at: int) -> Outburst | None:
    import json as _j
    from ..contracts.events import Event, EventType
    from . import mind as mindmod
    from .actor import adjust_stress
    from .perception import word_for
    from .resolve import drain
    provs = provocations(tx, holder_id, turn_index, at) + exposures(tx, holder_id, turn_index, at)
    for pv in provs:
        provoke(tx, holder_id, pv.toward_id, pv.kind, pv.event_id, at, turn_index)
    if not provs:
        return None
    pc = tx.query_one("SELECT value FROM meta WHERE key='pc_actor_id'")
    if pc and pc[0] == holder_id:
        return None
    last = {}
    for i, pv in enumerate(provs):
        last[pv.toward_id] = (i, pv.event_id)
    T = max(last, key=lambda x: (heat(tx, holder_id, x, at), last[x][0]))
    h = heat(tx, holder_id, T, at)
    if h < threshold(tx, holder_id):
        return None
    E = last[T][1]
    R = tx.rules.temper
    res = tx.query_one("SELECT resolve_cur FROM actors WHERE actor_id=?", (holder_id,))[0]
    if rng.chance(tx, "mind", f"hold:{holder_id}:{E}", min(R.hold_max, R.hold_per_resolve * res)):
        drain(tx, holder_id, "held_temper", E, at, turn_index)
        return None
    tm = temper_of(tx, holder_id)
    out = tx.commit_event(Event(type=EventType.INVOLUNTARY, writer="mind.temper", at=at, turn_index=turn_index, actor_id=holder_id,
                                cause_event_id=E, payload={"actor_id": holder_id, "kind": "outburst", "outlet": tm.outlet,
                                                           "toward_id": T}))
    _set_heat(tx, holder_id, T, h // 2, "vented", E, out.event_id, at, turn_index)
    adjust_stress(tx, holder_id, -1, out.event_id, at, turn_index)
    if tm.grudge > 0:
        loops = [dict(r) for r in tx.query("SELECT * FROM open_loops WHERE holder_id=? AND kind='grudge' AND status='open' "
                                              "ORDER BY created_at, loop_id", (holder_id,))]
        mine = [lp for lp in loops if T in _j.loads(lp["subject_ids"])]
        if mine:
            mindmod.strengthen_loop(tx, mine[0]["loop_id"], 1, out.event_id, at, turn_index)
        else:
            mindmod.open_loop(tx, holder_id, "grudge", f"{word_for(tx, holder_id, T)} pushed me too far", [T], tm.grudge,
                              out.event_id, at, turn_index)
        mindmod.relate(tx, holder_id, T, "resentment", 1, out.event_id, at, turn_index)
    return Outburst(T, tm.outlet, E)



def exposures(tx: "Tx", holder_id: str, turn_index: int, at: int) -> list[Provocation]:
    from ..physical.objects import coverage
    from ..sense.olfaction import odour_of, smells
    me = tx.query_one("SELECT kind FROM bodies WHERE body_id=?", (holder_id,))
    if me is None or me[0] != "human":
        return []
    C = tx.rules.condition
    seen = {r[0] for r in tx.query(
        "SELECT source_id FROM percept_log WHERE holder_id=? AND turn_index IN (?, ?) AND at<=? AND channel='visual' "
        "AND fidelity IN ('exact','partial') AND source_id IS NOT NULL", (holder_id, turn_index - 1, turn_index, at))}

    def recent(toward, kind, mins):
        return tx.query_one("SELECT 1 FROM events WHERE type='TEMPER_CHANGE' AND actor_id=? AND json_extract(payload,'$.toward_id')=? "
                            "AND json_extract(payload,'$.kind')=? AND at>?", (holder_id, toward, kind, at - mins * 60_000)) is not None
    out = []
    for r in tx.query("SELECT body_id, age_years, looks FROM bodies WHERE alive=1 AND kind='human' AND body_id<>? ORDER BY body_id",
                      (holder_id,)):
        s = r["body_id"]
        o = odour_of(tx, s, at)
        if o is not None and o.kind == "dead" and smells(tx, holder_id, s, at) == "exact" and not recent(s, "reeked", C.reek_every_min):
            out.append(Provocation(s, "reeked", None))
        if (s in seen and r["age_years"] is not None and r["age_years"] >= 18 and r["looks"] is not None
                and not ({"torso", "groin"} & coverage(tx, s)) and not recent(s, "bared", C.bared_every_min)):
            out.append(Provocation(s, "bared", None))
    return out