"""Physical wear (P10; fidelity C02 — replaces the salvaged Memory Fade). Rules WEAR-01..04.
docs/as/06_WORLD.md §4. Things change because something happened to them: rain rusts a gun left in
the street, paper turns to pulp, food goes off. Nothing is deleted because the player was away or
because it seemed unimportant — there are no scores, tiers or overhauls — and what a scavenger
takes, a scavenger who exists took (world.worldmove OPS-03). A mind forgets (mind.retrieval); the
world does not: every change is an event, so the history stays whole. D = RulesConfig().decay; no
rng is drawn (wear is arithmetic). Every function that returns an Event has committed it (at and
turn_index as given).

WEAR-01 exposed(store, place_id) -> bool: places.indoor is 0 — a street, a road, an outdoor place, a
  building site's outside. An indoor place (a room, a building's inside) shelters what is in it.
  An unknown place -> ValueError.
WEAR-02 wet(store) -> bool: world_clock.weather is 'rain', 'storm' or 'snow'.
WEAR-03 day(tx, rng, at, turn_index, cause_event_id) -> list[Event]   (world.worldmove.day calls it
  once the day's weather is set; ``rng`` is not drawn)
  1 Weather, only when wet(tx): per item (by item_id) lying loose (items.place_id set) in an
    exposed place with condition > 0, by its def's kind: in D.rust_kinds -> loss D.rust_per_wet_day
    ('rust'); 'document' -> D.pulp_per_wet_day ('pulp'); in D.rot_kinds -> D.rot_per_wet_day
    ('rot'); any other kind -> nothing.
  2 Spoilage, every day: per food item anywhere — held, packed or loose — (by item_id) whose def
    has food.spoil_days, whose props.made_at is set and whose props.spoiled is not true: at -
    made_at >= spoil_days x DAY -> spoiled ('spoiled').
  Each change is ITEM_WEAR {item_id, cause: 'rust' | 'pulp' | 'rot' | 'spoiled', condition_before,
  condition} (writer 'physical.objects', cause = cause_event_id, place_id = the item's place when it
  lies loose, else NULL) updating items.condition = max(0, condition_before - loss) — spoiled: 0,
  and props gains spoiled: true. A document whose condition reaches 0 has fallen apart:
  physical.objects.destroy(tx, it, at, that ITEM_WEAR id, turn_index). The active area is no
  exception (a gun rusts whether or not anyone is looking). Returns every event committed, in seq
  order.
WEAR-04 made_at: physical.objects.create (P10 amendment) gives a food item whose def has
  food.spoil_days props.made_at = at, unless the props it was given already carry made_at (loot,
  production and cheats create through it; the tinned food of a worldgen larder has no spoil_days
  and never goes off).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..contracts.events import Event
    from ..kernel.rng import Rng
    from ..kernel.store import Store, Tx


def exposed(store: "Store | Tx", place_id: str) -> bool:
    raise NotImplementedError("P10")


def wet(store: "Store | Tx") -> bool:
    raise NotImplementedError("P10")


def day(tx: "Tx", rng: "Rng", at: int, turn_index: int, cause_event_id: str | None) -> list["Event"]:
    raise NotImplementedError("P10")
