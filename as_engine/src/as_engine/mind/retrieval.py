"""Memory retrieval for packets (P6). Rules MEM-10..17, SKULL-10. MUST NOT import kernel.truth.
docs/as/05_ACTORS.md §9.3.

MEM-10 The model never decides what it receives: everything here is computed by code from
  committed state, deterministically, every ordering ending with an id so ties cannot flip.

retrieve(tx, holder_id, turn_index, at, *, max_beliefs, max_memories, max_loops) -> Retrieved

MEM-11 Two key sets. The MOMENT set M (Retrieved.moment_keys) — what is in front of the holder now:
  * the holder's place id (positions);
  * every body that is the source_id of one of the holder's percept rows of this turn (the same
    row selection as the packet: this turn_index, at <= ``at`` — SKULL-10 —, older standing
    views excluded);
  * every body the holder can name that is named in perceived speech: for each speech row of that
    selection with non-empty detail.words and each acquaintance row of the holder with a known_name,
    the body when the known name — or its first word, when that word has 3 or more letters —
    occurs in the words as a whole word, case-insensitive;
  * the target_ids of the holder's current task (actors.current_task, else its first 'active'
    task by started_at).
  And K (Retrieved.keys) = M plus the subject_ids of the holder's 'open' loops — what is in front
  of it or on its mind. Beliefs and episodes use K; loops and refusals use M (ranking loops by K
  would be circular: every loop's subjects are in K).
MEM-12 recency_bonus(hours) = max(0.0, 20.0 - max(0.0, hours) / 6.0): 20 now, 10 after 2.5 days,
  0 from 5 days. hours = (at - t) / 3_600_000.
MEM-13 beliefs: the holder's live believed holdings (believed 1, superseded_by NULL); subject =
  the proposition's subject_id (a claims row: claims.subject_id); score = confidence * 10 +
  recency_bonus(hours since acquired_at) + (15 when subject is in K); ordered (score desc,
  claim_id asc); the first max_beliefs. Entries {claim_id, text, confidence, provenance,
  acquired_at, score}; text as mind.packet words a belief.
MEM-14 episodes: the holder's episodes with decayed 0.
  Anchors (anchor 1) come first and always: ordered (salience desc, at desc, episode_id), at most 2.
  Then the rest by score = salience + (20 when any subject_id is in K) + (15 when the episode
  matches the speech query) + recency_bonus(hours since episode.at), ordered (score desc,
  episode_id asc), until max_memories entries in total (anchors count toward it).
  Speech query: the content words of this turn's perceived speech (detail.words of the holder's
  speech rows, in row order): lowercase runs of letters and apostrophes with 4 or more letters,
  not in STOPWORDS, first occurrence kept; each double-quoted, joined with ' OR '. An episode
  matches when its rowid is in SELECT rowid FROM episodes_fts WHERE episodes_fts MATCH <query>.
  No words -> no episode gets the 15.
  Entries {episode_id, summary, at, salience, anchor, score}.
MEM-15 lessons: the holder's lessons whose cue_tags intersect mind.cues.cues_of(tx, holder,
  turn_index, at), ordered (confidence desc, at desc, lesson_id), at most MAX_LESSONS. Entries
  {lesson_id, text, confidence, cue_tags}.
MEM-16 loops: the holder's 'open' loops; those with any subject_id in M first, then the rest; each
  part ordered (strength desc, created_at desc, loop_id); the first max_loops. Entries {loop_id,
  kind, text, strength, subject_ids}.
MEM-17 refusals: the holder's refusals with status 'standing' or 'reopened' whose requester_id is
  in M — a standing refusal comes back when the one who asked is here or named (WILL-05) —
  ordered (created_at, refusal_id). Entries {refusal_id, requester_id, summary, times_asked,
  created_at}.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..kernel.store import Tx

MAX_LESSONS = 3

STOPWORDS: frozenset[str] = frozenset({
    "about", "after", "again", "also", "back", "been", "before", "being", "come", "could", "didn't",
    "does", "doesn't", "done", "don't", "down", "even", "every", "from", "going", "gonna", "good",
    "have", "haven't", "here", "into", "it's", "just", "know", "like", "look", "made", "make", "many",
    "more", "much", "must", "need", "never", "only", "other", "over", "really", "right", "said",
    "same", "should", "some", "still", "such", "take", "tell", "than", "that", "that's", "their",
    "them", "then", "there", "these", "they", "they're", "thing", "think", "this", "those", "want",
    "well", "we're", "were", "what", "what's", "when", "where", "which", "while", "will", "with",
    "won't", "would", "yeah", "you're", "your", "yours",
})


@dataclass
class Retrieved:
    beliefs: list[dict] = field(default_factory=list)
    episodes: list[dict] = field(default_factory=list)
    lessons: list[dict] = field(default_factory=list)
    loops: list[dict] = field(default_factory=list)
    refusals: list[dict] = field(default_factory=list)
    keys: set[str] = field(default_factory=set)
    moment_keys: set[str] = field(default_factory=set)


def retrieve(tx: "Tx", holder_id: str, turn_index: int, at: int, *, max_beliefs: int, max_memories: int,
             max_loops: int) -> Retrieved:
    raise NotImplementedError("P6")


def recency_bonus(hours_since: float) -> float:
    raise NotImplementedError("P6")
from ._impl_p6 import retrieve, recency_bonus  # noqa
