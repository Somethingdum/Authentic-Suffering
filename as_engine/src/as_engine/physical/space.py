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
    (a.exterior_portals: building grounds <-> to_room, anchor_a = the grounds' first anchor), where
    held = 1 -> is_open = starts_open, is_locked = 1 when lockable, damage 0; held = 0 -> damage =
    rng.range_int(tx, f"layout:{place_id}", f"damage:{i}", 0, 2), is_open = rng.chance(...,
    f"open:{i}", 0.3), is_locked 0 (i = the exterior portal's index); and updating the building's
    layout_generated to 1.
  2 Per room with an anchor whose template names a container_item (anchor order): that container is
    created lying at the anchor (physical.objects.create, origin 'loot').
  3 Loot (GEO-04 / WG-32): per room with a loot_table, in room order, stream f"loot:{place_id}:{room
    id}": n = range_int(lo, hi) of the table's rolls (held = 0: (0, max(0, hi - 2)), the place was
    picked over); per roll: entry = weighted by weight, qty = range_int(qty), condition =
    range_int(condition); the item is created (origin 'loot', ITEM_CREATED, that condition) inside the
    room's first container with room for it (capacity_bulk), else lying at the room's first anchor;
    a def that is not stackable with qty > 1 becomes qty separate items of 1, each placed the same way.
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


# P10 functions stand above the P2 ones so the kit's P10 patch merges over built code.
def place_body(tx: "Tx", body_id: str, place_id: str, anchor_id: str | None, x_m: float, y_m: float, at: int,
               cause_event_id: str | None, turn_index: int, *, replaces: str | None = None) -> Event:
    raise NotImplementedError("P10")


def change_place(tx: "Tx", place_id: str, changes: dict, reason: str, at: int, cause_event_id: str | None,
                 turn_index: int) -> Event:
    raise NotImplementedError("P10")


def distance_m(ax: float, ay: float, bx: float, by: float) -> float:
    """Euclidean distance (implemented)."""
    return ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5


def shoulder_cm(mass_kg: int, kind: str = "human") -> float:
    w = max(30.0, min(65.0, 30 + mass_kg * 0.2))
    return w * 0.5 if kind == "lurker" else w


def portal_point(store: "Store | Tx", portal_id: str, place_id: str) -> tuple[float, float]:
    """The portal's point on the side of ``place_id`` (its anchor there, else the place centre).
    ValueError when the portal does not touch that place."""
    raise NotImplementedError("P2")


def admits(store: "Store | Tx", portal_id: str, body_id: str) -> tuple[bool, str]:
    """(True, 'upright'|'crawl') or (False, reason) where reason in
    {'wall','closed','too_narrow','too_low'}."""
    raise NotImplementedError("P2")


def path(store: "Store | Tx", body_id: str, to_place: str, to_anchor: str | None = None,
         *, allow_closed: bool = False, allow_locked: bool = False) -> list[PathLeg] | None:
    """Shortest traversable route by distance (Dijkstra, ties broken by portal_id). With
    allow_closed=True closed-but-unlocked, unbarricaded portals count as traversable (the mover
    will have to open them). P10: with allow_locked=True every closed portal counts, locked or
    barricaded — never a wall or a fence — (world.infected INF-12: to something that bangs, a door
    is a door). The body must still fit through. Returns None when unreachable."""
    raise NotImplementedError("P2")


def point_distance(store: "Store | Tx", a_body: str, b_body: str) -> float | None:
    """Distance between two bodies: same place -> euclidean; else the shortest route over every
    portal (walls, fences and closed portals included; see module docstring). None when no link."""
    raise NotImplementedError("P2")


def distance_to_point(store: "Store | Tx", body_id: str, place_id: str, x_m: float, y_m: float) -> float | None:
    """P5 (cues, effects). point_distance from a body to a point (same Dijkstra over EVERY
    portal); straight line when the point is in the body's place."""
    raise NotImplementedError("P5")


def line_of_sight(store: "Store | Tx", observer_id: str, subject_id: str) -> bool:
    """Same place -> True. Adjacent place through ONE portal that is open or transparent (a wall
    never; a fence only when transparent) -> True when observer or subject is within 3.0 m of that
    portal's point on their side. Otherwise False."""
    raise NotImplementedError("P3")


def move_event(tx: "Tx", body_id: str, to_place: str, to_anchor: str | None, x_m: float, y_m: float,
               at: int, cause_event_id: str | None, turn_index: int, *, hidden: bool = False) -> Event:
    """Build (not commit) a MOVE event, writer 'physical.space', actor_id = body_id, updating
    positions. Also sets since_ms=at and hidden (see above). Caller commits."""
    raise NotImplementedError("P2")


def portal_change_event(tx: "Tx", portal_id: str, changes: dict, at: int, actor_id: str | None,
                        cause_event_id: str | None, turn_index: int) -> Event:
    """PORTAL_CHANGE event. ``changes`` keys limited to is_open, is_locked, barricade, damage and
    (P10) strain_min."""
    raise NotImplementedError("P2")


def discover_layout(tx: "Tx", rng, building_place_id: str, at: int, turn_index: int) -> list[Event]:
    """GEO-03/04 (P10): the building's rooms, portals, containers and loot, the first time (see the
    module docstring)."""
    raise NotImplementedError("P10")


def places_near(store: "Store | Tx", place_id: str, max_hops: int = 2) -> list[str]:
    raise NotImplementedError("P2")
