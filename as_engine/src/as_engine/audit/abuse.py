"""Abuse battery (P11). Rules ABUSE-01..08. [SALVAGE: IRONCLAD Step 9] — run by code against the
author, because the author is the threat.
  ABUSE-01 starting stat bands: generated actors' SPECIAL within content bands for their archetype
  ABUSE-02 bodyguard mortality: no body has passive immunity; god-mode flags only on cheat saves
  ABUSE-03 synergy caps: no check target exceeds 9 (clamp) and tag bonuses never stack
  ABUSE-04 gear rarity: items with rarity 'rare' do not exceed content caps per settlement
  ABUSE-05 base realism: every settlement has >= 2 vulnerabilities (portals with barricade < 2)
  ABUSE-06 infinite loops: repeating the same noise/resource/stealth action 20x does not duplicate items
  ABUSE-07 timer desync: every body's needs clocks advance with the world clock
  ABUSE-08 cheat leakage: a SANDBOX save's world invariants equal those of the clean twin (CHEAT-02)
"""

from __future__ import annotations
