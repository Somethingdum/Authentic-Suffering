"""Places, anchors, portals, routes, positions (P2). docs/as/07_RULES.md §Space. Owner 'physical.space'.

Geometry model (one authority, rule GEO-00): the store. Places form a graph; portals are the edges.
A portal of kind 'wall' or 'fence' has aperture 0: never traversable (the climb effect moves a body
over a climbable fence/window, 07 §4), always an acoustic link, and a visual link only when
transparent = 1 (a chain-link fence; a wall is never transparent). Every other portal kind is
traversable when ``admits`` is true.
Coordinates: x_m/y_m are metres inside the place (origin = a corner). Distances between two points
in different places are computed along the shortest portal path (anchor-to-portal-anchor legs);
when a portal has no anchor on a side, its point on that side is the place centre.

Portal facts are orthogonal (GEO-01): a door may be simultaneously closed, locked, barricaded,
damaged and watched. There is no single 'state' field.

Body clearance (GEO-02, used by ``admits``):
  shoulder_cm = clamp(30 + mass_kg * 0.2, 30, 65)          (lurker: * 0.5 — LUR_FLEX_SLITHER)
  upright passage: aperture_w >= shoulder_cm and aperture_h >= 0.9 * height_cm
  crawl passage:   aperture_w >= shoulder_cm and aperture_h >= 45   (costs 4x time, posture prone)
  a portal admits nobody when kind in ('wall','fence') or not is_open (closed portals must be
  opened first; locked/barricaded ones cannot be opened without an affordance that defeats them).

Points: a body's point is positions (x_m, y_m). A portal's point on a side is its anchor on that
side (anchor_a for place_a, anchor_b for place_b), or that place's centre (width/2, depth/2) when
the anchor is NULL. Place ids, anchors and portals come from the store only.

Traversal: a portal is TRAVERSABLE for a body when admits() is True — or, with
allow_closed=True, when admits() says 'closed' but the portal is unlocked, unbarricaded and the
body would fit through its aperture once opened. ``path`` searches over places
with Dijkstra: the cost of entering a portal from a point is the euclidean distance from that
point to the portal's point on the current side; crossing costs 0 and the walker continues from
the portal's point on the far side. The final leg is the distance to the destination anchor (0
when to_anchor is None). A result is a list of PathLeg: one per portal crossed —
PathLeg(portal_id, place_id = the place entered, distance_m = metres walked before crossing) —
then PathLeg(None, to_place, final-leg metres). Same place: [PathLeg(None, place, d)].
A route enters each place at most once and never goes back into the place it starts in (P10: a
hub's roads all meet at its centre, so stepping into one road and straight back out costs nothing
— without this rule a tie would send the walker down the wrong road and back first).
Equal totals: the route whose portal-id sequence sorts first wins (deterministic).
``point_distance`` uses the same Dijkstra over EVERY portal (walls, fences, closed doors included:
it measures how far apart two bodies are, not whether one can walk to the other).
``places_near(place, max_hops)`` = place ids reachable over any portal within max_hops (the start
place excluded), sorted by (hops, place_id).

Events built here (callers commit them; writer 'physical.space'):
  MOVE {body_id, from_place, to_place, from_anchor, to_anchor, x_m, y_m, hidden} — updates
    positions (place_id, anchor_id, x_m, y_m, since_ms = at, hidden = the ``hidden`` argument,
    default False: moving gives a hider away unless the move itself is the hiding — the hide and
    sneak effects pass hidden=True, P5). When to_anchor is given, x_m/y_m must be that anchor's
    point (the caller passes them; ValueError when the anchor is not in to_place). A MOVE may
    keep the body where it is (from == to): that is how a body hides where it stands.
  PORTAL_CHANGE {portal_id, changes, before} — ``changes`` keys limited to is_open, is_locked,
    barricade, damage and (P10, world.infected INF-13) strain_min (ValueError otherwise;
    ValueError when the result would be open AND barricaded — W08 — so a barricade comes down
    before the door opens; wall/fence portals can change only damage and strain_min). ``before``
    holds the previous values of the changed keys.

Discovery (PLMP carried, rule GEO-03; built in P10 with worldgen — scenario fixtures already
contain their rooms, so nothing before P10 needs it): a building's rooms are generated from its
archetype the first time a body arrives at it (world.worldmove.on_arrival calls
``discover_layout``), with rng stream f"layout:{place_id}", and are permanent after that. Nothing
else creates rooms. A worldgen building site is the building's grounds (kind 'building', indoor 0);
its rooms are children of it and its exterior portals join the grounds to the rooms.
discover_layout(tx, rng, building_place_id, at, turn_index) -> list[Event]   (P10)
  Not a building, no archetype_ref, or layout_generated = 1 -> [] (idempotent). Otherwise, with
  a = the canon BuildingArchetype and held = places.held:
  1 One PLACE_DISCOVERED {place_id, rooms: n, source: 'discovery'} (writer 'physical.space', at,
    turn_index) inserting, per RoomTemplate in order, a place {kind 'room', parent_id = the building,
    zone_id = the building's, name = the room's name, width_m, depth_m, indoor, material, light_level
    1, ambient_db 25, layout_generated 1, held = the building's, props '{}'} with its anchors (name,
    kind, x_m, y_m, cover, concealment, capacity 4); the room-to-room portals of each template's
    ``portals`` (to_room within the building; is_open = starts_open, is_locked 0, lock_quality, the
    aperture / seal / open_loss / transparent / height fields as given); the EXTERIOR portals
    (a.exterior_portals: building grounds <-> to_room, anchor_a = the grounds' first anchor by
    anchor_id, anchor_b NULL; room-to-room portals have no anchors), where
    held = 1 -> is_open = starts_open, is_locked = 1 when lockable, damage 0; held = 0 -> damage =
    rng.range_int(tx, f"layout:{place_id}", f"damage:{i}", 0, 2), is_open = rng.chance(...,
    f"open:{i}", 0.3), is_locked 0 (i = the exterior portal's index); and updating the building's
    layout_generated to 1.
  2 Per room with an anchor whose template names a container_item (anchor order): that container is
    created lying at the anchor (physical.objects.create, origin 'loot').
  3 Loot (GEO-04 / WG-32): per room with a loot_table, in room order, stream f"loot:{place_id}:{room
    id}": n = range_int(purpose 'rolls', lo, hi) of the table's rolls (held = 0: (0, max(0, hi -
    2)), the place was picked over); per roll k (from 0): entry = weighted by weight (purpose
    f"entry:{k}"), qty = range_int(f"qty:{k}", *entry.qty), condition = range_int(f"condition:{k}",
    *entry.condition) — so the stream draws exactly 1 + 3 x n times; the item is created (origin
    'loot', ITEM_CREATED, that condition) inside the room's first container (anchor order) with room
    for it (the bulk already inside + this item's bulk x qty <= capacity_bulk), else lying at the
    room's first anchor; a def that is not stackable with qty > 1 becomes qty separate items of 1,
    each placed the same way.
  Returns every event committed, in seq order. The Fall-damage TRACE of an unheld building ("Old
  damage: this place was picked over long ago.", kind 'damage', in the entrance room) is created by
  the caller, world.worldmove.on_arrival (physical does not write world tables).

P10 — putting bodies and changing places outside a turn:
place_body(tx, body_id, place_id, anchor_id, x_m, y_m, at, cause_event_id, turn_index, *,
           replaces=None) -> Event
  MOVE {body_id, from_place: NULL, to_place: place_id, from_anchor NULL, to_anchor: anchor_id, x_m,
  y_m, hidden: false} (writer 'physical.space', actor_id = body_id) INSERTING the positions row
  (facing 0, since_ms = at, hidden 0); a body that already has one -> ValueError (use move_event).
  ``replaces`` = a body whose positions row the same event DELETES (a corpse that got up:
  world.infected.rise) — the payload then has replaces: that id.
remove_body(tx, body_id, at, cause_event_id, turn_index) -> Event   (P10, world.hordes HRD-18)
  DEMATERIALIZE {body_id, place_id, x_m, y_m} (writer 'physical.space', actor_id = body_id)
  DELETING the body's positions row: it leaves the world's detail and goes back into a count. A
  body with no positions row -> ValueError. Nothing perceives it (propagation has no rule for it;
  HRD-18 folds a body only where no living person is).
change_place(tx, place_id, changes, reason, at, cause_event_id, turn_index) -> Event
  PLACE_CHANGE {place_id, changes, before, reason} (writer 'physical.space') updating places;
  ``changes`` keys limited to held, light_level, ambient_db and props (props merged key by key into
  the JSON object); anything else -> ValueError.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..contracts.events import Event

if TYPE_CHECKING:
    from ..kernel.store import Store, Tx


@dataclass(frozen=True)
class PathLeg:
    portal_id: str | None  # None for the final leg inside the destination place
    place_id: str
    distance_m: float


def distance_m(ax: float, ay: float, bx: float, by: float) -> float:
    """Euclidean distance (implemented)."""
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


def shoulder_cm(mass_kg: int, kind: str = "human") -> float:
    w = max(30.0, min(65.0, 30 + mass_kg * 0.2))
    return w * 0.5 if kind == "lurker" else w



import heapq as _heapq


def _row(s, sql, params=()):
    r = s.query_one(sql, params)
    return dict(r) if r is not None else None


def _place_centre(s, place_id):
    r = _row(s, "SELECT width_m, depth_m FROM places WHERE place_id=?", (place_id,))
    return (r["width_m"] / 2, r["depth_m"] / 2)


def portal_point(store: "Store | Tx", portal_id: str, place_id: str) -> tuple[float, float]:
    """The portal's point on the side of ``place_id`` (its anchor there, else the place centre).
    ValueError when the portal does not touch that place."""
    p = _row(store, "SELECT * FROM portals WHERE portal_id=?", (portal_id,))
    if p["place_a"] == place_id:
        anc = p["anchor_a"]
    elif p["place_b"] == place_id:
        anc = p["anchor_b"]
    else:
        raise ValueError(f"portal {portal_id} does not touch {place_id}")
    if anc:
        a = _row(store, "SELECT x_m, y_m FROM anchors WHERE anchor_id=?", (anc,))
        return (a["x_m"], a["y_m"])
    return _place_centre(store, place_id)


def _fits(store, p, body_id):
    b = _row(store, "SELECT mass_kg, height_cm, kind FROM bodies WHERE body_id=?", (body_id,))
    sh = shoulder_cm(b["mass_kg"], "lurker" if b["kind"] == "lurker" else "human")
    w, h = p["aperture_w_cm"], p["aperture_h_cm"]
    if w < sh:
        return False, "too_narrow"
    if h >= 0.9 * b["height_cm"]:
        return True, "upright"
    if h >= 45:
        return True, "crawl"
    return False, "too_low"


def admits(store: "Store | Tx", portal_id: str, body_id: str) -> tuple[bool, str]:
    """(True, 'upright'|'crawl') or (False, reason) where reason in
    {'wall','closed','too_narrow','too_low'}."""
    p = _row(store, "SELECT * FROM portals WHERE portal_id=?", (portal_id,))
    if p["kind"] in ("wall", "fence"):
        return False, "wall"
    if not p["is_open"]:
        return False, "closed"
    return _fits(store, p, body_id)


def _traversable(store, p, body_id, allow_closed, allow_locked=False):
    if p["kind"] in ("wall", "fence"):
        return False
    ok, why = admits(store, p["portal_id"], body_id)
    if ok:
        return True
    if allow_closed and why == "closed" and not p["is_locked"] and p["barricade"] == 0:
        return _fits(store, p, body_id)[0]
    if allow_locked and not p["is_open"]:
        return _fits(store, p, body_id)[0]
    return False


def _dijkstra(store, start_place, start_pt, goal_place, goal_pt, ok_portal):
    portals = [dict(r) for r in store.query("SELECT * FROM portals ORDER BY portal_id")]
    # entries: (cost, done_flag, seq, n, place, point, legs); done entries (flag 0) win ties
    n = 0
    heap = [(0.0, 1, (), n, start_place, start_pt, ())]
    settled = set()
    while heap:
        cost, flag, seq, _, place, pt, legs = _heapq.heappop(heap)
        if flag == 0:
            return cost, [PathLeg(pid, pl, d) for pid, pl, d in legs]
        key = (place, pt)
        if key in settled:
            continue
        settled.add(key)
        if place == goal_place:
            final = distance_m(*pt, *goal_pt) if goal_pt is not None else 0.0
            n += 1
            _heapq.heappush(heap, (cost + final, 0, seq, n, place, pt, legs + ((None, goal_place, final),)))
        for p in portals:
            if place not in (p["place_a"], p["place_b"]) or p["place_a"] == p["place_b"]:
                continue
            if not ok_portal(p):
                continue
            other = p["place_b"] if p["place_a"] == place else p["place_a"]
            if other == start_place or any(pl == other for _, pl, _ in legs):
                continue  # a route enters each place at most once
            here = portal_point(store, p["portal_id"], place)
            there = portal_point(store, p["portal_id"], other)
            if (other, there) in settled:
                continue
            d = distance_m(*pt, *here)
            n += 1
            _heapq.heappush(heap, (cost + d, 1, seq + (p["portal_id"],), n, other, there, legs + ((p["portal_id"], other, d),)))
    return None


def _body_pt(store, body_id):
    r = _row(store, "SELECT place_id, x_m, y_m FROM positions WHERE body_id=?", (body_id,))
    return r["place_id"], (r["x_m"], r["y_m"])


def path(store: "Store | Tx", body_id: str, to_place: str, to_anchor: str | None = None,
         *, allow_closed: bool = False, allow_locked: bool = False) -> list[PathLeg] | None:
    """Shortest traversable route by distance (Dijkstra, ties broken by portal_id). With
    allow_closed=True closed-but-unlocked, unbarricaded portals count as traversable (the mover
    will have to open them). P10: with allow_locked=True every closed portal counts, locked or
    barricaded — never a wall or a fence — (world.infected INF-12: to something that bangs, a door
    is a door). The body must still fit through. Returns None when unreachable."""
    place, pt = _body_pt(store, body_id)
    goal = None
    if to_anchor is not None:
        a = _row(store, "SELECT x_m, y_m, place_id FROM anchors WHERE anchor_id=?", (to_anchor,))
        if a is None or a["place_id"] != to_place:
            raise ValueError("anchor not in place")
        goal = (a["x_m"], a["y_m"])
    r = _dijkstra(store, place, pt, to_place, goal, lambda p: _traversable(store, p, body_id, allow_closed, allow_locked))
    return None if r is None else r[1]


def point_distance(store: "Store | Tx", a_body: str, b_body: str) -> float | None:
    """Distance between two bodies: same place -> euclidean; else the shortest route over every
    portal (walls, fences and closed portals included; see module docstring). None when no link."""
    pa, pta = _body_pt(store, a_body)
    pb, ptb = _body_pt(store, b_body)
    if pa == pb:
        return distance_m(*pta, *ptb)
    r = _dijkstra(store, pa, pta, pb, ptb, lambda p: True)
    return None if r is None else r[0]


def line_of_sight(store: "Store | Tx", observer_id: str, subject_id: str) -> bool:
    """Same place -> True. Adjacent place through ONE portal that is open or transparent (a wall
    never; a fence only when transparent) -> True when observer or subject is within 3.0 m of that
    portal's point on their side. Otherwise False."""
    po, pto = _body_pt(store, observer_id)
    ps, pts = _body_pt(store, subject_id)
    if po == ps:
        return True
    for p in store.query("SELECT * FROM portals WHERE (place_a=? AND place_b=?) OR (place_a=? AND place_b=?) ORDER BY portal_id", (po, ps, ps, po)):
        p = dict(p)
        if p["kind"] == "wall":
            continue
        if not (p["is_open"] or p["transparent"]):
            continue
        a = portal_point(store, p["portal_id"], po)
        b = portal_point(store, p["portal_id"], ps)
        if distance_m(*pto, *a) <= 3.0 or distance_m(*pts, *b) <= 3.0:
            return True
    return False


