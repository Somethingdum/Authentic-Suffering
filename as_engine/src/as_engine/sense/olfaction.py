"""Smell (P3, the owner's F1b). Rules SMELL-01..03. docs/as/07_RULES.md §4.1. Pure reads: what a
body smells of, how far it carries, and whether one holder smells it now. O = RulesConfig().olfaction.

Smell is a sense for people. The common dead do not hunt by it (the lore's "they can smell you if
the wind's wrong" is a false belief); what gore does to them is world.infected INF-14.

SMELL-01 odour_of(store, body_id, at) -> Odour | None: what the body smells of, from what is on it
  (physical.bodies.condition_of) and, for a corpse, how long it has been dead. The candidates:
    'dead'      gore >= 2                                       strength = gore
    'death'     alive 0, kind not 'infected', dead_at set; h = (at - dead_at) / 3 600 000:
                h >= O.death_hours[2] -> 4, h >= O.death_hours[1] -> 3, h >= O.death_hours[0] -> 2,
                else no candidate
    'blood'     blood >= 3                                      strength = blood - 1
    'unwashed'  grime >= 3                                      strength = grime - 2
  The strongest; a tie goes to the first in ODOUR_KINDS order. None when there is no candidate or
  no such body. (Every infected body is caked in gore, physical.bodies LOOK-04: the dead reek of the
  dead, and so does anyone who has smeared themselves with them.)
SMELL-02 smell_range_m(store, strength, place_id) -> float: O.range_m[strength], times
  O.outdoor_mult when the place is not indoor (places.indoor 0).
SMELL-03 smells(store, holder_id, source_id, at) -> 'exact' | 'partial' | None: whether the holder
  smells the source now. None when source_id == holder_id (you get used to your own), when the
  holder is not alive with awareness 'awake', when the two are not in the same place (positions),
  when odour_of(source) is None, or when d = physical.space.point_distance(holder, source) is None or
  more than smell_range_m(its strength, the place); 'exact' when d <= that range / 2, else 'partial'.

ODOUR_KINDS and ODOUR_WORDS are implemented data: the words mind.perception and mind.packet use.
ODOUR_WORDS[kind] = (said of someone seen, smelled exactly; seen, smelled faintly; unseen, exactly;
unseen, faintly).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..kernel.store import Store, Tx

ODOUR_KINDS: tuple[str, ...] = ("dead", "death", "blood", "unwashed")

ODOUR_WORDS: dict[str, tuple[str, str, str, str]] = {
    "dead": ("Reeks of the dead.", "Smells faintly of the dead.",
             "The reek of the dead, close by.", "A faint reek of the dead."),
    "death": ("Gives off the smell of death.", "Smells faintly of death.",
              "The smell of death, close by.", "A faint smell of death."),
    "blood": ("Smells of blood.", "Smells faintly of blood.",
              "The smell of blood, close by.", "A faint smell of blood."),
    "unwashed": ("Smells of sweat and dirt.", "Smells faintly of sweat and dirt.",
                 "The smell of sweat and dirt, close by.", "A faint smell of sweat and dirt."),
}


@dataclass(frozen=True)
class Odour:
    kind: str       # one of ODOUR_KINDS
    strength: int   # 1..5


def odour_of(store: "Store | Tx", body_id: str, at: int) -> Odour | None:
    raise NotImplementedError("P3")


def smell_range_m(store: "Store | Tx", strength: int, place_id: str) -> float:
    raise NotImplementedError("P3")


def smells(store: "Store | Tx", holder_id: str, source_id: str, at: int) -> str | None:
    raise NotImplementedError("P3")
