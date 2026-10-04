"""Actors and dossier fusion (P4). Owner 'mind.actor'. Rules DOS-01..05.

Dossiers are stored as the FULL baseline JSON (never trimmed, DOS-01) plus deltas. ``fused`` applies
the actor's dossier_deltas in (at, delta_id) order to the baseline: op 'set' replaces the value at
the dotted path, 'append' appends value_json to the list at the path, 'remove' removes the first
equal list element (absent -> ValueError). A path segment that is not a key of the current
mapping -> ValueError naming the path (DOS-02) — deltas edit fields, they never invent them. The
result validates as ActorDossier/PCDossier again (DOS-03; PCDossier when the baseline carries a
'card').
display_name(actor) = actors.display_name. controller(actor) = actors.controller.
recent_lines(actor, n): pinned voice_lines first (oldest first), then the most recent unpinned
lines, at most n in total, the unpinned ones also oldest first.

Resolve.max = base + floor((E + C) / divisor) + capability.resolve_trait_mod  (RulesConfig.resolve)
Voice: packet exemplars = the dossier's 3 exemplars; recent_lines = last max_recent_lines rows of
voice_lines for the actor (pinned lines first) — voice consistency comes from the database (DOS-05).
(D-117) The lines are written by the speech itself: each SPEECH action.resolve commits for a speaker
with an actors row inserts that speaker's voice line (action.resolve SEG-03).

create(tx, body_id, dossier, source, at, turn_index, *, content_ref=None, mind_kind='model',
       cause_event_id=None, goal='', event_origin='sim') -> Event   (P10: worldgen, materialisation)
  ``dossier`` is a dict that validates as ActorDossier (PCDossier when it has a 'card'; ValueError
  otherwise). One MATERIALIZE {actor_id: body_id, source} (writer 'mind.actor', actor_id = body_id,
  origin = event_origin — worldgen passes 'worldgen') inserting dossiers
  {dossier_id (kind 'dos'), actor_id, source, content_ref, baseline_json = canonical_json of the
  validated record (model_dump mode 'json', by_alias), content_hash = sha256 of it} and actors
  {actor_id: body_id, dossier_id, controller = mind_kind ('model' | 'human' | 'policy'),
  display_name = identity.name, resolve_max = resolve_max(E, C, capability.resolve_trait_mod,
  tx.rules.resolve), resolve_cur = resolve_max, stress 0, goal_text = goal, lod_hint 'cold',
  accepted_authority '[]', quarantine 0}. A body that already has an actors row -> ValueError.
  (D-130) Then what they know: one LESSON_LEARNED {holder_id, cues, seed: true} (writer 'mind.mind',
  actor_id = body_id, the same origin) inserting a lessons row per registry cue of the dossier's
  knowledge.cues {cue_tags [cue], text f'Knows: {the cue's description}', confidence 3,
  source_event = the MATERIALIZE, at} — as the scenario loader seeds them (AFF-10) — when there are
  any. (D-130, LORE-02) The MATERIALIZE also inserts the lore they hold (seed_lore's rows for their
  dossier's cohort and the groups they are already in). Returns the MATERIALIZE.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..contracts.dossier import ActorDossier, PCDossier

if TYPE_CHECKING:
    from ..contracts.events import Event
    from ..contracts.settings import ResolveRules
    from ..kernel.store import Store, Tx


def create(tx: "Tx", body_id: str, dossier: dict, source: str, at: int, turn_index: int, *,
           content_ref: str | None = None, mind_kind: str = "model", cause_event_id: str | None = None,
           goal: str = "", event_origin: str = "sim") -> "Event":
    """P10: a person's dossier and actors row (see the module docstring)."""
    raise NotImplementedError("P10")


def resolve_max(E: int, C: int, trait_mod: int, rules: "ResolveRules") -> int:
    """rules.base + (E + C) // rules.divisor + trait_mod, never below 1. Built in P2: the scenario
    loader needs it to seed actors.resolve_max."""
    raise NotImplementedError("P2")


def fused(store: "Store | Tx", actor_id: str) -> ActorDossier | PCDossier:
    raise NotImplementedError("P4")


def display_name(store: "Store | Tx", actor_id: str) -> str:
    raise NotImplementedError("P4")


def recent_lines(store: "Store | Tx", actor_id: str, n: int) -> list[str]:
    raise NotImplementedError("P4")


def adjust_stress(tx: "Tx", actor_id: str, delta: int, cause_event_id: str, at: int,
                  turn_index: int) -> "Event | None":
    """Commit a RESOLVE_CHANGE event (writer 'mind.actor') whose payload is
    {"stress_delta": delta, "stress": new_value} updating actors.stress clamped to 0..10.
    delta 0 -> None. Used by the 'calm' speech effect (calm_person: CLEAN -2, COST -1) and by
    sustained fear (+1 per fear scene). Stress never modifies a roll; it feeds packets and
    portrayal only (P5)."""
    raise NotImplementedError("P5")


def controller(store: "Store | Tx", actor_id: str) -> str:
    """'human' | 'model' | 'policy'. Used ONLY by turn.pipeline to decide where an intent comes
    from; simulation modules must never call this (SYM-01)."""
    return store.query_one("SELECT controller FROM actors WHERE actor_id=?", (actor_id,))["controller"]
from ._impl_p4a import resolve_max, fused, display_name, recent_lines  # noqa
from ..action._impl_p5a import adjust_stress  # noqa
from ..world._impl_p10 import actor_create as create  # noqa


def seed_lore(tx: "Tx", holder_id: str, at: int, turn_index: int, *, origin: str = "sim") -> "Event | None":
    """LORE-02 (D-130): what everyone around them says, as they grew up hearing it. A person (an actors
    row on a human body) holds, of every canon lore entry (by ref) and each of its beliefs in order:
    those held_by 'common'; 'cohort:<c>' when their fused dossier identity.cohort is c; a faction
    ContentRef when they are a member (group_members status member or probation) of a group whose
    content_ref is it ('region:<tag>' is held by nobody yet). Held as lore_held rows {holder_id,
    lore_ref, belief (the index), confidence = the belief's, provenance 'childhood' for a
    cohort:post_fall_born belief (the only world they have known), 'group' for a faction's, else
    'common'; acquired_at} — never claim_holdings: what someone grew up hearing is not something they
    perceived, and it never competes with what they know (MEM-13). create writes them inside its
    MATERIALIZE (and the scenario loader inside each actor's), so a new person costs no extra event;
    this function adds what is missing for someone who already exists (worldgen WG7, once their
    groups exist): one MATERIALIZE {actor_id, source: 'lore', beliefs: n} (writer 'mind.actor',
    actor_id = holder, ``origin``) inserting the rows not yet held; nothing missing, or not a person
    -> None. The beliefs' cues are not given out (AFF-10's lore cues: SPEC_ISSUES SI-006). What it
    gives is brought to mind by mind.retrieval.lore_lines (LORE-03), never listed whole."""
    raise NotImplementedError("D-130")
from ._impl_lore import seed_lore  # noqa: E402,F811

