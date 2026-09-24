"""Narrator continuity state (P11). Rules STYLE-03, NARR-09. Owner 'narration.narrator'.

load(tx) -> NarratorStyle; save(tx, style, turn_index) -> Event (narrator_state upsert).
update_after_turn(style, prose, scene_type) -> NarratorStyle
  recently_used_images: append distinctive 2-word noun phrases (adjective+noun) from the prose,
  keep the last 30; the next narration prompt lists them as 'images you already used — do not
  reuse'. recent_scene_type updated. Style survives save/load unchanged (STYLE-03).
"""

from __future__ import annotations

from ..contracts.narration import NarratorStyle


def update_after_turn(style: NarratorStyle, prose: str, scene_type: str) -> NarratorStyle:
    raise NotImplementedError("P11")
