"""Death screen and post-death truth reveal (P12). May import kernel.truth ONLY for the reveal,
which is shown after the player explicitly clicks 'Show me everything' (DEATH-10).

build_death_view(store, pc_id) -> DeathView
  cause_text from the DEATH event cause chain rendered as the PC would understand it; last_turns =
  the last 3 narrations; contributing = the PC's own committed choices in the cause chain (their
  ui labels), newest first, max 5.
truth_reveal(store, pc_id) -> list[str]
  The canonical account of the final scene and the hidden events that led to it: who was where,
  who decided what (from actions + private_reason), what the PC never perceived.
"""

from __future__ import annotations
