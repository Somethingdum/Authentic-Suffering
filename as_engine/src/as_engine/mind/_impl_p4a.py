"""Implementation: mind.resolve, mind.firewall, mind.actor (P4 parts)."""
from __future__ import annotations

import json
import re

from ..contracts.common import ResponseClass, Standing, UtteranceForm, Verb
from ..contracts.events import Event, EventType, WriteOp, WriteRecord


def _row(s, sql, params=()):
    r = s.query_one(sql, params)
    return dict(r) if r is not None else None


# ---------------------------------------------------------------- actor
def resolve_max(E, C, trait_mod, rules):
    return max(1, rules.base + (E + C) // rules.divisor + trait_mod)


def fused(store, actor_id):
    from ..contracts.dossier import ActorDossier, PCDossier
    a = _row(store, "SELECT d.baseline_json FROM actors a JOIN dossiers d ON d.dossier_id=a.dossier_id WHERE a.actor_id=?", (actor_id,))
    d = json.loads(a["baseline_json"])
    for r in store.query("SELECT * FROM dossier_deltas WHERE actor_id=? ORDER BY at, delta_id", (actor_id,)):
        parts = r["path"].split(".")
        cur = d
        for p in parts[:-1]:
            if not isinstance(cur, dict) or p not in cur:
                raise ValueError(f"unknown dossier path {r['path']}")
            cur = cur[p]
        last = parts[-1]
        if not isinstance(cur, dict) or last not in cur:
            raise ValueError(f"unknown dossier path {r['path']}")
        v = json.loads(r["value_json"])
        if r["op"] == "set":
            cur[last] = v
        elif r["op"] == "append":
            cur[last].append(v)
        else:
            if v not in cur[last]:
                raise ValueError(f"{r['path']}: nothing equal to remove")
            cur[last].remove(v)
    return (PCDossier if "card" in d else ActorDossier).model_validate(d)


def display_name(store, actor_id):
    return _row(store, "SELECT display_name FROM actors WHERE actor_id=?", (actor_id,))["display_name"]


def recent_lines(store, actor_id, n):
    pinned = [r["text"] for r in store.query("SELECT text FROM voice_lines WHERE actor_id=? AND pinned=1 ORDER BY at, line_id", (actor_id,))]
    if len(pinned) >= n:
        return pinned[:n]
    rest = [r["text"] for r in store.query("SELECT text FROM voice_lines WHERE actor_id=? AND pinned=0 ORDER BY at DESC, line_id DESC LIMIT ?", (actor_id, n - len(pinned)))]
    return pinned + list(reversed(rest))


# ---------------------------------------------------------------- resolve
_RECOVER = {"safe_night": "recover_per_safe_night", "fulfilled_obligation": "recover_fulfilled_obligation",
            "protected_dependent": "recover_protected_dependent", "shock_passes": "recover_shock_passes"}


def _resolve_change(tx, actor_id, new, delta, reason, cause, at, ti):
    return tx.commit_event(Event(type=EventType.RESOLVE_CHANGE, writer="mind.actor", at=at, turn_index=ti, actor_id=actor_id,
                                 cause_event_id=cause, writes=[WriteRecord(op=WriteOp.UPDATE, table="actors", key={"actor_id": actor_id}, values={"resolve_cur": new})],
                                 payload={"actor_id": actor_id, "reason": reason, "delta": delta, "resolve": new}))


def drain(tx, actor_id, reason, cause_event_id, at, turn_index):
    R = tx.rules.resolve
    if reason not in R.drains:
        raise ValueError(f"unknown drain {reason}")
    a = _row(tx, "SELECT resolve_cur FROM actors WHERE actor_id=?", (actor_id,))
    new = max(0, a["resolve_cur"] - R.drains[reason])
    if new == a["resolve_cur"]:
        return None
    return _resolve_change(tx, actor_id, new, new - a["resolve_cur"], reason, cause_event_id, at, turn_index)


def recover(tx, actor_id, reason, cause_event_id, at, turn_index):
    R = tx.rules.resolve
    if reason not in _RECOVER:
        raise ValueError(f"unknown recovery {reason}")
    a = _row(tx, "SELECT resolve_cur, resolve_max FROM actors WHERE actor_id=?", (actor_id,))
    new = min(a["resolve_max"], a["resolve_cur"] + getattr(R, _RECOVER[reason]))
    cap = ceiling(tx, actor_id)
    if cap is not None:
        new = min(new, max(cap, a["resolve_cur"]))
    if new == a["resolve_cur"]:
        return None
    return _resolve_change(tx, actor_id, new, new - a["resolve_cur"], reason, cause_event_id, at, turn_index)


def the_talk(tx, actor_id, mind, cause_event_id, at, turn_index):
    a = tx.query_one("SELECT resolve_cur FROM actors WHERE actor_id=?", (actor_id,))
    if a is None:
        return None
    cur = a[0]
    new = {"shattered": 0, "broken": min(cur, 1)}.get(mind, max(0, cur - tx.rules.resolve.drains["the_talk"]))
    if new == cur:
        return None
    return _resolve_change(tx, actor_id, new, new - cur, "the_talk", cause_event_id, at, turn_index)


def ceiling(store_or_tx, actor_id):
    d = store_or_tx.query_one("SELECT mind, shock_over FROM dooms WHERE body_id=?", (actor_id,))
    if d is None:
        return None
    if d[0] == "shattered":
        return 1 if d[1] else 0
    return 1 if d[0] == "broken" else None


def gate(resolve_cur, definition, authority_name=None):
    tags = set(definition.tags)
    if resolve_cur <= 0:
        ok = definition.verb in (Verb.FLEE, Verb.ESCAPE, Verb.SURRENDER, Verb.WAIT, Verb.OBSERVE, Verb.SPEAK, Verb.TAKE_COVER,
                                 Verb.HIDE) or bool(tags & {"protect_dependent", "comply_under_threat", "low_exposure", "despair"})
        return ok, None
    if resolve_cur == 1:
        return (not definition.requires.fear_exposure), None
    if resolve_cur == 2 and "opposes_authority" in tags:
        return True, f"It means going against {authority_name or 'the people in charge'}."
    return True, None


# ---------------------------------------------------------------- firewall

_THREAT = ("or i'll", "or i will", "or else", "i'll kill", "i will kill", "i'll hurt", "i'll shoot", "don't make me", "last warning", "you'll regret")
_OFFER = ("i'll give", "i will give", "i can give", "in exchange", "trade you", "i'll trade", "how about i", "i'll pay", "for your trouble")
_REQUEST = ("please", "could you", "can you", "would you", "will you", "would you mind", "i need you to", "help me")
_CLAIMS = ("i'm in charge", "i am in charge", "that's an order", "orders", "i'm the boss", "you work for me")


def _imperative(t):
    from .firewall import IMPERATIVE_VERBS
    words = t.split()
    if not words:
        return False
    first = words[0]
    if first.endswith(",") and len(words) > 1:
        first = words[1]
    return re.sub(r"[^a-z']", "", first) in IMPERATIVE_VERBS


def classify_form(text, *, weapon_pointed_at_receiver=False):
    t = text.lower().strip()
    imp = _imperative(t)
    if (weapon_pointed_at_receiver and imp) or any(x in t for x in _THREAT):
        return UtteranceForm.THREAT
    if any(x in t for x in _OFFER):
        return UtteranceForm.OFFER
    if any(x in t for x in _REQUEST):
        return UtteranceForm.REQUEST
    if imp:
        return UtteranceForm.ORDER
    if t.endswith("?"):
        return UtteranceForm.QUESTION
    return UtteranceForm.STATEMENT


def classify_standing(tx, speaker_id, receiver_id, text):
    rel = _row(tx, "SELECT trust, fear FROM relationships WHERE from_id=? AND to_id=?", (receiver_id, speaker_id))
    if rel and (rel["trust"] <= -2 or rel["fear"] >= 2):
        return Standing.HOSTILE
    canon = tx.canon if getattr(tx, "canon", None) is not None else tx.store.canon
    rg = [r[0] for r in tx.query("SELECT g.content_ref FROM group_members m JOIN groups g ON g.group_id=m.group_id WHERE m.actor_id=? AND g.content_ref IS NOT NULL", (receiver_id,))]
    sg = {r[0] for r in tx.query("SELECT g.content_ref FROM group_members m JOIN groups g ON g.group_id=m.group_id WHERE m.actor_id=? AND g.content_ref IS NOT NULL", (speaker_id,))}
    for ref in rg:
        if canon.has(ref):
            for rel_ in canon.get(ref).relations:
                if rel_.faction in sg and rel_.stance in ("hostile", "war"):
                    return Standing.HOSTILE
    ra = _row(tx, "SELECT accepted_authority FROM actors WHERE actor_id=?", (receiver_id,))
    if ra and speaker_id in json.loads(ra["accepted_authority"]):
        return Standing.VALID_ORDER
    sa = _row(tx, "SELECT accepted_authority FROM actors WHERE actor_id=?", (speaker_id,))
    if sa and receiver_id in json.loads(sa["accepted_authority"]):
        return Standing.SUBORDINATE
    t = text.lower()
    if any(c in t for c in _CLAIMS):
        return Standing.CLAIMED_AUTHORITY
    if tx.query_one("SELECT 1 FROM acquaintance WHERE holder_id=? AND subject_id=? AND known_name IS NOT NULL", (receiver_id, speaker_id))             or tx.query_one("SELECT 1 FROM relationships WHERE from_id=? AND to_id=?", (receiver_id, speaker_id)):
        return Standing.PEER
    return Standing.STRANGER


def _normalise(text):
    raw = text.strip()
    first = raw.split(" ", 1)
    t = raw
    if len(first) == 2 and first[0].endswith(","):
        t = first[1]
    t = re.sub(r"[^a-z0-9' ]", "", t.lower())
    t = re.sub(r"\s+", " ", t).strip()
    again = True
    while again:
        again = False
        for p in ("would you mind ", "please ", "could you ", "can you ", "would you ", "will you "):
            if t.startswith(p):
                t = t[len(p):]
                again = True
                break
    if t.endswith(" please"):
        t = t[: -len(" please")]
    return t


def request_signature(text, speaker_id, receiver_id, perceived_entities):
    from .firewall import REQUEST_PATTERNS
    t = _normalise(text)
    for pat, tmpl in REQUEST_PATTERNS:
        m = re.match(pat, t)
        if not m:
            continue
        x = None
        if "{x}" in tmpl:
            phrase = (m.groupdict().get("x") or "").strip()
            dfn = tmpl.split(":", 1)[0]
            kind = "portal" if dfn in ("open_portal", "close_portal") else ("anchor" if dfn == "guard_anchor" else None)

            def _best(pref):
                best = None
                for k, v in perceived_entities.items():
                    kk = k.lower()
                    if pref is None:
                        if "|" in kk:
                            continue
                    else:
                        if not kk.startswith(pref + "|"):
                            continue
                        kk = kk[len(pref) + 1:]
                    if kk == phrase or kk in phrase:
                        if best is None or len(kk) > len(best[0]):
                            best = (kk, v)
                return best
            best = (_best(kind) if kind else None) or _best(None)
            x = best[1] if best else "*"
        return tmpl.replace("{speaker}", speaker_id).replace("{x}", x or "*")
    return "*:*"


def _matches(sig, chosen):
    d, t = sig.split(":", 1)
    if d != "*" and d != chosen.def_id:
        return False
    if t != "*" and t not in (chosen.target_id, chosen.destination_id, chosen.item_id):
        return False
    return True


def classify_response(signature, chosen, speech_text, resolve_cur, form, *, entrenched_block, resolve_drained_this_turn,
                      steps_toward=frozenset()):
    from .firewall import ASSENT_TOKENS, CONDITION_TOKENS
    if signature != "*:*" and _matches(signature, chosen):
        if form == UtteranceForm.THREAT and resolve_cur == 0:
            return ResponseClass.COERCED_COMPLIANCE
        if not resolve_drained_this_turn and not chosen.cost_note:
            return ResponseClass.READY_COMPLIANCE
        return ResponseClass.RELUCTANT_COMPLIANCE
    if entrenched_block:
        return ResponseClass.ENTRENCHED_REFUSAL
    s = (speech_text or "").lower()
    if s.rstrip().endswith("?"):
        return ResponseClass.CLARIFYING
    def has(tokens):
        return any(re.search(r"\b" + re.escape(a) + r"\b", s) for a in tokens)
    if s and has(ASSENT_TOKENS):
        if has(CONDITION_TOKENS):
            return ResponseClass.DEFERRED_ASSENT
        tgt = signature.split(":", 1)[1] if ":" in signature else "*"
        near = set(steps_toward) | ({tgt} if tgt != "*" else set())
        if near & {chosen.target_id, chosen.destination_id} - {None}:
            return ResponseClass.PREPARING
        return ResponseClass.UNRESOLVED_ASSENT
    if s and classify_form(s) == UtteranceForm.OFFER:
        return ResponseClass.COUNTER_OFFER
    return ResponseClass.REFUSAL
