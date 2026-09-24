"""Households (P9). Owner 'society.household' (households, household_members). Rules HH-01..07.
docs/as/06_WORLD.md §2.2. A parent's decisions can account for their child because the engine
knows who their child is. Every function that returns an Event has committed it (writer
'society.household', at and turn_index as given). R = RulesConfig().society.

members(store, household_id, living=True) -> list[str]
  Actor ids of the household's household_members rows, sorted; living=True keeps only members
  whose body is alive (physical.bodies.is_alive).
household_of(store, actor_id) -> str | None
  The lowest household_id among the actor's household_members rows; None without one.
HH-01 head_of(store, household_id) -> str | None
  The living member with role 'head' (lowest id if several); else the living member with role
  'partner' (lowest id); else the oldest living member with bodies.age_years >= 15 (ties by id);
  else None.
HH-02 dependents_of(store, actor_id) -> list[str]
  The living actor ids listed in the guardian_of of ANY of the actor's household_members rows,
  sorted, without duplicates.
HH-03 has_dependents(store, household_id) -> bool
  True when a living member has role 'child' or 'dependent', or a bodies.age_band of infant,
  child or preteen.
HH-04 households_of(store, settlement_id) -> list[str]
  Households whose settlement_id is the settlement, plus every household with at least one
  living member among the settlement's named people (society.population.census(...).named);
  sorted, without duplicates.
HH-07 worst_hit(store, settlement_id) -> str | None
  The household of households_of(settlement) that is hit hardest by a shortage: among those with
  at least one living member, the highest ratio dependents / max(1, providers), where dependents
  = the living members HH-03 counts (role child or dependent, or band infant/child/preteen) and
  providers = the other living members aged >= 15 whose physical.bodies.capacity is mobile. Ties:
  the smaller sum of households.shared_stores values, then the lower household_id. None when no
  household qualifies.
HH-05 apply_change(tx, household_id, change, actor_id, at, turn_index, cause_event_id,
                   grief_delta=0) -> Event
  change in {'member_died', 'member_joined', 'member_left', 'grief_eased'} (ValueError
  otherwise); an unknown household -> ValueError. Commits HOUSEHOLD_CHANGE {household_id,
  change, actor_id, grief_before, grief_after} (event actor_id = actor_id) writing:
    'member_joined'  household_members INSERT {role 'lodger', guardian_of [],
                     protection_priority 0}; the actor already a member -> ValueError;
    'member_left'    household_members DELETE for (household_id, actor_id);
    'member_died'    nothing on the member row (the dead stay on the roll; members() filters
                     them) — the core cascade CAS-007 sends grief_delta 1;
    'grief_eased'    nothing but grief (actor_id is None);
  and, when grief_delta != 0, households.grief_state = clamp(grief_before + grief_delta, 0, 3).
  grief_before / grief_after are the grief_state before and after this event.
HH-06 day(tx, household_id, at, turn_index, cause_event_id) -> Event | None
  Grief eases with time (society.settlement.day calls this for each household of the
  settlement). When grief_state > 0 and the newest HOUSEHOLD_CHANGE event whose
  payload.household_id is this household is at least R.grief_ease_days days before ``at``:
  apply_change(tx, household_id, 'grief_eased', None, at, turn_index, cause_event_id,
  grief_delta=-1). Otherwise None (nothing committed).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..contracts.events import Event
    from ..kernel.store import Store, Tx


def members(store: "Store | Tx", household_id: str, living: bool = True) -> list[str]:
    raise NotImplementedError("P9")


def household_of(store: "Store | Tx", actor_id: str) -> str | None:
    raise NotImplementedError("P9")


def head_of(store: "Store | Tx", household_id: str) -> str | None:
    raise NotImplementedError("P9")


def dependents_of(store: "Store | Tx", actor_id: str) -> list[str]:
    raise NotImplementedError("P9")


def has_dependents(store: "Store | Tx", household_id: str) -> bool:
    raise NotImplementedError("P9")


def households_of(store: "Store | Tx", settlement_id: str) -> list[str]:
    raise NotImplementedError("P9")


def apply_change(tx: "Tx", household_id: str, change: str, actor_id: str | None, at: int,
                 turn_index: int, cause_event_id: str | None, grief_delta: int = 0) -> "Event":
    raise NotImplementedError("P9")


def day(tx: "Tx", household_id: str, at: int, turn_index: int, cause_event_id: str | None) -> "Event | None":
    raise NotImplementedError("P9")


def worst_hit(store: "Store | Tx", settlement_id: str) -> str | None:
    raise NotImplementedError("P9")
from ._impl_society import hh_members as members, household_of, head_of, dependents_of, has_dependents, households_of, worst_hit, apply_change, household_day as day  # noqa
