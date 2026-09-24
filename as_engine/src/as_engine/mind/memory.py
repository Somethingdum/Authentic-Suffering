"""Aftermath and memory writeback (P6). Rules MEM-01..09, L8. MUST NOT import kernel.truth.
Owner 'mind.memory' (episodes). Relationships, loops and lessons are written through mind.mind,
beliefs through mind.perception.infer (the knowledge writers), dropped items are logged through
audit.log.repair. docs/as/05_ACTORS.md §9.

MEM-01 build_aftermath(tx, holder_id, turn_index, at) -> AftermathPacket   (Stage 13, gate G13)
  Exactly what the holder perceived this turn and nothing else — the same selection and handles as
  the Skull Packet (mind.packet; reuse its helpers, the two must agree):
  percept rows  the holder's percept_log rows with this turn_index and at <= ``at`` (SKULL-10; at
                stage 13 ``at`` is the end of the window, so every row of the turn), except
                standing-view rows (event_id 'scene:…') older than the latest standing view among
                them, ordered (at, percept_id).
  handles       S1..Sn over percepts and utterances together, in that order (one numbering);
                P1..Pn bodies, each once, never the holder: the source_id of those rows when it is
                a body, in row order, then bodies the holder has relationships rows toward (by
                to_id), then the other members of its households (by actor_id); L1..Ln its open
                loops (below). ``handles`` maps each handle to its id (percept_id, body id, loop_id).
  percepts      non-speech rows as PerceivedItem(handle, channel, fidelity, text, source_handle =
                the P-handle of source_id or None, seconds_ago = (at - row.at) / 1000).
  utterances    speech rows as UtteranceView, built exactly as mind.packet builds them.
  entities      PacketEntity per P-handle, as mind.packet (known_name, description,
                relation_summary, whereabouts).
  identity      the holder's whole card, mind.identity.compile_identity(mind.actor.fused(tx,
                holder_id)) (IDN-01): what happened is read by this person, as this person.
  own_action_text   what the holder did itself this turn (it never perceives its own actions):
                None when it committed no SPEECH and no ACTION_START this turn (events with
                actor_id = holder and this turn_index); else these sentences, in event seq order,
                joined with one space:
                  SPEECH        f'Said: "{payload.words}"'
                  ACTION_START  f'Chose to {label}.' — label = payload.label without a trailing
                                parenthesised part (' (4 m, about 3 seconds)'), first letter
                                lower-cased; skipped for def_id 'speak' (its SPEECH says it).
                e.g. 'Said: "Quiet." Chose to move to the rear shelving.'
  own_expectation_text   payload.goal of the holder's LAST ACTION_START this turn when it is not
                empty and differs from that start's payload.label; else None.
  open_loops    the holder's loops with status 'open', ordered (strength desc, created_at desc,
                loop_id), at most PacketRules.max_open_loops: LoopLine(L#, kind, text).
  relationships RelationshipLine per P-handle with a relationships row from the holder, in handle
                order, worded exactly as mind.packet words them.

MEM-03 writeback_groups(packets: dict[holder_id, AftermathPacket]) -> list[list[holder_id]]
  Holders may share ONE writeback call only when nothing in their packets is private
  (own_action_text None, no open_loops, no relationships) AND the packets agree, in order, on every
  percept (channel, fidelity, text, source body id), every utterance (words, volume,
  addressed_to_me, fidelity, speaker body id) and every entity (body id, description). Such holders
  with equal keys form one group; every other holder is a group of one. Each group is sorted by
  holder id; groups are ordered by their first holder id. The shared call is rendered from the
  first holder's packet; its output is applied to EACH member with that member's own packet, so
  every handle resolves to the member's own percepts.

MEM-02 apply_writeback(tx, holder_id, output, packet, at, turn_index, *, cue_ids) -> list[str]
  (Stage 14, gate G14: a mind writes nothing that cites what it did not perceive.)
  ``cue_ids`` = the registry cue ids (Canon cues). Handle kinds: a percept handle is a key of
  packet.handles starting 'S', an entity handle one starting 'P', a loop handle one starting 'L'.
  Each item is checked on its own, in the order beliefs, relationships, new_loops, closed_loops,
  lesson; a failing item is DROPPED — only that item — and audit.log.repair(kind
  'hallucinated_ref', stage 14, rule_id 'MEM-02', detail {holder_id, item, index, ref}) is written
  (item 'belief' | 'relationship' | 'new_loop' | 'closed_loop' | 'lesson'; index = its position in
  its list, 0 for the lesson; ref = the first bad reference, checks in the order listed):
    belief        every ``because`` is a percept handle; ``about`` is 'self', 'place' or an entity handle
    relationship  ``because`` is a percept handle; ``with`` is an entity handle
    new_loop      ``because`` is a percept handle; ``subject`` is None or an entity handle
    closed_loop   ``because`` is a percept handle; ``loop`` is a loop handle whose loop is still 'open'
    lesson        ``because`` is a percept handle; cue tags not in ``cue_ids`` are removed — with none
                  left the lesson is dropped (ref = its first tag)
  The rest is applied, in this order; returns the ids of every event this call committed, in commit
  order (read back by seq).
  MEM-04 episode  always (even when every other item was dropped): EPISODE_WRITTEN (writer
                  'mind.memory', actor_id = holder, cause_event_id = the event of the first percept
                  row in handle order whose event_id is a committed event, else NULL) {episode_id,
                  holder_id, salience, anchor}; episodes INSERT (episode id kind 'epi', at,
                  turn_index, place_id = the holder's place (positions), summary = output.episode
                  stripped, salience, percept_ids = the S-handle ids in handle order, subject_ids =
                  the P-handle ids in handle order, anchor, decayed 0). The episodes_fts row comes
                  from the schema trigger.
  MEM-06 anchor   1 when salience >= 90, or when a percept of the packet is of a DEATH or FALSE_DEATH
                  event (the holder cannot tell them apart) whose source is a body the holder is
                  bonded to: a relationships row from the holder toward it with affection >= 2 or
                  kind in BONDED_KINDS; else 0. Anchor memories never decay and are always
                  retrieved first (mind.retrieval MEM-14).
  MEM-05 beliefs  per belief, in order: perception.infer(holder, about = ('body', the entity's id)
                  | ('self', None) | ('place', None), text = claim, confidence, because = the cited
                  percept ids).
  MEM-07 relationships  mind.mind.relate(holder, the entity's id, axis, delta, cause = the cited
                  percept's event_id — percept_log.event_id, which may be a 'scene:N' reference).
         new_loops      mind.mind.open_loop(holder, kind, text, [subject's id] or [], strength,
                  cause = the cited percept's event_id).
         closed_loops   mind.mind.close_loop(the loop's id, status, cause = the cited percept's
                  event_id).
         lesson         mind.mind.learn(holder, the kept cue tags, text, expectation =
                  packet.own_expectation_text or '', outcome = the cited percept's text, cause =
                  the cited percept's event_id).
  MEM-08 The PC gets writeback exactly like everyone else (L12): its episodes feed the Journal and
  the recap.
MEM-09 Nothing here reads another mind or the truth layer: every id apply_writeback uses comes
  from this holder's packet handles, and build_aftermath reads only this holder's rows plus its
  own ACTION_START / SPEECH events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..contracts.mind import AftermathPacket, WritebackOutput

if TYPE_CHECKING:
    from ..kernel.store import Tx

BONDED_KINDS: tuple[str, ...] = ("parent", "child", "sibling", "spouse", "partner")


def build_aftermath(tx: "Tx", holder_id: str, turn_index: int, at: int) -> AftermathPacket:
    raise NotImplementedError("P6")


def writeback_groups(packets: dict[str, AftermathPacket]) -> list[list[str]]:
    raise NotImplementedError("P6")


def apply_writeback(tx: "Tx", holder_id: str, output: WritebackOutput, packet: AftermathPacket,
                    at: int, turn_index: int, *, cue_ids: frozenset[str] | set[str]) -> list[str]:
    raise NotImplementedError("P6")
from ._impl_p6 import build_aftermath, writeback_groups, apply_writeback  # noqa