def move_event(tx: "Tx", body_id: str, to_place: str, to_anchor: str | None, x_m: float, y_m: float,
               at: int, cause_event_id: str | None, turn_index: int, *, hidden: bool = False) -> Event:
    """Build (not commit) a MOVE event, writer 'physical.space', actor_id = body_id, updating
    positions. Also sets since_ms=at and hidden (see above). Caller commits."""
    from ..contracts.events import EventType, WriteOp, WriteRecord
    cur = _row(tx, "SELECT * FROM positions WHERE body_id=?", (body_id,))
    if to_anchor is not None:
        a = _row(tx, "SELECT place_id, x_m, y_m FROM anchors WHERE anchor_id=?", (to_anchor,))
        if a is None or a["place_id"] != to_place:
            raise ValueError(f"anchor {to_anchor} is not in {to_place}")
    vals = {"place_id": to_place, "anchor_id": to_anchor, "x_m": x_m, "y_m": y_m, "since_ms": at, "hidden": int(bool(hidden))}
    if cur is None:
        w = WriteRecord(op=WriteOp.INSERT, table="positions", values={"body_id": body_id, "facing_deg": 0, **vals})
    else:
        w = WriteRecord(op=WriteOp.UPDATE, table="positions", key={"body_id": body_id}, values=vals)
    return Event(type=EventType.MOVE, writer="physical.space", at=at, turn_index=turn_index, actor_id=body_id,
                 place_id=to_place, cause_event_id=cause_event_id, writes=[w],
                 payload={"body_id": body_id, "from_place": cur["place_id"] if cur else None, "to_place": to_place,
                          "from_anchor": cur["anchor_id"] if cur else None, "to_anchor": to_anchor, "x_m": x_m, "y_m": y_m,
                          "hidden": bool(hidden)})


