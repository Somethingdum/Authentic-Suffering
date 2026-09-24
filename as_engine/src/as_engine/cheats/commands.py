"""Cheat activation, parsing and execution (P12). Owner 'cheats' (cheat_log) — state changes go
through the owning modules' APIs with Event.origin = 'cheat' and type CHEAT_OVERRIDE.

detect_activation(text) -> bool   (CHEAT-01)
  True when the standalone token 2508 appears: re.search(r"(?<!\\d)2508(?!\\d)", text).
  Activation commits CHEAT_ACTIVATED, sets meta.cheat_active = '1', and the UI receives
  cheat_activated {persona_line} (the narrator tell is a UI shimmer; the narrator itself never
  knows — cheat vocabulary appears in NO narrator/actor prompt, ever: CHEAT-03).
  The input line that contained the token is consumed by activation (no turn is played).

parse(text) -> CheatCommand | CheatParseError   (CHEAT-02) — only when cheat_active and text
  starts with '/'. The full grammar, argument vocabulary and persona live in docs/as/CHEATS.md
  (the bonus document); this list is the machine contract. Command words are case-insensitive;
  arguments may be quoted with "..." to include spaces; <person>, <place>, <item> resolve by
  name (see Resolution below).
    /help                                   list commands (persona voice)
    /off                                    deactivate (CHEAT_DEACTIVATED; persona signs off)
    /give <item> [<qty>] [to <person>]      ITEM_CREATED origin 'cheat' (default: to the PC's pack)
    /heal [<person>]                        remove wounds, blood loss 0, needs 0, pain 0
    /god on|off [<person>]                  toggle meta 'god_bodies' membership for that body
    /tp <place>                             move the PC (MOVE origin 'cheat') to a known or named place
    /set <stat> <value> [<person>]          stat in S P E C I A L (1..10), resolve (0..max),
                                            or a skill domain (0..3) -> dossier_deltas row
    /time +<n>h                             advance the world clock n hours (1..720) through the
                                            normal off-screen tick (the world keeps living)
    /weather <kind>                         clear|overcast|rain|storm|fog|wind|heat|snow
    /rep <group> <-5..5>                    set group_standing toward the PC
    /spawn <what> [x<n>] [ally]             <what> = an actor/pc dossier ref (core:actor/mara_voss),
                                            a cheat-pack dossier id (e.g. fredrick), or an infected
                                            type word (shambler|crawler|runner|lurker); n 1..20;
                                            'ally' adds the PC to the spawned actor's
                                            accepted_authority. Placed at the PC's place.
    /despawn <person or item>               remove a CHEAT-ORIGIN entity only; emits CHEAT_OVERRIDE
                                            with payload {"reconciliation": true} (quarantine repair)
    /kill <person>                          DEATH with cause 'cheat'
    /revive <person>                        alive again, wounds cleared (origin 'cheat'); infection
                                            state is left exactly as it was — no command cures
                                            (CMG §42.2, lore core:lore/no_cure)
    /reveal                                 truth-layer summary of the PC's place and adjacent places
                                            (cheat message only)
    /mind <person>                          that actor's current goal, plan, top beliefs, open loops
                                            and last private_reason (cheat message only)
    /brief <person>                         GRANT that actor the current truth about the PC's place,
                                            present people and known factions as beliefs
                                            (perception.grant, provenance 'cheat', confidence 3).
                                            This is how an omniscient cheat companion stays inside
                                            Skull Law: it believes true things because a cheat put
                                            them in its head, and nothing else changes.
    /noise <db> [here|at <anchor>]          a NOISE event of that level (40..180)
  Resolution: names resolve against what the PC knows first (acquaintance, known_places), then
  every entity (display names, place names, item names, group names), case-insensitive; exact
  match first, else difflib.get_close_matches(cutoff=0.8); ambiguity or no match ->
  CheatParseError naming the candidates. Unknown command word -> CheatParseError whose message is
  a persona line (never a stack trace).

execute(session, command) -> CheatResult(ok, persona_line, detail, events)   (CHEAT-04..07)
  Runs in its own store transaction OUTSIDE the turn pipeline; takes no world time (except /time);
  CHEAT_OVERRIDE is not a sensory event (perception ignores it — people perceive only the
  resulting state at the next compile).
  Every executed command: cheat_log row (verbatim command, outcome, persona line), CHEAT_OVERRIDE
  event with origin 'cheat'; every command NOT in SANDBOX_EXEMPT also sets meta.sandbox = '1'
  (irreversible for the run; the run card and top bar show it).
  Cheat packs (CHEAT-10): packs whose id starts with 'cheat_' are compiled with the others but only
  /spawn may resolve their dossiers; worldgen and the New Life wizard never read them.
  Quarantine (CHEAT-05): spawned bodies/items get origin 'cheat'; actors.quarantine = 1;
  worldgen, threat scaling, faction balance and the abuse battery exclude quarantined entities.
  God mode: meta 'god_bodies' JSON list; bodies.apply_harm skips wounds for listed bodies (the
  check is per body, never per player — L12).
  /reveal and /mind return text for the cheat message only; they never enter narration or any
  actor packet (CHEAT-06). /brief is the one command that writes beliefs, and only through
  perception.grant (so every belief it creates is visible in percept_log with origin 'cheat').
  Persona lines (CHEAT-09): the CHEAT_PERSONA call (lane B) writes one line per executed command
  with the last 5 persona lines listed as 'do not repeat'; on any failure a canned line from
  CANNED_LINES[command] is used, never the same canned line twice in a row (rng stream 'cheats').
  Standing brief (CHEAT-11): an actor whose dossier carries the tag 'standing_brief' (allowed only
  in cheat_ packs; generation 'cheat') is briefed automatically at Stage 2 of every turn in which
  it is HOT or WARM, before its packet is built: the /brief grant PLUS the truth_text of every
  loaded faction, the current goal and dossier secrets of every body present, and the positions of
  infected within two route hops. Same door (perception.grant, provenance 'cheat', confidence 3),
  no cheat_log row (the spawn already logged it), and nothing changes for anyone else. This is
  Fredrick's "engine-level awareness" (your Batch-2 idea) implemented inside Skull Law.
  Hard line (CHEAT-08): no command, argument or spawned dossier may produce sexual content
  involving a minor; CNT-11 validation runs on every spawned dossier. This outranks cheats.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

ACTIVATION_RE = re.compile(r"(?<!\d)2508(?!\d)")

CommandName = Literal["help", "off", "give", "heal", "god", "tp", "set", "time", "weather", "rep",
                      "spawn", "despawn", "kill", "revive", "reveal", "mind", "brief", "noise"]

SANDBOX_EXEMPT: frozenset[str] = frozenset({"help", "off"})

COMMAND_NAMES: tuple[str, ...] = ("help", "off", "give", "heal", "god", "tp", "set", "time", "weather",
                                  "rep", "spawn", "despawn", "kill", "revive", "reveal", "mind",
                                  "brief", "noise")

ACTIVATION_LINE = ("Alright, alright, settle down. 'Mr. Cheater Man' reporting for duty, Boss. Systems "
                   "unlocked, safeties vaporized. You now wield the digital thunder. What reality shall "
                   "we rewrite today?")
DEACTIVATION_LINE = "Right you are, Boss. Reality re-solidifying... mostly. Enjoy the ripples."
SHIMMER_NOTICE = "A barely perceptible shimmer passes over the world for a moment."
RETIRED_SPAWNS: dict[str, str] = {
    "campervan": ("Whoa there, Boss! The 'Camper-Van of the Gods'? Ah, you speak of legends! That thing "
                  "was so unbelievably cool it started to unravel reality just by existing. The devs had "
                  "to vault it. You'll have to settle for slightly less game-breaking miracles today."),
}

# Canned persona lines (fallback when the CHEAT_PERSONA call fails). Two per command; the executor
# never uses the same canned line twice in a row. Full table with voice notes: docs/as/CHEATS.md.
CANNED_LINES: dict[str, tuple[str, str]] = {
    "help": ("Here's the keyring, Boss. Try not to lose any fingers.",
             "The menu of sins, as requested."),
    "give": ("Conjured and pocketed. Consequences are for the un-cheated.",
             "Done. Somewhere a quartermaster just felt a chill."),
    "heal": ("Stitched, scrubbed and good as new. Don't tell the medics.",
             "Blood back in, holes closed. Try to keep it that way for five minutes."),
    "god": ("God mode toggled. The universe will apologise if it inconveniences you.",
            "Mortality settings adjusted. Handle with smugness."),
    "tp": ("Relocated. Nobody saw anything, mostly.",
           "And you're there. Mind the landing."),
    "set": ("Numbers nudged. Nature can file a complaint.",
            "Stat rewritten. The dossier is sulking."),
    "time": ("Clock wound forward. The world kept living without you, as it does.",
             "Hours gone. Check your water."),
    "weather": ("Sky reconfigured. Dress accordingly.",
                "Weather swapped. The locals will blame the gods."),
    "rep": ("Reputation adjusted. They'll never know why they feel that way.",
            "Standing rewritten. Enjoy the new looks you get."),
    "spawn": ("Materialised beside you, Boss. Quarantined, of course — I'm reckless, not stupid.",
              "One fresh arrival. They're on the naughty list, balance-wise."),
    "despawn": ("Gone like they were never there. The paperwork says otherwise.",
                "Unmade. The ledger keeps the receipt."),
    "kill": ("Lights out. Grim, but you're the Boss.",
             "Done. Somebody's going to find that."),
    "revive": ("Back from the dark. They won't be thanking anyone.",
               "Heart's going again. Don't ask how."),
    "reveal": ("Curtain's up. Just for you.",
               "Here's what's actually going on. Don't let it go to your head."),
    "mind": ("Peeking inside. Wipe your feet.",
             "Here's what's rattling around in there."),
    "brief": ("Briefed. They now know what you'd have to be a god to know.",
              "Knowledge injected. They'll think they worked it out themselves."),
    "noise": ("Made a racket. Hope that was the plan.",
              "Loud enough? Everything nearby agrees it was."),
    "off": (DEACTIVATION_LINE, DEACTIVATION_LINE),
}


@dataclass
class CheatCommand:
    name: CommandName
    args: dict[str, Any] = field(default_factory=dict)
    raw: str = ""


@dataclass
class CheatParseError:
    message: str


@dataclass
class CheatResult:
    ok: bool
    persona_line: str
    detail: str = ""
    event_ids: list[str] = field(default_factory=list)


def detect_activation(text: str) -> bool:
    """Implemented (CHEAT-01)."""
    return bool(ACTIVATION_RE.search(text))


def parse(text: str) -> CheatCommand | CheatParseError:
    raise NotImplementedError("P12")


def execute(session, command: CheatCommand) -> CheatResult:
    raise NotImplementedError("P12")


def is_cheat_question(text: str) -> bool:
    """Ask-mode deflection trigger (CHEAT-03): any of 'cheat', 'god mode', 'godmode', 'noclip',
    'infinite ammo', 'console', 'dev mode', 'developer', 'mr. cheater', 'code' + 'unlock'.
    Implemented."""
    t = text.lower()
    keys = ("cheat", "god mode", "godmode", "noclip", "infinite ammo", "console", "dev mode",
            "developer", "mr. cheater", "mr cheater")
    return any(k in t for k in keys) or ("code" in t and "unlock" in t)
