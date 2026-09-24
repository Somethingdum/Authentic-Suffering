"""Items, containers, lots, conservation (P2). docs/as/07_RULES.md §Objects. Owner 'physical.objects'.
Item definitions come from canon: ``tx.canon.get(item.def_ref)`` (an ItemDef).

Location rule (CONSERVE-02, enforced by the items CHECK constraint): an item is held by exactly one
body (holder_body + holder_slot), inside exactly one container item (container_id), or lying in
exactly one place (place_id, optional anchor_id).
Conservation (CONSERVE-01, L11): a transfer never changes sum(qty) per def_ref; creation only via
ITEM_CREATED with origin in {worldgen, scenario, production, loot, cheat, craft}; destruction only
via ITEM_DESTROYED with a cause. Gate bit W04 checks sum(items.qty) per def_ref == sum of
ITEM_CREATED payload qty - sum of ITEM_DESTROYED payload qty, so both payloads carry def_ref + qty.

Events (writer 'physical.objects'; the functions commit them and return the committed Event):
  ITEM_CREATED   {item_id, def_ref, qty, origin, props, to}           (create)
  ITEM_TRANSFER  {item_id, qty, from, to, new_item_id}                (transfer; new_item_id only
                                                                       on a split, else null;
                                                                       + props_after when
                                                                       props_update was given)
  ITEM_DESTROYED {item_id, def_ref, qty, cause_event_id}              (destroy)
  ITEM_CONDITION {firearm_id, result: 'fired'|'click'|'chambered'|'loaded', rounds_left}
                                                                      (fire, chamber, load_rounds)
  ``from`` / ``to`` are Holder dicts: {kind, id, slot, anchor_id}.
Rules:
  * create: qty > 1 needs ItemDef.stackable (ValueError); origin outside the set -> ValueError;
    the destination obeys the same checks as a transfer. P10: the keyword ``condition`` (0..100,
    default 100) sets items.condition (loot rolls it, physical.space.discover_layout).
  * transfer (OBJ-02): a hand slot (hand_l / hand_r) holds at most ONE item -> ValueError when it
    is taken; a container item (its def has a ``container`` block) accepts contents while
    sum(bulk x qty of contents) + moved bulk x qty <= container.capacity_bulk, else ValueError;
    a firearm accepts exactly one item whose tags include the firearm's caliber tag and whose kind
    is 'magazine' (its magazine), anything else -> ValueError; an item may not be moved into
    itself or into something it contains (ValueError). qty None = the whole stack. Splitting a
    stack (qty < item qty) mints a new item id with the same def_ref, lot_id, condition and props;
    the new item goes to ``to`` and the original keeps the rest; ONE ITEM_TRANSFER carries both
    writes.
  * destroy: a container that still holds anything -> ValueError (empty it first). ``qty``
    None = the whole item (row deleted); qty < item qty = that many units consumed from the stack
    (row qty reduced, P5: eating one can of a stack of three); qty > item qty -> ValueError. The
    ITEM_DESTROYED payload qty is the number of units destroyed.
Access time (OBJ-03): an item in a hand 0 s; 'worn' 1 s; 'pocket' 2 s; 'pack' 4 s; lying in a
  place 1 s; inside a container = that container def's access_time_s + the container's own access
  time (nested containers add up); a magazine inside a firearm = 1 s + the firearm's access time.
Firearms (OBJ-05): a magazine-fed firearm item's props = {"chambered": bool}; its magazine is an
  item whose container_id = the firearm id and props {"rounds": n}. ``fire``: chambered -> a shot
  (result 'fired'); the next round is chambered from the magazine when it has rounds > 0
  (rounds - 1), else chambered becomes false. Not chambered -> result 'click', no writes.
  A firearm whose FirearmProps.feeds_from is 'cylinder' or 'internal' has no magazine item: its own
  props are {"rounds": n} (0..capacity) and a trigger pull consumes one when n > 0 ('fired'), else
  'click' (a revolver needs no chambering; a pump or bolt gun needs a manual cycle, which the
  shoot effect folds into its duration). rounds_left = rounds that can still fire without a reload
  (magazine rounds + 1 if chambered, or the internal count). Reloading those loads loose ammo items
  whose tags carry the caliber tag, one round per 2 s up to capacity (action.effects 'reload').
  A click is never a shot: the shoot effect turns it into ACTION_COMPLETE {"result": "click"} plus
  a 20 dB NOISE (canonical scenario INTENT-03).
Carried mass (OBJ-06): sum(mass_g x qty) / 1000 over everything held by the body in any slot,
  plus everything inside those items, recursively.
load_word: carried / body mass_kg <= 0.20 'light', <= 0.35 'moderate', <= 0.50 'heavy', else
  'overloaded'.
inventory_tree: one dict per item held by the body — {item_id, def_ref, name, qty, slot, props,
  contents: [same dicts, recursively, slot None]} — ordered by slot in the order hand_l, hand_r,
  worn, pocket, pack, then item_id; contents ordered by item_id. name = ItemDef.name (plural when
  qty > 1). props are the parsed JSON.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from ..contracts.events import Event

if TYPE_CHECKING:
    from ..kernel.store import Store, Tx


@dataclass(frozen=True)
class Holder:
    kind: Literal["body", "container", "place"]
    id: str
    slot: str | None = None  # for kind == 'body': hand_l|hand_r|worn|pocket|pack
    anchor_id: str | None = None  # for kind == 'place'


def location_of(store: "Store | Tx", item_id: str) -> Holder:
    raise NotImplementedError("P2")


def transfer(tx: "Tx", item_id: str, to: Holder, qty: int | None, at: int, actor_id: str | None,
             cause_event_id: str | None, turn_index: int, *, props_update: dict | None = None) -> Event:
    """ITEM_TRANSFER (split when qty < item qty). Holding a third item in hands raises ValueError
    (two hands); a container over bulk capacity raises ValueError (rule OBJ-02).
    ``props_update`` (P5: equip / holster) merges keys into the moved item's props in the same
    write (a key with value None is removed); the payload then also carries props_after."""
    raise NotImplementedError("P2")


def create(tx: "Tx", def_ref: str, qty: int, to: Holder, origin: str, props: dict, at: int,
           cause_event_id: str | None, turn_index: int, *, event_origin: str = "sim", condition: int = 100) -> Event:
    """ITEM_CREATED. ``origin`` is the ITEM's origin column (worldgen, scenario, production, loot,
    cheat, craft); ``event_origin`` is the Event.origin (the scenario loader passes 'system',
    worldgen 'worldgen', cheats 'cheat')."""
    raise NotImplementedError("P2")


def destroy(tx: "Tx", item_id: str, at: int, cause_event_id: str, turn_index: int,
            qty: int | None = None) -> Event:
    raise NotImplementedError("P2")


def fire(tx: "Tx", firearm_id: str, at: int, actor_id: str, cause_event_id: str | None,
         turn_index: int) -> tuple[bool, Event]:
    """Returns (shot_fired, event). See module docstring (OBJ-05)."""
    raise NotImplementedError("P2")


def chamber(tx: "Tx", firearm_id: str, at: int, actor_id: str | None, cause_event_id: str | None,
            turn_index: int) -> Event | None:
    """P5 (reload). A magazine-fed firearm that is not chambered and whose magazine has rounds > 0:
    commit ITEM_CONDITION {firearm_id, result: 'chambered', rounds_left} moving one round from the
    magazine (rounds - 1) into the chamber (props.chambered true); rounds_left = magazine rounds + 1
    afterwards. Otherwise None (nothing to do)."""
    raise NotImplementedError("P5")


def load_rounds(tx: "Tx", firearm_id: str, rounds: int, at: int, actor_id: str | None,
                cause_event_id: str | None, turn_index: int) -> Event:
    """P5 (reload of a cylinder / internal firearm). Set the firearm's props.rounds to ``rounds``
    (0..capacity, ValueError otherwise): ITEM_CONDITION {firearm_id, result: 'loaded',
    rounds_left: rounds}. The loose rounds are consumed by the caller with destroy(qty=...)."""
    raise NotImplementedError("P5")


def access_time_s(store: "Store | Tx", item_id: str) -> float:
    raise NotImplementedError("P2")


def carried_mass_kg(store: "Store | Tx", body_id: str) -> float:
    raise NotImplementedError("P2")


def load_word(store: "Store | Tx", body_id: str) -> str:
    raise NotImplementedError("P2")


def inventory_tree(store: "Store | Tx", body_id: str) -> list[dict]:
    """Held/worn/pocket/pack items with nested container contents, ordered by slot then item_id."""
    raise NotImplementedError("P2")


def total_qty(store: "Store | Tx", def_ref: str) -> int:
    raise NotImplementedError("P2")