def portal_change_event(tx: "Tx", portal_id: str, changes: dict, at: int, actor_id: str | None,
                        cause_event_id: str | None, turn_index: int) -> Event:
    """PORTAL_CHANGE event. ``changes`` keys limited to is_open, is_locked, barricade, damage and
    (P10) strain_min."""
    from ..contracts.events import EventType, WriteOp, WriteRecord
    allowed = {"is_open", "is_locked", "barricade", "damage", "strain_min"}
    if not changes or set(changes) - allowed:
        raise ValueError(f"portal changes limited to {sorted(allowed)}")
    p = _row(tx, "SELECT * FROM portals WHERE portal_id=?", (portal_id,))
    if p["kind"] in ("wall", "fence") and set(changes) - {"damage", "strain_min"}:
        raise ValueError("a wall or fence can only be damaged")
    after = {**p, **{k: int(v) for k, v in changes.items()}}
    if after["is_open"] and after["barricade"] > 0:
        raise ValueError("an open portal cannot be barricaded (W08)")
    vals = {k: int(v) for k, v in changes.items()}
    return Event(type=EventType.PORTAL_CHANGE, writer="physical.space", at=at, turn_index=turn_index, actor_id=actor_id,
                 cause_event_id=cause_event_id, target_ids=[portal_id],
                 writes=[WriteRecord(op=WriteOp.UPDATE, table="portals", key={"portal_id": portal_id}, values=vals)],
                 payload={"portal_id": portal_id, "changes": vals, "before": {k: p[k] for k in vals}})


