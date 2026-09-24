"""Test helpers (PROTECTED — docs/as/12_TESTING.md §6). Import as ``import helpers``."""

from __future__ import annotations

from typing import Any


def handle_for(packet: Any, def_id: str, target_local: str | None = None, world: Any = None) -> str:
    """The A-handle of the option built from ``def_id`` whose target / destination / item is the
    fixture-local id ``target_local`` (resolved through ``world.id``). Accepts a SkullPacket or any
    context object with a ``.packet`` attribute. Raises AssertionError listing the options when
    nothing matches, so a failing test shows what WAS offered."""
    pkt = getattr(packet, "packet", packet)
    wanted = world.id(target_local) if (world is not None and target_local is not None) else target_local
    offered = []
    for opt in pkt.affordances:
        sig = pkt.handles.get(opt.handle, "")
        parts = sig.split(":")
        offered.append(f"{opt.handle}={sig} ({opt.label})")
        if not parts or parts[0] != def_id:
            continue
        if wanted is None or wanted in parts[1:]:
            return opt.handle
    raise AssertionError(f"no option {def_id} -> {target_local!r}; offered:\n  " + "\n  ".join(offered))


def option_defs(packet: Any) -> set[str]:
    """Set of def_ids offered in a packet."""
    pkt = getattr(packet, "packet", packet)
    return {pkt.handles.get(o.handle, "").split(":")[0] for o in pkt.affordances}


def percepts_of(store: Any, holder_id: str, turn: int | None = None) -> list[Any]:
    """percept_log rows for one holder (optionally one turn), in seq order."""
    sql = "SELECT * FROM percept_log WHERE holder_id = ?"
    params: list[Any] = [holder_id]
    if turn is not None:
        sql += " AND turn_index = ?"
        params.append(turn)
    return store.query(sql + " ORDER BY at, percept_id", tuple(params))


def holdings_of(store: Any, holder_id: str) -> list[Any]:
    """claim_holdings rows (with the proposition text joined) for one holder."""
    return store.query(
        "SELECT h.*, COALESCE(p.text, c.predicate || ' ' || COALESCE(c.object_value, '')) AS text "
        "FROM claim_holdings h LEFT JOIN propositions p ON p.prop_id = h.claim_id "
        "LEFT JOIN claims c ON c.claim_id = h.claim_id "
        "WHERE h.holder_id = ? ORDER BY h.acquired_at, h.claim_id", (holder_id,))


def events_of(store: Any, type_: str, turn: int | None = None) -> list[Any]:
    """Event rows of one type (optionally one turn), in seq order."""
    sql = "SELECT * FROM events WHERE type = ?"
    params: list[Any] = [type_]
    if turn is not None:
        sql += " AND turn_index = ?"
        params.append(turn)
    return store.query(sql + " ORDER BY seq", tuple(params))


def ledger_draws(store: Any, turn: int | None = None) -> list[Any]:
    """prng_ledger rows (optionally one turn), in seq order."""
    if turn is None:
        return store.query("SELECT * FROM prng_ledger ORDER BY seq")
    return store.query("SELECT * FROM prng_ledger WHERE turn_index = ? ORDER BY seq", (turn,))


def text_of_percepts(rows: list[Any]) -> str:
    """All percept texts of the given rows joined with newlines (lower-cased), for containment checks."""
    return "\n".join((r["text"] or "") for r in rows).lower()


def make_intent(world: Any, actor_local: str, def_id: str, target: str | None = None,
                destination: str | None = None, item: str | None = None, *, est_s: float | None = None,
                speech: Any = None, manner: str = "", source: str = "model", label: str | None = None,
                goal: str | None = None) -> Any:
    """An Intent built straight from a core AffordanceDef, bypassing enumeration and selection (P5+
    tests exercise the resolver, not the menu). Local ids are resolved through ``world.id`` (a
    value that is not a local id is used as given). est_s defaults to the def's base_s plus
    per_meter_s x the straight-line distance from the actor to the destination/target point when
    that is an anchor or body in its place. ``speech`` = (text, [local ids] or ['everyone'], volume).
    ``label`` (the option label) and ``goal`` default to the def id."""
    import math

    from as_engine.action.intent import Intent, SpeechAct
    from as_engine.contracts.common import LOD, Volume
    from as_engine.mind.affordance import BoundAffordance

    def real(x):
        return None if x is None else world.ids.get(x, x)

    d = world.canon.find("affordance", def_id)
    actor = world.id(actor_local)
    t, dest, it = real(target), real(destination), real(item)
    if est_s is None:
        est_s = d.duration.base_s
        pos = world.store.query_one("SELECT place_id, x_m, y_m FROM positions WHERE body_id = ?", (actor,))
        pt = None
        for ref in (dest, t):
            if ref and ref.startswith("anc_"):
                pt = world.store.query_one("SELECT place_id, x_m, y_m FROM anchors WHERE anchor_id = ?", (ref,))
            elif ref and ref.startswith("act_"):
                pt = world.store.query_one("SELECT place_id, x_m, y_m FROM positions WHERE body_id = ?", (ref,))
            if pt is not None:
                break
        if pt is not None and pt[0] == pos[0]:
            est_s += d.duration.per_meter_s * math.hypot(pt[1] - pos[1], pt[2] - pos[2])
    bound = BoundAffordance(def_id=def_id, verb=d.verb, label=label or def_id, ui_label=def_id, target_id=t, destination_id=dest,
                            item_id=it, est_duration_s=est_s, noise_db=d.noise_db, check=d.check, tags=tuple(d.tags))
    sp = None
    if speech is not None:
        text, to, vol = speech
        sp = SpeechAct(text=text, to=tuple(real(x) if x != "everyone" else x for x in to), volume=Volume(vol))
    return Intent(actor_id=actor, bound=bound, speech=sp, manner=manner, goal=goal or def_id, private_reason="", source=source,
                  lod=LOD.WARM)


class ScriptedRng:
    """Deterministic stand-in for kernel.rng.Rng in P5+ tests: returns scripted values in order for
    d10 / draw / range_int / chance / choice / weighted / shuffle calls (weighted and choice take an
    index into the items; shuffle returns the list unchanged). Records every (method, stream,
    purpose). An exhausted script raises AssertionError naming the purpose that asked."""

    def __init__(self, *values: Any):
        self.values = list(values)
        self.asked: list[tuple[str, str, str]] = []

    def _next(self, method: str, stream: str, purpose: str) -> Any:
        self.asked.append((method, stream, purpose))
        if not self.values:
            raise AssertionError(f"ScriptedRng exhausted at {method}({stream!r}, {purpose!r})")
        return self.values.pop(0)

    def d10(self, tx: Any, stream: str, purpose: str) -> int:
        return self._next("d10", stream, purpose)

    def draw(self, tx: Any, stream: str, purpose: str, n: int) -> int:
        return self._next("draw", stream, purpose)

    def range_int(self, tx: Any, stream: str, purpose: str, lo: int, hi: int) -> int:
        return self._next("range_int", stream, purpose)

    def chance(self, tx: Any, stream: str, purpose: str, p: float) -> bool:
        return self._next("chance", stream, purpose)

    def choice(self, tx: Any, stream: str, purpose: str, seq: Any) -> Any:
        return seq[self._next("choice", stream, purpose)]

    def weighted(self, tx: Any, stream: str, purpose: str, items: Any) -> Any:
        return items[self._next("weighted", stream, purpose)][0]

    def shuffle(self, tx: Any, stream: str, purpose: str, seq: Any) -> list:
        self.asked.append(("shuffle", stream, purpose))
        return list(seq)
