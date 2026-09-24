"""Bounded consultation (P4/P6, Actor v2 — Actor Spec §7 and §8). Rules CONSULT-01..06.
MUST NOT import as_engine.kernel.truth: every lookup is holder-local — this person's own records and
this call's options, from the same snapshot as the packet.

A deliberation may ask ONE consultation before it decides (turn.cognition REPLY-02). It is a lookup
inside the person's own head and menu, never a look through a drawer: inspecting, listening at a
door or reading a ledger are timed attempts on the menu. No consultation sees a canonical truth row
or another mind, and nothing physically happens until a final, validated decision reaches the
barrier. Query text and handles are data, never evaluated.

CONSULT-01 What a packet offers (mind.packet fills SkullPacket.consult_kinds): a reaction offers
  nothing; a deliberation offers 'recall', and 'more_actions' when the packet lists at least one
  family (CONSULT-03). 'compose' needs offered templates, which arrive with typed plans; until then
  it is never offered. A packet built with a consultation's answer offers nothing (one per
  decision) and lists no families.

family_of(defn) -> str   (implemented)
  defn.family when it is set; else, first match: effect eat / drink / rest / sleep -> 'care'; a def
  tagged 'posture' -> 'movement'; verb attack / escape / surrender -> 'conflict'; move / flee /
  take_cover / hide -> 'movement'; manipulate bound to a portal -> 'access'; manipulate otherwise,
  and search -> 'possessions'; treat -> 'care'; speak -> 'conversation'; signal -> 'expression';
  observe / guard / wait -> 'attention'; continue_task -> 'work'.

CONSULT-02 check(packet, consultation) -> str | None
  Why this consultation cannot be answered in this call, or None when it can, first match:
    kind not in packet.consult_kinds -> 'not_offered';
    a subject that is not a P# or S# key of packet.handles -> 'hallucinated_ref';
    recall with a blank or missing query and no subjects -> 'empty';
    more_actions whose family is not in packet.families -> 'not_offered'.
  turn.cognition treats a reason like any unusable answer (one repair, then HOLD-01).

CONSULT-03 families(affordances, defs) -> list[str]
  ``defs`` maps def id -> AffordanceDef. The keys of contracts.content.AFFORDANCE_FAMILIES, in that
  order, that have at least one option in affordances.pool that is not in affordances.options (by
  signature): the kinds of thing the person could also try that the menu does not show.

CONSULT-04 more_actions(affordances, family, subject_ids, defs) -> list[BoundAffordance]
  The options of affordances.pool, in pool order, that are not in affordances.options (by
  signature), whose def's family_of is ``family`` and — when subject_ids is not empty — whose
  target_id, destination_id or item_id is one of subject_ids; the first MAX_MORE.

CONSULT-05 recall(tx, packet, query, subject_ids, turn_index, at) -> list[str]
  Up to MAX_RECALL of the holder's own records that the packet does not already show, one line
  each, with where it came from and how long ago (the age worded as mind.packet words a belief's):
    episodes of the holder with decayed 0 that are not values of packet.handles, matching when a
      subject_id is in their subject_ids or, with a query, their rowid is in SELECT rowid FROM
      episodes_fts WHERE episodes_fts MATCH <the query's content words: lowercase runs of letters
      and apostrophes of 4 or more letters not in mind.retrieval.STOPWORDS, first occurrence kept,
      each double-quoted, joined with ' OR '> — ordered (salience desc, at desc, episode_id):
      f'You remember ({age}): {summary}';
    then the holder's live believed holdings (believed 1, superseded_by NULL; text and subject as
      mind.retrieval reads them — the proposition's, or a claims row's '<predicate> <value>' and
      subject_id) whose text is not the text of a packet belief, matching when their subject is in
      subject_ids or their text contains one of those content words as a whole word
      (case-insensitive) — ordered
      (confidence desc, acquired_at desc, claim_id): f'You believe ({provenance words}, {age}):
      {text}' (provenance words as mind.packet's provenance_text).
  Episodes first, then beliefs; the first MAX_RECALL in all. None found -> ['Nothing more comes back
  to you.'] — no record found means only that, never that it did not happen.

Consulted(kind, lines, options)   the answer mind.packet.build_packet shows (``consulted=``).
answer(tx, packet, affordances, consultation, defs, turn_index, at) -> Consulted   (CONSULT-06)
  ``consultation`` already passed check(). Subject ids: packet.handles[h] for a P# handle, the
  percept's source_id for an S# handle (a percept without a source adds nothing).
  recall        Consulted('recall', lines = recall(tx, packet, query, subject ids, turn_index, at)).
  more_actions  options = more_actions(affordances, family, subject ids, defs), appended to the menu
                as A handles after the ones already offered (unchanged handles keep their meaning:
                n = len(affordances.options), the new ones are A{n+1}..); lines = [f'More ways of
                {AFFORDANCE_FAMILIES[family]}: {"A{n+1}, A{n+2}, …"}.'] or, with none, [f'Nothing
                more of that kind comes to mind ({AFFORDANCE_FAMILIES[family]}).'].
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..contracts.common import Verb

if TYPE_CHECKING:
    from ..contracts.content import AffordanceDef
    from ..contracts.mind import Consultation, SkullPacket
    from ..kernel.store import Tx
    from .affordance import AffordanceSet, BoundAffordance

MAX_RECALL = 3
MAX_MORE = 12


@dataclass(frozen=True)
class Consulted:
    kind: str
    lines: list[str] = field(default_factory=list)
    options: list["BoundAffordance"] = field(default_factory=list)


def family_of(defn: "AffordanceDef") -> str:
    """CONSULT family rule (implemented)."""
    if defn.family:
        return defn.family
    v = Verb(defn.verb)
    if defn.effect in ("eat", "drink", "rest", "sleep"):
        return "care"
    if "posture" in defn.tags:
        return "movement"
    if v in (Verb.ATTACK, Verb.ESCAPE, Verb.SURRENDER):
        return "conflict"
    if v in (Verb.MOVE, Verb.FLEE, Verb.TAKE_COVER, Verb.HIDE):
        return "movement"
    if v == Verb.MANIPULATE:
        return "access" if defn.binds == "portal" else "possessions"
    if v == Verb.SEARCH:
        return "possessions"
    if v == Verb.TREAT:
        return "care"
    if v == Verb.SPEAK:
        return "conversation"
    if v == Verb.SIGNAL:
        return "expression"
    if v == Verb.CONTINUE_TASK:
        return "work"
    return "attention"          # observe, guard, wait


def check(packet: "SkullPacket", consultation: "Consultation") -> str | None:
    raise NotImplementedError("P4")


def families(affordances: "AffordanceSet", defs: dict[str, "AffordanceDef"]) -> list[str]:
    raise NotImplementedError("P4")


def more_actions(affordances: "AffordanceSet", family: str, subject_ids: list[str],
                 defs: dict[str, "AffordanceDef"]) -> list["BoundAffordance"]:
    raise NotImplementedError("P4")


def recall(tx: "Tx", packet: "SkullPacket", query: str | None, subject_ids: list[str], turn_index: int,
           at: int) -> list[str]:
    raise NotImplementedError("P6")


def answer(tx: "Tx", packet: "SkullPacket", affordances: "AffordanceSet", consultation: "Consultation",
           defs: dict[str, "AffordanceDef"], turn_index: int, at: int) -> Consulted:
    raise NotImplementedError("P7")
from ._impl_consult import check, families, more_actions, recall, answer  # noqa