def discover_layout(tx: "Tx", rng, building_place_id: str, at: int, turn_index: int) -> list[Event]:
    """GEO-03/04 (P10): the building's rooms, portals, containers and loot, the first time (see the
    module docstring)."""
    import json as _json
    from ..contracts.events import EventType, WriteOp, WriteRecord
    from . import objects
    b = _row(tx, "SELECT * FROM places WHERE place_id=?", (building_place_id,))
    if b is None or b["kind"] != "building" or not b["archetype_ref"] or b["layout_generated"]:
        return []
    a = tx.canon.get(b["archetype_ref"])
    held = b["held"]
    stream = f"layout:{building_place_id}"
    room_ids, anchors_of, ws = {}, {}, []
    for r in a.rooms:
        pid = tx.mint("plc")
        room_ids[r.id] = pid
        ws.append(WriteRecord(op=WriteOp.INSERT, table="places", values={
            "place_id": pid, "zone_id": b["zone_id"], "parent_id": building_place_id, "kind": "room", "name": r.name,
            "archetype_ref": None, "width_m": r.width_m, "depth_m": r.depth_m, "indoor": int(r.indoor),
            "material": r.material, "light_level": 1, "ambient_db": 25.0, "layout_generated": 1, "held": held,
            "props": {}}))
    for r in a.rooms:
        anchors_of[r.id] = []
        for an in r.anchors:
            aid = tx.mint("anc")
            anchors_of[r.id].append((aid, an))
            ws.append(WriteRecord(op=WriteOp.INSERT, table="anchors", values={
                "anchor_id": aid, "place_id": room_ids[r.id], "name": an.name, "kind": an.kind, "x_m": an.x_m,
                "y_m": an.y_m, "cover": an.cover, "concealment": an.concealment, "capacity": 4}))

    def portal_vals(pt, a_place, b_place, anchor_a, is_open, is_locked, damage):
        return {"portal_id": tx.mint("prt"), "place_a": a_place, "place_b": b_place, "anchor_a": anchor_a,
                "anchor_b": None, "kind": pt.kind, "name": pt.name, "is_open": int(is_open), "is_locked": int(is_locked),
                "lock_quality": pt.lock_quality, "barricade": 0, "damage": damage, "aperture_w_cm": pt.aperture_w_cm,
                "aperture_h_cm": pt.aperture_h_cm, "seal_db": pt.seal_db, "open_loss_db": pt.open_loss_db,
                "transparent": int(pt.transparent), "height_cm": pt.height_cm}
    for r in a.rooms:
        for pt in r.portals:
            ws.append(WriteRecord(op=WriteOp.INSERT, table="portals", values=portal_vals(
                pt, room_ids[r.id], room_ids[pt.to_room], None, pt.starts_open, False, 0)))
    front = _row(tx, "SELECT anchor_id FROM anchors WHERE place_id=? ORDER BY anchor_id LIMIT 1", (building_place_id,))
    for i, pt in enumerate(a.exterior_portals):
        if held:
            is_open, locked, dmg = pt.starts_open, pt.lockable, 0
        else:
            dmg = rng.range_int(tx, stream, f"damage:{i}", 0, 2)
            is_open, locked = rng.chance(tx, stream, f"open:{i}", 0.3), False
        ws.append(WriteRecord(op=WriteOp.INSERT, table="portals", values=portal_vals(
            pt, building_place_id, room_ids[pt.to_room], front["anchor_id"] if front else None, is_open, locked, dmg)))
    ws.append(WriteRecord(op=WriteOp.UPDATE, table="places", key={"place_id": building_place_id}, values={"layout_generated": 1}))
    ev = tx.commit_event(Event(type=EventType.PLACE_DISCOVERED, writer="physical.space", at=at, turn_index=turn_index,
                               place_id=building_place_id, writes=ws,
                               payload={"place_id": building_place_id, "rooms": len(a.rooms), "source": "discovery"}))
    out = [ev]
    containers = {}
    for r in a.rooms:
        for aid, an in anchors_of[r.id]:
            if an.container_item:
                e2 = objects.create(tx, an.container_item, 1, objects.Holder("place", room_ids[r.id], anchor_id=aid),
                                    "loot", {}, at, ev.event_id, turn_index)
                out.append(e2)
                containers.setdefault(r.id, []).append(e2.payload["item_id"])
    for r in a.rooms:
        if not r.loot_table:
            continue
        table = tx.canon.get(r.loot_table)
        ls = f"loot:{building_place_id}:{r.id}"
        lo, hi = table.rolls
        if not held:
            lo, hi = 0, max(0, hi - 2)
        n = rng.range_int(tx, ls, "rolls", lo, hi)
        for k in range(n):
            e = rng.weighted(tx, ls, f"entry:{k}", [(en, en.weight) for en in table.entries])
            qty = rng.range_int(tx, ls, f"qty:{k}", e.qty[0], e.qty[1])
            cond = rng.range_int(tx, ls, f"condition:{k}", e.condition[0], e.condition[1])
            idef = tx.canon.get(e.item)
            units = [qty] if (idef.stackable or qty == 1) else [1] * qty
            for q in units:
                holder = None
                for c in containers.get(r.id, []):
                    cdef = tx.canon.get(_row(tx, "SELECT def_ref FROM items WHERE item_id=?", (c,))["def_ref"])
                    used = sum(tx.canon.get(rr["def_ref"]).bulk * rr["qty"]
                               for rr in tx.query("SELECT def_ref, qty FROM items WHERE container_id=?", (c,)))
                    if cdef.container is not None and used + idef.bulk * q <= cdef.container.capacity_bulk:
                        holder = objects.Holder("container", c)
                        break
                if holder is None:
                    holder = objects.Holder("place", room_ids[r.id], anchor_id=anchors_of[r.id][0][0])
                out.append(objects.create(tx, e.item, q, holder, "loot", {}, at, ev.event_id, turn_index, condition=cond))
    return out


