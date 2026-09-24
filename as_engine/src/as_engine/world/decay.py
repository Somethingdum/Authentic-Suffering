"""Log decay / Memory Fade (P10). [SALVAGE: verbatim shape]. Rules DECAY-01..05. Owner 'world.decay'
(persistence_locks). docs/as/06_WORLD.md §4. The world forgets what nobody cares about — and every
forgetting is an event, so decay replays and is itself one of the strongest "it moved on" signals.
D = RulesConfig().decay; rng stream 'offscreen'. You = meta.pc_actor_id. Every function that returns an
Event has committed it (at and turn_index as given).

DECAY-01 Score. For a loose item (items.place_id set — lying somewhere, not held and not inside
  anything): SS = D.weights[0] x narrative + D.weights[1] x location + D.weights[2] x recency +
  D.weights[3] x object, each 0..100:
    narrative  80 when You hold a percept whose source_id is the item, else 20;
    location   100 in a settlement's place or inside one, 60 in a place You have visited, else 30;
    recency    from You's known_places.last_seen of the item's place (the place itself, or for a
               room its building): within 1 day 100, 7 days 60, 30 days 20, else (or never) 0;
    object     by the item def's kind: firearm, magazine, ammo, melee, medical, key 80; food, water,
               fuel, valuable, document 50; tool, light 40; anything else 10.
  score(store, item_id, at) -> float (rounded to 1 decimal).
DECAY-02 Tier 1, graceful forgetting: SS < D.tier1_below -> DECAY_TIER_1 {item_id, place_id, ss}
  (writer 'world.decay') then physical.objects.destroy(tx, item, at, that id, turn_index).
DECAY-03 Tier 2, environmental reclaim: D.tier1_below <= SS < D.tier2_below and the place is public
  or dangerous (a street, outdoor place or road; a room of a building that did not hold; or a zone
  whose danger 'shambler' >= 5), never a settlement's place or one inside it -> DECAY_TIER_2
  {item_id, place_id, ss}, destroy, and — once per
  place per day — a TRACE 'missing_stock' "Someone has been through here and taken things."
DECAY-04 Tier 3, location overhaul: at most ONE place a day — the non-settlement place with a
  generated layout (and every room under it), with no living body and no pending queue row whose
  subject is there, whose last visit by You (known_places.last_seen; never visited -> its discovery
  time, the PLACE_DISCOVERED event) is at least D.tier3_unvisited_days days ago; the oldest first,
  ties by place id. Everything loose in it and its rooms is destroyed (DECAY_TIER_3 {place_id,
  change: kind, items: n} first), its unlocked traces are removed (TRACE_DECAYED), and one new TRACE
  'damage' tells what happened: kind = rng.weighted(tx, 'offscreen', f"overhaul:{place}", (('collapse',
  1), ('fire', 1), ('occupation', 1))) with texts "The roof has come down since anyone last looked.",
  "Everything here is burnt black.", "Someone has moved in: bedding, a cold fire, a warning
  scratched on the door."
DECAY-05 Persistence locks: a subject id in persistence_locks never decays (items, places, traces).
  lock(tx, subject_id, reason, at, turn_index, cause_event_id) -> Event | None: already locked ->
  None; else MATERIALIZE {subject_id, reason} (writer 'world.decay') inserting persistence_locks, and
  for a trace world.traces.lock(...). Automatic locks, at the start of day(): the 'corpse' trace of
  every dead body You have an acquaintance row with (the stain where someone you knew died, reason
  'where they died').

day(tx, rng, at, turn_index, cause_event_id) -> list[Event]   (world.worldmove.day calls it)
  Automatic locks; then tiers 1 and 2 over the loose items (by item_id) that are not locked and not
  in a place inside the active area (turn.select.active_area); then tier 3. Returns every event.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..contracts.events import Event
    from ..kernel.rng import Rng
    from ..kernel.store import Store, Tx


def score(store: "Store | Tx", item_id: str, at: int) -> float:
    raise NotImplementedError("P10")


def lock(tx: "Tx", subject_id: str, reason: str, at: int, turn_index: int, cause_event_id: str | None) -> "Event | None":
    raise NotImplementedError("P10")


def day(tx: "Tx", rng: "Rng", at: int, turn_index: int, cause_event_id: str | None) -> list["Event"]:
    raise NotImplementedError("P10")
