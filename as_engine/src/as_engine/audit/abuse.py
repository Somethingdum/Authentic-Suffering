"""Abuse battery (P11). Rules ABUSE-01..08. [SALVAGE: IRONCLAD Step 9] — run by code against the
author, because the author is the threat: whoever wrote the content, the worldgen model, a bug, a
cheat that leaked. Each check reads a world (read-only) and returns findings; a clean world
returns none. The release audit (audit/release.py) runs the whole battery.

AbuseFinding(rule, subject, text): the rule id, the row it is about (a body, item, event,
settlement or meta key id) and one plain sentence. Every check lists its findings ordered by
subject, then text.

ABUSE-01 stat_bands(tx) — nobody is born a superman. For every body whose origin is not 'cheat'
  (by body_id):
    kind 'human' or 'lurker': bodies.special must be exactly the seven letters S P E C I A L,
      each a whole number 1..10 -> else f"{body_id}'s SPECIAL is not seven values from 1 to 10";
      when the body's actors row names a dossier whose source is 'generated', each letter must lie
      in GENERATED_BAND (3..7, the worldgen draw: world.worldgen.people) -> else
      f"{body_id}'s {letter} is {v}, outside the 3..7 of a generated person" (per letter, SPECIAL
      order);
    kind 'infected' with an infected_state row: each letter its type (the canon 'infected' record
      whose id is infected_state.type_id) gives a range for must lie in it -> else
      f"{body_id}'s {letter} is {v}, outside {lo}..{hi} for {type id}".
ABUSE-02 mortality(tx) — nobody is passively immune. god = the JSON list in meta 'god_bodies'
  (absent or unparsable = []; the P12 god mode):
    god non-empty while meta 'sandbox' != '1' -> subject 'god_bodies', f"god mode is on in a
      run that is not a sandbox ({n} bodies)";
    every living body (alive 1) of kind human, lurker or animal not in god (when the run is a
      sandbox; outside one, god protects nobody), by body_id — what the death test (physical.bodies
      DEATH-01..05) would already have killed:
      blood_loss_pct >= rules.harm.death_at_blood_loss_pct -> f"{body_id} is alive with
        {pct:g}% of their blood lost";
      a needs stage (thirst, hunger, cold or heat) >= rules.needs.death_stage ->
        f"{body_id} is alive at {need} stage {stage}";
      an unhealed (healed_at NULL) catastrophic wound whose ANATOMY_GROUP is head or neck ->
        f"{body_id} is alive with a catastrophic {anatomy} wound".
ABUSE-03 check_caps(tx) — no synergy breaks the ladder. Every CHECK_RESOLVED event (by seq),
  with R = rules.checks and p its payload:
    formula = attr_mod(attr_value) + skill_rank + tag_bonus + situation + scale
              - impairment // 2 - resistance;
    each problem is one finding (subject the event id, text f"{def_id} by {actor_id}: " + one of):
    'target {t} is not the clamped formula {v}' when target != clamp(formula,
    R.target_min, R.target_max); 'tag bonus {b} stacks' when tag_bonus not in (0, R.tag_bonus);
    'skill rank {r} is outside 0..3'; 'situation {s} is outside -3..3'; 'scale {s} is outside
    -2..2'; 'resistance {r} is negative'; 'draw {d} is outside 1..{R.die_sides}'; 'margin {m} is
    not target minus draw'; 'band {b} does not match margin {m}' when band !=
    action.checks.band_for_margin(margin, R).
ABUSE-04 gear_limits(tx) — no free guns or bottomless magazines. Every items row (by item_id):
    a def that is not stackable with qty > 1 -> f"{qty} {plural} in one row: a {name} does not
      stack";
    a firearm def whose feeds_from is 'internal' or 'cylinder': rounds = props.rounds (0 when
      absent) must be 0..capacity -> else f"{rounds} rounds in a {name} that holds {capacity}";
    a def of kind 'magazine' whose container is an item with a firearm def: rounds 0..that
      firearm's capacity -> else the same sentence with the firearm's name and capacity.
ABUSE-05 ways_in(tx) — no fortress the world cannot touch. Every settlement with a place_id (by
    settlement_id) whose place has no portal at all (neither place_a nor place_b) ->
    f"{name} has no way in".
ABUSE-06 no_farming(tx) — doing the same thing again yields nothing new. Loot is rolled once, when
  a building's rooms are first discovered (physical.space.discover_layout, idempotent):
    a place with more than one PLACE_DISCOVERED event whose payload.source is 'discovery' ->
      subject the place, f"{place_id}'s rooms were discovered {n} times";
    an ITEM_CREATED event whose payload.origin is 'loot' and whose cause_event_id is not a
      PLACE_DISCOVERED event -> subject the event id, f"loot {def_ref} came from
      {the cause's type or 'nothing'}, not from a discovery".
ABUSE-07 clock_sync(tx) — every body lives in the world's time. Every living body with a
    positions row (by body_id; a body folded into a count has none) whose progressed_at !=
    world_clock.now_ms -> f"{body_id}'s clocks stand {minutes:g} minutes {'behind' | 'ahead of'}
    the world" (minutes = |difference| / 60000).
ABUSE-08 cheat_leakage(tx) — a cheat never leaks into a clean run (CHEAT-02). When meta 'sandbox'
  != '1': each of these that exists is one finding (subject the table or 'meta'):
    meta 'cheat_active' != '0' -> 'cheats are active in a run that is not a sandbox';
    events with origin 'cheat', bodies or items with origin 'cheat', dossiers with source
      'cheat', player_inputs with mode 'cheat', story_log rows with kind 'cheat', cheat_log rows
      -> f"{what} in a run that is not a sandbox: {n}" (what: 'cheat events', 'cheat-made bodies',
      'cheat-made items', 'cheat-made dossiers', 'cheat inputs', 'cheat story lines', 'cheat log
      rows').
  In a sandbox: every actors row whose body has origin 'cheat' must have quarantine 1 -> else
    subject the actor, f"{actor_id} was made by a cheat and still counts in the world's sums".
battery(tx) -> list[AbuseFinding]: the eight checks, ABUSE-01 first.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..kernel.store import Tx

GENERATED_BAND = (3, 7)
LETTERS = "SPECIAL"


@dataclass(frozen=True)
class AbuseFinding:
    rule: str
    subject: str
    text: str


def _sorted(out: list[AbuseFinding]) -> list[AbuseFinding]:
    return sorted(out, key=lambda f: (f.subject, f.text))


def _meta(tx: "Tx", key: str) -> str | None:
    r = tx.query_one("SELECT value FROM meta WHERE key=?", (key,))
    return None if r is None else r[0]


def stat_bands(tx: "Tx") -> list[AbuseFinding]:
    types = {t.id: t for t in tx.canon.all("infected")}
    out = []
    for b in tx.query("SELECT b.body_id, b.kind, b.special, d.source, s.type_id FROM bodies b "
                      "LEFT JOIN actors a ON a.actor_id = b.body_id LEFT JOIN dossiers d ON d.dossier_id = a.dossier_id "
                      "LEFT JOIN infected_state s ON s.body_id = b.body_id WHERE b.origin != 'cheat' ORDER BY b.body_id"):
        sp = json.loads(b["special"])
        if b["kind"] in ("human", "lurker"):
            if sorted(sp) != sorted(LETTERS) or not all(isinstance(v, int) and 1 <= v <= 10 for v in sp.values()):
                out.append(AbuseFinding("ABUSE-01", b["body_id"], f"{b['body_id']}'s SPECIAL is not seven values from 1 to 10"))
                continue
            if b["source"] == "generated":
                lo, hi = GENERATED_BAND
                out += [AbuseFinding("ABUSE-01", b["body_id"], f"{b['body_id']}'s {L} is {sp[L]}, outside the 3..7 of a generated person")
                        for L in LETTERS if not lo <= sp[L] <= hi]
        elif b["kind"] == "infected" and b["type_id"] in types:
            t = types[b["type_id"]]
            for L in LETTERS:
                rng = t.special.get(L)
                if rng is not None and L in sp and not rng.lo <= sp[L] <= rng.hi:
                    out.append(AbuseFinding("ABUSE-01", b["body_id"],
                                            f"{b['body_id']}'s {L} is {sp[L]}, outside {rng.lo}..{rng.hi} for {t.id}"))
    return _sorted(out)


def mortality(tx: "Tx") -> list[AbuseFinding]:
    from ..contracts.common import ANATOMY_GROUP
    try:
        god = list(json.loads(_meta(tx, "god_bodies") or "[]"))
    except (ValueError, TypeError):
        god = []
    sandbox = _meta(tx, "sandbox") == "1"
    out = []
    if god and not sandbox:
        out.append(AbuseFinding("ABUSE-02", "god_bodies", f"god mode is on in a run that is not a sandbox ({len(god)} bodies)"))
    spared = set(god) if sandbox else set()
    H, N = tx.rules.harm, tx.rules.needs
    for b in tx.query("SELECT b.body_id, b.blood_loss_pct, n.thirst_stage, n.hunger_stage, n.cold_stage, n.heat_stage "
                      "FROM bodies b LEFT JOIN needs n ON n.body_id = b.body_id "
                      "WHERE b.alive = 1 AND b.kind IN ('human','lurker','animal') ORDER BY b.body_id"):
        bid = b["body_id"]
        if bid in spared:
            continue
        if b["blood_loss_pct"] >= H.death_at_blood_loss_pct:
            out.append(AbuseFinding("ABUSE-02", bid, f"{bid} is alive with {b['blood_loss_pct']:g}% of their blood lost"))
        for need in ("thirst", "hunger", "cold", "heat"):
            st = b[f"{need}_stage"]
            if st is not None and st >= N.death_stage:
                out.append(AbuseFinding("ABUSE-02", bid, f"{bid} is alive at {need} stage {st}"))
        for w in tx.query("SELECT anatomy FROM wounds WHERE body_id=? AND healed_at IS NULL AND severity='catastrophic' "
                          "ORDER BY wound_id", (bid,)):
            if ANATOMY_GROUP.get(w[0]) in ("head", "neck"):
                out.append(AbuseFinding("ABUSE-02", bid, f"{bid} is alive with a catastrophic {w[0]} wound"))
    return _sorted(out)


def check_caps(tx: "Tx") -> list[AbuseFinding]:
    from ..action.checks import band_for_margin
    from ..contracts.common import attr_mod
    R = tx.rules.checks
    out = []
    for e in tx.query("SELECT event_id, payload FROM events WHERE type='CHECK_RESOLVED' ORDER BY seq"):
        p = json.loads(e[1])
        head = f"{p.get('def_id')} by {p.get('actor_id')}: "
        probs = []
        formula = (attr_mod(p["attr_value"]) + p["skill_rank"] + p["tag_bonus"] + p["situation"] + p["scale"]
                   - p["impairment"] // 2 - p["resistance"])
        if p["target"] != max(R.target_min, min(R.target_max, formula)):
            probs.append(f"target {p['target']} is not the clamped formula {formula}")
        if p["tag_bonus"] not in (0, R.tag_bonus):
            probs.append(f"tag bonus {p['tag_bonus']} stacks")
        if not 0 <= p["skill_rank"] <= 3:
            probs.append(f"skill rank {p['skill_rank']} is outside 0..3")
        if not -3 <= p["situation"] <= 3:
            probs.append(f"situation {p['situation']} is outside -3..3")
        if not -2 <= p["scale"] <= 2:
            probs.append(f"scale {p['scale']} is outside -2..2")
        if p["resistance"] < 0:
            probs.append(f"resistance {p['resistance']} is negative")
        if not 1 <= p["draw"] <= R.die_sides:
            probs.append(f"draw {p['draw']} is outside 1..{R.die_sides}")
        if p["margin"] != p["target"] - p["draw"]:
            probs.append(f"margin {p['margin']} is not target minus draw")
        if p["band"] != band_for_margin(p["margin"], R).value:
            probs.append(f"band {p['band']} does not match margin {p['margin']}")
        out += [AbuseFinding("ABUSE-03", e[0], head + x) for x in probs]
    return _sorted(out)


def gear_limits(tx: "Tx") -> list[AbuseFinding]:
    out = []
    for it in tx.query("SELECT i.item_id, i.def_ref, i.qty, i.props, c.def_ref AS container_def FROM items i "
                       "LEFT JOIN items c ON c.item_id = i.container_id ORDER BY i.item_id"):
        d = tx.canon.get(it["def_ref"])
        iid = it["item_id"]
        if not d.stackable and it["qty"] > 1:
            out.append(AbuseFinding("ABUSE-04", iid, f"{it['qty']} {d.plural} in one row: a {d.name} does not stack"))
        rounds = int(json.loads(it["props"]).get("rounds", 0))
        gun = None
        if d.firearm is not None and d.firearm.feeds_from in ("internal", "cylinder"):
            gun = d
        elif d.kind == "magazine" and it["container_def"] is not None:
            c = tx.canon.get(it["container_def"])
            gun = c if c.firearm is not None else None
        if gun is not None and not 0 <= rounds <= gun.firearm.capacity:
            out.append(AbuseFinding("ABUSE-04", iid, f"{rounds} rounds in a {gun.name} that holds {gun.firearm.capacity}"))
    return _sorted(out)


def ways_in(tx: "Tx") -> list[AbuseFinding]:
    out = []
    for s in tx.query("SELECT settlement_id, name, place_id FROM settlements WHERE place_id IS NOT NULL ORDER BY settlement_id"):
        if tx.query_one("SELECT 1 FROM portals WHERE place_a=? OR place_b=?", (s[2], s[2])) is None:
            out.append(AbuseFinding("ABUSE-05", s[0], f"{s[1]} has no way in"))
    return _sorted(out)


def no_farming(tx: "Tx") -> list[AbuseFinding]:
    out = []
    for r in tx.query("SELECT json_extract(payload,'$.place_id') AS pid, COUNT(*) AS n FROM events WHERE type='PLACE_DISCOVERED' "
                      "AND json_extract(payload,'$.source')='discovery' GROUP BY pid HAVING n > 1"):
        out.append(AbuseFinding("ABUSE-06", r[0], f"{r[0]}'s rooms were discovered {r[1]} times"))
    for e in tx.query("SELECT e.event_id, json_extract(e.payload,'$.def_ref') AS def_ref, c.type AS cause FROM events e "
                      "LEFT JOIN events c ON c.event_id = e.cause_event_id WHERE e.type='ITEM_CREATED' "
                      "AND json_extract(e.payload,'$.origin')='loot' AND (c.type IS NULL OR c.type != 'PLACE_DISCOVERED')"):
        out.append(AbuseFinding("ABUSE-06", e[0], f"loot {e[1]} came from {e[2] or 'nothing'}, not from a discovery"))
    return _sorted(out)


def clock_sync(tx: "Tx") -> list[AbuseFinding]:
    now = tx.query_one("SELECT now_ms FROM world_clock")[0]
    out = []
    for b in tx.query("SELECT b.body_id, b.progressed_at FROM bodies b JOIN positions p ON p.body_id = b.body_id "
                      "WHERE b.alive = 1 AND b.progressed_at != ? ORDER BY b.body_id", (now,)):
        gap = b[1] - now
        out.append(AbuseFinding("ABUSE-07", b[0], f"{b[0]}'s clocks stand {abs(gap) / 60000:g} minutes "
                                                  f"{'behind' if gap < 0 else 'ahead of'} the world"))
    return _sorted(out)


_LEAKS = (
    ("events", "SELECT COUNT(*) FROM events WHERE origin='cheat'", "cheat events"),
    ("bodies", "SELECT COUNT(*) FROM bodies WHERE origin='cheat'", "cheat-made bodies"),
    ("items", "SELECT COUNT(*) FROM items WHERE origin='cheat'", "cheat-made items"),
    ("dossiers", "SELECT COUNT(*) FROM dossiers WHERE source='cheat'", "cheat-made dossiers"),
    ("player_inputs", "SELECT COUNT(*) FROM player_inputs WHERE mode='cheat'", "cheat inputs"),
    ("story_log", "SELECT COUNT(*) FROM story_log WHERE kind='cheat'", "cheat story lines"),
    ("cheat_log", "SELECT COUNT(*) FROM cheat_log", "cheat log rows"),
)


def cheat_leakage(tx: "Tx") -> list[AbuseFinding]:
    out = []
    if _meta(tx, "sandbox") != "1":
        if _meta(tx, "cheat_active") != "0":
            out.append(AbuseFinding("ABUSE-08", "meta", "cheats are active in a run that is not a sandbox"))
        for table, sql, what in _LEAKS:
            n = tx.query_one(sql)[0]
            if n:
                out.append(AbuseFinding("ABUSE-08", table, f"{what} in a run that is not a sandbox: {n}"))
        return _sorted(out)
    for r in tx.query("SELECT a.actor_id FROM actors a JOIN bodies b ON b.body_id = a.actor_id "
                      "WHERE b.origin='cheat' AND a.quarantine != 1 ORDER BY a.actor_id"):
        out.append(AbuseFinding("ABUSE-08", r[0], f"{r[0]} was made by a cheat and still counts in the world's sums"))
    return _sorted(out)


CHECKS = (stat_bands, mortality, check_caps, gear_limits, ways_in, no_farming, clock_sync, cheat_leakage)


def battery(tx: "Tx") -> list[AbuseFinding]:
    out: list[AbuseFinding] = []
    for check in CHECKS:
        out += check(tx)
    return out