def place_body(tx: "Tx", body_id: str, place_id: str, anchor_id: str | None, x_m: float, y_m: float, at: int,
               cause_event_id: str | None, turn_index: int, *, replaces: str | None = None) -> Event:
    from ..contracts.events import EventType, WriteOp, WriteRecord
    if _row(tx, "SELECT 1 FROM positions WHERE body_id=?", (body_id,)) is not None:
        raise ValueError(f"{body_id} already has a position")
    ws = [WriteRecord(op=WriteOp.INSERT, table="positions", values={
        "body_id": body_id, "place_id": place_id, "anchor_id": anchor_id, "x_m": x_m, "y_m": y_m, "facing_deg": 0,
        "since_ms": at, "hidden": 0})]
    payload = {"body_id": body_id, "from_place": None, "to_place": place_id, "from_anchor": None, "to_anchor": anchor_id,
               "x_m": x_m, "y_m": y_m, "hidden": False}
    if replaces is not None:
        ws.append(WriteRecord(op=WriteOp.DELETE, table="positions", key={"body_id": replaces}))
        payload["replaces"] = replaces
    return tx.commit_event(Event(type=EventType.MOVE, writer="physical.space", at=at, turn_index=turn_index,
                                 actor_id=body_id, place_id=place_id, cause_event_id=cause_event_id, writes=ws,
                                 payload=payload))


