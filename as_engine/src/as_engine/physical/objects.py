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
    default 100) sets items.condition (loot rolls it, physical.space.discover_layout). P10
    (world.decay WEAR-04): a food def with food.spoil_days gets props.made_at = at unless the
    given props carry made_at (the ITEM_CREATED payload's props include it).
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

P10 — mouth contact (lore §3.2: "everyone knows somebody who was killed by a shared bottle"; used
by action.effects drink):
  ITEM_CONTAMINATED {item_id, pathway, by, lasting}   (contaminate) updating items.props.contaminated
                                              = {pathway, by, at, lasting} (a newer mark replaces the
                                              older — but never a lasting one with a passing one)
contaminate(tx, item_id, pathway, body_id, at, cause_event_id, turn_index, *, lasting=False) -> Event
contaminated(store, item_id, at) -> dict | None: the item's props.contaminated while at - its at <=
  RulesConfig.infected.saliva_hours hours (saliva dries out; [SAND]), else None (no mark, too old,
  or no such item). (I1) A lasting mark never dries: the dead's blood and fluids in meat or in
  loose water (world.infected INF-18/19; action.effects butcher) stay in it for good. A mark
  written before I1 (no 'lasting' key) is a passing one.

F1a — clothing.
LOOK-02 A worn item is an items row with holder_slot 'worn'; clothing is an item whose ItemDef has a
  ``clothing`` block (contracts.content.ClothingProps); its props may carry colour (overrides the
  block's colour), state ('clean' | 'worn' | 'soiled' | 'torn'; 'worn' when absent) and insignia (a
  mark anyone can see). A person placed in the world is dressed in their looks' outfit (dress).
CLOTHING_SLOT_ORDER = ('head', 'face', 'neck', 'torso', 'body', 'legs', 'hands', 'feet');
  CLOTHING_LAYER_ORDER = ('outer', 'mid', 'under').
worn(store, body_id) -> list[dict]: the body's worn items as {item_id, def_ref, name (ItemDef.name),
  clothing (the ClothingProps' model_dump(mode='json'), or None), colour, state, insignia} —
  clothing first, by (CLOTHING_SLOT_ORDER index, CLOTHING_LAYER_ORDER index, item_id); then the
  worn items without a clothing block (a holster, a pack), by item_id. colour = props.colour,
  else the block's colour, else ''; state = props.state, else 'worn'; insignia = props.insignia,
  else None.
coverage(store, body_id) -> set[str]: the union of ``covers`` of the worn clothing (a torn piece
  still covers).
warmth(store, body_id) -> int   (F1c, physical.bodies LOOK-09) the sum of ClothingProps.warmth over
  the body's worn clothing (0 with nothing on).
visible_gear(store, body_id) -> list[str]: the item ids anyone looking at the body can see, in
  this order — the items in hand_l, then hand_r; then the worn items without a clothing block,
  by item_id, except that one whose ItemDef.bulk <= 2 (a holstered handgun, a knife on a belt)
  is hidden while the body wears clothing with conceals true at layer 'outer' covering 'torso'
  (a long parka). Pockets and what is inside a container are never seen.
dress(tx, body_id, outfit, at, cause_event_id, turn_index, origin) -> list[str]
  For each OutfitPiece in order: create(tx, piece.item, 1, Holder('body', body_id, 'worn'), origin,
  props = {colour, state, insignia} with the None ones left out, at, cause_event_id, turn_index,
  event_origin = 'worldgen' when origin is 'worldgen', 'system' when it is 'scenario', else 'sim').
  Returns the new items' ids (each ITEM_CREATED's item), in order. (The scenario loader dresses a
  body given ``dress: true``; world.worldgen.opening dresses the PC.)
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



import json as _json

SLOT_ORDER = ("hand_l", "hand_r", "worn", "pocket", "pack")
ORIGINS = ("worldgen", "scenario", "production", "loot", "cheat", "craft")


def _item(s, item_id):
    r = s.query_one("SELECT * FROM items WHERE item_id=?", (item_id,))
    if r is None:
        raise KeyError(item_id)
    d = dict(r)
    d["props"] = _json.loads(d["props"])
    return d


def _def(s, def_ref):
    return s.canon.get(def_ref) if hasattr(s, "canon") and s.canon is not None else s.store.canon.get(def_ref)


def _canon(s):
    return s.canon if getattr(s, "canon", None) is not None else s.store.canon


def location_of(store: "Store | Tx", item_id: str) -> Holder:
    it = _item(store, item_id)
    if it["holder_body"]:
        return Holder("body", it["holder_body"], it["holder_slot"])
    if it["container_id"]:
        return Holder("container", it["container_id"])
    return Holder("place", it["place_id"], anchor_id=it["anchor_id"])


def _hd(h):
    return {"kind": h.kind, "id": h.id, "slot": h.slot, "anchor_id": h.anchor_id}


def _cols(h):
    if h.kind == "body":
        if h.slot not in SLOT_ORDER:
            raise ValueError("a body holder needs a slot")
        return {"holder_body": h.id, "holder_slot": h.slot, "container_id": None, "place_id": None, "anchor_id": None}
    if h.kind == "container":
        return {"holder_body": None, "holder_slot": None, "container_id": h.id, "place_id": None, "anchor_id": None}
    return {"holder_body": None, "holder_slot": None, "container_id": None, "place_id": h.id, "anchor_id": h.anchor_id}


def _contents(s, cid):
    return [dict(r) for r in s.query("SELECT * FROM items WHERE container_id=? ORDER BY item_id", (cid,))]


def _descendants(s, iid):
    out = []
    for c in _contents(s, iid):
        out.append(c["item_id"])
        out += _descendants(s, c["item_id"])
    return out


def _check_destination(tx, def_ref, qty, to, moving_id=None):
    canon = _canon(tx)
    d = canon.get(def_ref)
    if to.kind == "body" and to.slot in ("hand_l", "hand_r"):
        if tx.query_one("SELECT 1 FROM items WHERE holder_body=? AND holder_slot=?", (to.id, to.slot)):
            raise ValueError(f"{to.slot} already holds something (one item per hand)")
        if qty is not None and moving_id is None and False:
            pass
    if to.kind == "container":
        if moving_id is not None and (to.id == moving_id or to.id in _descendants(tx, moving_id)):
            raise ValueError("an item cannot go inside itself")
        host = _item(tx, to.id)
        hd = canon.get(host["def_ref"])
        if hd.container is not None:
            used = sum(canon.get(c["def_ref"]).bulk * c["qty"] for c in _contents(tx, to.id) if c["item_id"] != moving_id)
            if used + d.bulk * qty > hd.container.capacity_bulk:
                raise ValueError(f"{hd.name} is full (bulk {used} + {d.bulk * qty} > {hd.container.capacity_bulk})")
        elif hd.firearm is not None:
            if d.kind != "magazine" or hd.firearm.caliber not in d.tags or qty != 1:
                raise ValueError(f"only one {hd.firearm.caliber} magazine fits {hd.name}")
            if [c for c in _contents(tx, to.id) if c["item_id"] != moving_id]:
                raise ValueError(f"{hd.name} already has a magazine")
        else:
            raise ValueError(f"{hd.name} is not a container")


def create(tx: "Tx", def_ref: str, qty: int, to: Holder, origin: str, props: dict, at: int,
           cause_event_id: str | None, turn_index: int, *, event_origin: str = "sim", condition: int = 100) -> Event:
    """ITEM_CREATED. ``origin`` is the ITEM's origin column (worldgen, scenario, production, loot,
    cheat, craft); ``event_origin`` is the Event.origin (the scenario loader passes 'system',
    worldgen 'worldgen', cheats 'cheat')."""
    from ..contracts.events import EventType, WriteOp, WriteRecord
    if origin not in ORIGINS:
        raise ValueError(f"item origin {origin!r} not allowed")
    d = _canon(tx).get(def_ref)
    if qty > 1 and not d.stackable:
        raise ValueError(f"{def_ref} is not stackable")
    _check_destination(tx, def_ref, qty, to)
    props = dict(props or {})
    if d.food is not None and d.food.spoil_days is not None and "made_at" not in props:
        props["made_at"] = at   # WEAR-04 (P10)
    iid = tx.mint("itm")
    vals = {"item_id": iid, "def_ref": def_ref, "qty": qty, "condition": condition, "lot_id": None,
            "props": props, "origin": origin, **_cols(to)}
    return tx.commit_event(Event(type=EventType.ITEM_CREATED, writer="physical.objects", at=at, turn_index=turn_index,
                                 cause_event_id=cause_event_id, origin=event_origin, target_ids=[iid],
                                 writes=[WriteRecord(op=WriteOp.INSERT, table="items", values=vals)],
                                 payload={"item_id": iid, "def_ref": def_ref, "qty": qty, "origin": origin, "props": props or {}, "to": _hd(to)}))


def _create_with_id(tx, iid, def_ref, qty, to, origin, props, at, cause_event_id, turn_index, event_origin="sim", condition=100):
    """Loader helper: create with a pre-minted id (ids are minted up front by the scenario loader)."""
    from ..contracts.events import EventType, WriteOp, WriteRecord
    if origin not in ORIGINS:
        raise ValueError(f"item origin {origin!r} not allowed")
    d = _canon(tx).get(def_ref)
    if qty > 1 and not d.stackable:
        raise ValueError(f"{def_ref} is not stackable")
    _check_destination(tx, def_ref, qty, to)
    vals = {"item_id": iid, "def_ref": def_ref, "qty": qty, "condition": condition, "lot_id": None,
            "props": props or {}, "origin": origin, **_cols(to)}
    return tx.commit_event(Event(type=EventType.ITEM_CREATED, writer="physical.objects", at=at, turn_index=turn_index,
                                 cause_event_id=cause_event_id, origin=event_origin, target_ids=[iid],
                                 writes=[WriteRecord(op=WriteOp.INSERT, table="items", values=vals)],
                                 payload={"item_id": iid, "def_ref": def_ref, "qty": qty, "origin": origin, "props": props or {}, "to": _hd(to)}))


def transfer(tx: "Tx", item_id: str, to: Holder, qty: int | None, at: int, actor_id: str | None,
             cause_event_id: str | None, turn_index: int, *, props_update: dict | None = None) -> Event:
    """ITEM_TRANSFER (split when qty < item qty). Holding a third item in hands raises ValueError
    (two hands); a container over bulk capacity raises ValueError (rule OBJ-02).
    ``props_update`` (P5: equip / holster) merges keys into the moved item's props in the same
    write (a key with value None is removed); the payload then also carries props_after."""
    from ..contracts.events import EventType, WriteOp, WriteRecord
    it = _item(tx, item_id)
    q = it["qty"] if qty is None else qty
    if q < 1 or q > it["qty"]:
        raise ValueError("bad qty")
    frm = location_of(tx, item_id)
    _check_destination(tx, it["def_ref"], q, to, moving_id=item_id)
    writes = []
    new_id = None
    props = it["props"] if isinstance(it["props"], dict) else _json.loads(it["props"])
    if props_update:
        props = dict(props)
        for k, v in props_update.items():
            if v is None:
                props.pop(k, None)
            else:
                props[k] = v
    if q < it["qty"]:
        new_id = tx.mint("itm")
        writes.append(WriteRecord(op=WriteOp.UPDATE, table="items", key={"item_id": item_id}, values={"qty": it["qty"] - q}))
        writes.append(WriteRecord(op=WriteOp.INSERT, table="items", values={
            "item_id": new_id, "def_ref": it["def_ref"], "qty": q, "condition": it["condition"], "lot_id": it["lot_id"],
            "props": props, "origin": it["origin"], **_cols(to)}))
    else:
        vals = dict(_cols(to))
        if props_update:
            vals["props"] = props
        writes.append(WriteRecord(op=WriteOp.UPDATE, table="items", key={"item_id": item_id}, values=vals))
    payload = {"item_id": item_id, "qty": q, "from": _hd(frm), "to": _hd(to), "new_item_id": new_id}
    if props_update:
        payload["props_after"] = props
    return tx.commit_event(Event(type=EventType.ITEM_TRANSFER, writer="physical.objects", at=at, turn_index=turn_index,
                                 actor_id=actor_id, cause_event_id=cause_event_id, target_ids=[item_id], writes=writes,
                                 payload=payload))


def destroy(tx: "Tx", item_id: str, at: int, cause_event_id: str, turn_index: int,
            qty: int | None = None) -> Event:
    from ..contracts.events import EventType, WriteOp, WriteRecord
    if not cause_event_id:
        raise ValueError("destruction needs a cause")
    it = _item(tx, item_id)
    if _contents(tx, item_id):
        raise ValueError("empty the container first")
    q = it["qty"] if qty is None else qty
    if q < 1 or q > it["qty"]:
        raise ValueError("bad qty")
    if q == it["qty"]:
        w = WriteRecord(op=WriteOp.DELETE, table="items", key={"item_id": item_id})
    else:
        w = WriteRecord(op=WriteOp.UPDATE, table="items", key={"item_id": item_id}, values={"qty": it["qty"] - q})
    return tx.commit_event(Event(type=EventType.ITEM_DESTROYED, writer="physical.objects", at=at, turn_index=turn_index,
                                 cause_event_id=cause_event_id, target_ids=[item_id], writes=[w],
                                 payload={"item_id": item_id, "def_ref": it["def_ref"], "qty": q, "cause_event_id": cause_event_id}))


def fire(tx: "Tx", firearm_id: str, at: int, actor_id: str, cause_event_id: str | None,
         turn_index: int) -> tuple[bool, Event]:
    """Returns (shot_fired, event). See module docstring (OBJ-05)."""
    from ..contracts.events import EventType, WriteOp, WriteRecord
    gun = _item(tx, firearm_id)
    fd = _canon(tx).get(gun["def_ref"]).firearm
    if fd is None:
        raise ValueError("not a firearm")
    writes = []
    if fd.feeds_from in ("cylinder", "internal"):
        n = int(gun["props"].get("rounds", 0))
        fired = n > 0
        left = n - 1 if fired else 0
        if fired:
            writes.append(WriteRecord(op=WriteOp.UPDATE, table="items", key={"item_id": firearm_id}, values={"props": {**gun["props"], "rounds": left}}))
    else:
        mags = _contents(tx, firearm_id)
        mag = None
        if mags:
            mag = dict(mags[0]); mag["props"] = _json.loads(mag["props"])
        chambered = bool(gun["props"].get("chambered", False))
        fired = chambered
        mag_rounds = int(mag["props"].get("rounds", 0)) if mag else 0
        if fired:
            if mag_rounds > 0:
                mag_rounds -= 1
                writes.append(WriteRecord(op=WriteOp.UPDATE, table="items", key={"item_id": mag["item_id"]}, values={"props": {**mag["props"], "rounds": mag_rounds}}))
                new_ch = True
            else:
                new_ch = False
                writes.append(WriteRecord(op=WriteOp.UPDATE, table="items", key={"item_id": firearm_id}, values={"props": {**gun["props"], "chambered": False}}))
            left = mag_rounds + (1 if new_ch else 0)
        else:
            left = mag_rounds
    ev = tx.commit_event(Event(type=EventType.ITEM_CONDITION, writer="physical.objects", at=at, turn_index=turn_index,
                               actor_id=actor_id, cause_event_id=cause_event_id, target_ids=[firearm_id], writes=writes,
                               payload={"firearm_id": firearm_id, "result": "fired" if fired else "click", "rounds_left": left}))
    return fired, ev


def access_time_s(store: "Store | Tx", item_id: str) -> float:
    it = _item(store, item_id)
    if it["holder_body"]:
        return {"hand_l": 0.0, "hand_r": 0.0, "worn": 1.0, "pocket": 2.0, "pack": 4.0}[it["holder_slot"]]
    if it["place_id"]:
        return 1.0
    host = _item(store, it["container_id"])
    hd = _canon(store).get(host["def_ref"])
    own = hd.container.access_time_s if hd.container is not None else 1.0
    return own + access_time_s(store, host["item_id"])


def _held_tree_ids(store, body_id):
    out = []
    for r in store.query("SELECT item_id FROM items WHERE holder_body=?", (body_id,)):
        out.append(r[0])
        out += _descendants(store, r[0])
    return out


def carried_mass_kg(store: "Store | Tx", body_id: str) -> float:
    canon = _canon(store)
    tot = 0
    for iid in _held_tree_ids(store, body_id):
        it = _item(store, iid)
        tot += canon.get(it["def_ref"]).mass_g * it["qty"]
    return tot / 1000


def load_word(store: "Store | Tx", body_id: str) -> str:
    m = store.query_one("SELECT mass_kg FROM bodies WHERE body_id=?", (body_id,))[0]
    r = carried_mass_kg(store, body_id) / m
    return "light" if r <= 0.20 else "moderate" if r <= 0.35 else "heavy" if r <= 0.50 else "overloaded"


def _node(store, it):
    d = _canon(store).get(it["def_ref"])
    props = it["props"] if isinstance(it["props"], dict) else _json.loads(it["props"])
    return {"item_id": it["item_id"], "def_ref": it["def_ref"], "name": d.plural if it["qty"] > 1 else d.name,
            "qty": it["qty"], "slot": it["holder_slot"], "props": props,
            "contents": [_node(store, dict(c)) for c in _contents(store, it["item_id"])]}


def inventory_tree(store: "Store | Tx", body_id: str) -> list[dict]:
    """Held/worn/pocket/pack items with nested container contents, ordered by slot then item_id."""
    items = [dict(r) for r in store.query("SELECT * FROM items WHERE holder_body=?", (body_id,))]
    items.sort(key=lambda i: (SLOT_ORDER.index(i["holder_slot"]), i["item_id"]))
    return [_node(store, i) for i in items]


def total_qty(store: "Store | Tx", def_ref: str) -> int:
    return store.query_one("SELECT COALESCE(SUM(qty),0) FROM items WHERE def_ref=?", (def_ref,))[0]


def chamber(tx: "Tx", firearm_id: str, at: int, actor_id: str | None, cause_event_id: str | None,
            turn_index: int) -> Event | None:
    """P5 (reload). A magazine-fed firearm that is not chambered and whose magazine has rounds > 0:
    commit ITEM_CONDITION {firearm_id, result: 'chambered', rounds_left} moving one round from the
    magazine (rounds - 1) into the chamber (props.chambered true); rounds_left = magazine rounds + 1
    afterwards. Otherwise None (nothing to do)."""
    from ..contracts.events import EventType, WriteOp, WriteRecord
    gun = _item(tx, firearm_id)
    if gun["props"].get("chambered"):
        return None
    mags = _contents(tx, firearm_id)
    if not mags:
        return None
    m = dict(mags[0])
    mp = _json.loads(m["props"])
    n = int(mp.get("rounds", 0))
    if n <= 0:
        return None
    return tx.commit_event(Event(type=EventType.ITEM_CONDITION, writer="physical.objects", at=at, turn_index=turn_index, actor_id=actor_id,
                                 cause_event_id=cause_event_id,
                                 writes=[WriteRecord(op=WriteOp.UPDATE, table="items", key={"item_id": m["item_id"]}, values={"props": {**mp, "rounds": n - 1}}),
                                         WriteRecord(op=WriteOp.UPDATE, table="items", key={"item_id": firearm_id}, values={"props": {**gun["props"], "chambered": True}})],
                                 payload={"firearm_id": firearm_id, "result": "chambered", "rounds_left": n}))


def load_rounds(tx: "Tx", firearm_id: str, rounds: int, at: int, actor_id: str | None,
                cause_event_id: str | None, turn_index: int) -> Event:
    """P5 (reload of a cylinder / internal firearm). Set the firearm's props.rounds to ``rounds``
    (0..capacity, ValueError otherwise): ITEM_CONDITION {firearm_id, result: 'loaded',
    rounds_left: rounds}. The loose rounds are consumed by the caller with destroy(qty=...)."""
    from ..contracts.events import EventType, WriteOp, WriteRecord
    gun = _item(tx, firearm_id)
    cap = _canon(tx).get(gun["def_ref"]).firearm.capacity
    if not 0 <= rounds <= cap:
        raise ValueError("rounds out of range")
    return tx.commit_event(Event(type=EventType.ITEM_CONDITION, writer="physical.objects", at=at, turn_index=turn_index, actor_id=actor_id,
                                 cause_event_id=cause_event_id,
                                 writes=[WriteRecord(op=WriteOp.UPDATE, table="items", key={"item_id": firearm_id}, values={"props": {**gun["props"], "rounds": rounds}})],
                                 payload={"firearm_id": firearm_id, "result": "loaded", "rounds_left": rounds}))


def contaminate(tx: "Tx", item_id: str, pathway: str, body_id: str, at: int, cause_event_id: str | None,
                turn_index: int, *, lasting: bool = False) -> Event:
    """P10: a spreader's mouth on the item (ITEM_CONTAMINATED updating props.contaminated)."""
    from ..contracts.events import EventType, WriteOp, WriteRecord
    it = _item(tx, item_id)
    props = dict(it["props"])
    old = props.get("contaminated") or {}
    if not (old.get("lasting") and not lasting):
        props["contaminated"] = {"pathway": pathway, "by": body_id, "at": at, "lasting": bool(lasting)}
    return tx.commit_event(Event(type=EventType.ITEM_CONTAMINATED, writer="physical.objects", at=at, turn_index=turn_index,
                                 actor_id=body_id, cause_event_id=cause_event_id, target_ids=[item_id],
                                 writes=[WriteRecord(op=WriteOp.UPDATE, table="items", key={"item_id": item_id},
                                                     values={"props": props})],
                                 payload={"item_id": item_id, "pathway": pathway, "by": body_id, "lasting": bool(lasting)}))


def contaminated(store: "Store | Tx", item_id: str, at: int) -> dict | None:
    r = store.query_one("SELECT props FROM items WHERE item_id=?", (item_id,))
    if r is None:
        return None
    c = _json.loads(r[0] or "{}").get("contaminated")
    if not c:
        return None
    c = {**c, "lasting": bool(c.get("lasting", False))}
    if c["lasting"]:
        return c
    rules = store.rules if hasattr(store, "rules") else store.store.rules
    if at - c["at"] > rules.infected.saliva_hours * 3_600_000:
        return None
    return c


CLOTHING_SLOT_ORDER = ("head", "face", "neck", "torso", "body", "legs", "hands", "feet")
CLOTHING_LAYER_ORDER = ("outer", "mid", "under")


def worn(store: "Store | Tx", body_id: str) -> list[dict]:
    canon = _canon(store)
    rows = [dict(r) for r in store.query("SELECT item_id, def_ref, props FROM items WHERE holder_body=? AND holder_slot='worn'",
                                         (body_id,))]
    clothes, gear = [], []
    for r in rows:
        d = canon.get(r["def_ref"])
        props = _json.loads(r["props"]) if isinstance(r["props"], str) else (r["props"] or {})
        c = d.clothing
        out = {"item_id": r["item_id"], "def_ref": r["def_ref"], "name": d.name,
               "clothing": c.model_dump(mode="json") if c is not None else None,
               "colour": props.get("colour") or (c.colour if c is not None else "") or "",
               "state": props.get("state", "worn"), "insignia": props.get("insignia")}
        (clothes if c is not None else gear).append(out)
    clothes.sort(key=lambda o: (CLOTHING_SLOT_ORDER.index(o["clothing"]["slot"]),
                                CLOTHING_LAYER_ORDER.index(o["clothing"]["layer"]), o["item_id"]))
    gear.sort(key=lambda o: o["item_id"])
    return clothes + gear


def coverage(store: "Store | Tx", body_id: str) -> set[str]:
    return {c for o in worn(store, body_id) if o["clothing"] for c in o["clothing"]["covers"]}


def visible_gear(store: "Store | Tx", body_id: str) -> list[str]:
    canon = _canon(store)
    out = []
    for slot in ("hand_l", "hand_r"):
        out += [r[0] for r in store.query("SELECT item_id FROM items WHERE holder_body=? AND holder_slot=? ORDER BY item_id",
                                          (body_id, slot))]
    w = worn(store, body_id)
    hides = any(o["clothing"] and o["clothing"]["conceals"] and o["clothing"]["layer"] == "outer"
                and "torso" in o["clothing"]["covers"] for o in w)
    for o in w:
        if o["clothing"] is None:
            if hides and canon.get(o["def_ref"]).bulk <= 2:
                continue
            out.append(o["item_id"])
    return out


def dress(tx: "Tx", body_id: str, outfit: list, at: int, cause_event_id: str | None, turn_index: int,
          origin: str) -> list[str]:
    eo = "worldgen" if origin == "worldgen" else "system" if origin == "scenario" else "sim"
    ids = []
    for piece in outfit:
        props = {k: v for k, v in (("colour", piece.colour), ("state", piece.state), ("insignia", piece.insignia)) if v is not None}
        ev = create(tx, piece.item, 1, Holder("body", body_id, "worn"), origin, props, at, cause_event_id, turn_index,
                    event_origin=eo)
        ids.append(ev.payload["item_id"])
    return ids


def warmth(store: "Store | Tx", body_id: str) -> int:
    return sum((o["clothing"].get("warmth") or 0) for o in worn(store, body_id) if o["clothing"])
