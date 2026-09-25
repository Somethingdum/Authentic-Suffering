"""Narrator continuity state (P11). Rules STYLE-03, NARR-09. Owner 'narration.narrator'.

The narrator keeps a little state between turns so its texture carries over and its pictures do
not repeat (05 §Narration): the NarratorStyle in narrator_state row 1, a world table, so a saved
run carries it and it survives save/load unchanged (STYLE-03).

load(tx) -> NarratorStyle
  NarratorStyle.model_validate_json(the style_json of narrator_state row id 1).
save(tx, style, turn_index) -> Event | None
  One SETTINGS_CHANGE event {source: 'narrator_state'} (writer 'narration.narrator', origin 'sim',
  at = kernel.clock.now) that UPDATEs narrator_state row id 1 with style_json =
  canonical_json(style.model_dump(mode='json')). When that is exactly the stored style_json,
  nothing is written and None is returned. (Replay leaves it alone: it has no 'field' key, and
  the replayed turn writes it again from the same prose.)
images(prose) -> list[str]   (NARR-09)
  The distinctive pictures a narration used, as 'adjective noun': every run of three words
  d a n of the narrator's own words — quoted speech is the Actor's and is not looked at
  (lint.unquoted) — where the words are lint WORD_RE matches with nothing but whitespace
  between them, and
    d.lower() is in DETERMINERS;
    a is all lowercase (a capital is a name: a name is never an image), is in neither
      lint.STOPWORDS nor DETERMINERS, and is an adjective: in ADJECTIVES, or at least 5 letters
      long and ending in one of ADJ_SUFFIXES;
    n is all lowercase, at least 3 letters long, in none of lint.STOPWORDS, DETERMINERS,
      ADJECTIVES, NOT_NOUNS or lint.IRREGULAR_PARTICIPLES, does not end in 'ly', and does not
      end in 'ed' when longer than 4 letters (a verb in the past: 'the enemy fired').
  The image is f"{a} {n}"; each image once, in the order it first occurs.
  'The rusted gate hung open. "The old dog," she said. A thin wind came through the broken
  window.' -> ['rusted gate', 'thin wind', 'broken window'].
scene_type(packet: NarratorPacket) -> str
  'arrival' when packet.establish_place; else 'talk' when any line has kind 'speech' and words;
  else 'action' when any line has kind 'outcome'; else 'quiet'.
update_after_turn(style, prose, scene_type) -> NarratorStyle   (NARR-09)
  A copy of style with recently_used_images = the old list without the prose's images, then the
  prose's images in order — the last MAX_IMAGES (30) kept — and recent_scene_type = scene_type.
  Every other field is unchanged. The next narration prompt lists the images as 'Images already
  used recently (do not reuse)' (prompts/narration.user.j2 from NarratorPacket.style).
Stage 17 (turn/pipeline.py), in the transaction that writes the narration, whatever the lint
  said: save(tx, update_after_turn(load(tx), prose, scene_type(packet)), T).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from ..contracts.narration import NarratorPacket, NarratorStyle

if TYPE_CHECKING:
    from ..contracts.events import Event
    from ..kernel.store import Tx

MAX_IMAGES = 30

DETERMINERS: frozenset[str] = frozenset("""
a an the his her its their my your our this that these those one some each every no
""".split())

ADJECTIVES: frozenset[str] = frozenset("""
bad bare big black bleak blind blue bright brown cheap clean clear close cold cool damp dark dead
deaf deep dim dry dull dumb faint fat fine firm flat foul free fresh full glad gold good grey gray
great green grim hard harsh high hot huge kind large late lean light live long loose loud low mad
mild narrow near neat new numb odd old open pale pink plain poor pure quick quiet rank raw red rich
ripe rough round rude sad safe sharp short shut sick slack slick slim slow small smooth soft sore
sour stale steep stiff still stark strange strong sweet swift tall tame taut thick thin tight torn
true vast warm weak wet white wide wild worn young
""".split())

ADJ_SUFFIXES: tuple[str, ...] = ("ed", "en", "y", "ful", "less", "ous", "ish", "ic", "al", "ble", "ive", "ing",
                                 "ent", "ant")

NOT_NOUNS: frozenset[str] = frozenset("""
ran sat stood came went saw fell rose froze shook took gave got knew heard lay began grew blew
flew knelt leapt slept wept crept swept bit hid slid spun spoke swung threw tore wore woke broke
drew drove ate sang sank thought was were has had did does
""".split())

_WORD = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")


def _is_adjective(a: str) -> bool:
    from .lint import STOPWORDS
    if not a.islower() or a in STOPWORDS or a in DETERMINERS:
        return False
    return a in ADJECTIVES or (len(a) >= 5 and a.endswith(ADJ_SUFFIXES))


def _is_noun(n: str) -> bool:
    from .lint import IRREGULAR_PARTICIPLES, STOPWORDS
    if not n.islower() or len(n) < 3 or n.endswith("ly") or (n.endswith("ed") and len(n) > 4):
        return False
    return not (n in STOPWORDS or n in DETERMINERS or n in ADJECTIVES or n in NOT_NOUNS or n in IRREGULAR_PARTICIPLES)


def images(prose: str) -> list[str]:
    from .lint import unquoted
    text = unquoted(prose)
    words = list(_WORD.finditer(text))
    out: list[str] = []
    for i in range(len(words) - 2):
        d, a, n = words[i], words[i + 1], words[i + 2]
        if text[d.end():a.start()].strip() or text[a.end():n.start()].strip():
            continue
        if d.group().lower() in DETERMINERS and _is_adjective(a.group()) and _is_noun(n.group()):
            img = f"{a.group()} {n.group()}"
            if img not in out:
                out.append(img)
    return out


def scene_type(packet: NarratorPacket) -> str:
    if packet.establish_place:
        return "arrival"
    if any(l.kind == "speech" and l.words for l in packet.lines):
        return "talk"
    if any(l.kind == "outcome" for l in packet.lines):
        return "action"
    return "quiet"


def update_after_turn(style: NarratorStyle, prose: str, scene_type: str) -> NarratorStyle:
    new = images(prose)
    kept = [i for i in style.recently_used_images if i not in new] + new
    return style.model_copy(update={"recently_used_images": kept[-MAX_IMAGES:], "recent_scene_type": scene_type})


def load(tx: "Tx") -> NarratorStyle:
    return NarratorStyle.model_validate_json(tx.query_one("SELECT style_json FROM narrator_state WHERE id=1")[0])


def save(tx: "Tx", style: NarratorStyle, turn_index: int) -> "Event | None":
    from ..contracts.events import Event, EventType, WriteOp, WriteRecord
    from ..kernel.clock import now
    from ..kernel.jsoncanon import canonical_json
    js = canonical_json(style.model_dump(mode="json"))
    if tx.query_one("SELECT style_json FROM narrator_state WHERE id=1")[0] == js:
        return None
    return tx.commit_event(Event(type=EventType.SETTINGS_CHANGE, writer="narration.narrator", at=now(tx), turn_index=turn_index,
                                 payload={"source": "narrator_state"},
                                 writes=[WriteRecord(op=WriteOp.UPDATE, table="narrator_state", values={"style_json": js},
                                                     key={"id": 1})]))