def remove_body(tx: "Tx", body_id: str, at: int, cause_event_id: str | None, turn_index: int) -> Event:
    from ..contracts.events import EventType, WriteOp, WriteRecord
    pos = _row(tx, "SELECT * FROM positions WHERE body_id=?", (body_id,))
    if pos is None:
        raise ValueError(f"{body_id} has no position")
    return tx.commit_event(Event(type=EventType.DEMATERIALIZE, writer="physical.space", at=at, turn_index=turn_index,
                                 actor_id=body_id, place_id=pos["place_id"], cause_event_id=cause_event_id,
                                 writes=[WriteRecord(op=WriteOp.DELETE, table="positions", key={"body_id": body_id})],
                                 payload={"body_id": body_id, "place_id": pos["place_id"], "x_m": pos["x_m"],
                                          "y_m": pos["y_m"]}))


def change_place(tx: "Tx", place_id: str, changes: dict, reason: str, at: int, cause_event_id: str | None,
                 turn_index: int) -> Event:
    import json as _json
    from ..contracts.events import EventType, WriteOp, WriteRecord
    allowed = {"held", "light_level", "ambient_db", "props", "name"}   # P12 D-103: 'name' (the console's reshape)
    if not changes or set(changes) - allowed:
        raise ValueError(f"place changes limited to {sorted(allowed)}")
    p = _row(tx, "SELECT * FROM places WHERE place_id=?", (place_id,))
    if p is None:
        raise ValueError(f"unknown place {place_id}")
    vals, before = {}, {}
    for k, v in changes.items():
        if k == "props":
            old = _json.loads(p["props"]) if isinstance(p["props"], str) else dict(p["props"])
            before["props"] = dict(old)
            vals["props"] = {**old, **v}
        else:
            before[k] = p[k]
            vals[k] = v
    return tx.commit_event(Event(type=EventType.PLACE_CHANGE, writer="physical.space", at=at, turn_index=turn_index,
                                 place_id=place_id, cause_event_id=cause_event_id,
                                 writes=[WriteRecord(op=WriteOp.UPDATE, table="places", key={"place_id": place_id}, values=vals)],
                                 payload={"place_id": place_id, "changes": changes, "before": before, "reason": reason}))


def places_near(store: "Store | Tx", place_id: str, max_hops: int = 2) -> list[str]:
    seen = {place_id: 0}
    frontier = [place_id]
    for hop in range(1, max_hops + 1):
        nxt = []
        for pl in frontier:
            for r in store.query("SELECT place_a, place_b FROM portals WHERE place_a=? OR place_b=?", (pl, pl)):
                o = r[1] if r[0] == pl else r[0]
                if o not in seen:
                    seen[o] = hop
                    nxt.append(o)
        frontier = nxt
    return [p for p, h in sorted(seen.items(), key=lambda kv: (kv[1], kv[0])) if p != place_id]


def distance_to_point(store: "Store | Tx", body_id: str, place_id: str, x_m: float, y_m: float) -> float | None:
    """P5 (cues, effects). point_distance from a body to a point (same Dijkstra over EVERY
    portal); straight line when the point is in the body's place."""
    pa, pta = _body_pt(store, body_id)
    if pa == place_id:
        return distance_m(*pta, x_m, y_m)
    r = _dijkstra(store, pa, pta, place_id, (x_m, y_m), lambda p: True)
    return None if r is None else r[0]
