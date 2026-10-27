# 16. The hosted engine (D-299)

The owner, 2026-10-26: *"Use THIS to replace the role play engine. Providing every feature, but better."* — *"It needs
to cleanly mesh with [the harness]. It needs to use the same model router and be routed BY [it], and be compliant with
all of its rules."* — and, about the game's own world: **"Keep the lore in."**

The engine can run as a component of a host — the owner's own harness — that routes every model call. This page is
the narrative; the contract is the docstrings of `as_engine/host/*.py` (rules HOST-01..HOST-27) and LANE-12 in
`lanes/client.py`, and the tests are `as_engine/tests/contract/p13_hosted/`.

## 1. Who decides what

| | Standalone (the Play UI) | Hosted |
|---|---|---|
| Which model answers a call | the call's lane (A the Writer, B the Clerk, D-111) | **the host**; the lane is only the *kind* of work: A narrative, B engineering |
| A model that is down | DEGRADE-01 moves the work, LANE_A_DOWN tells it plainly | the host routes or refuses; the engine never marks a lane down (LANE-12) |
| Thinking, `max_tokens`, sampling | the regimes | the host's caps and presets; the regimes say only what a call is worth |
| What fits in the time | `SchedulerRules` budgets and `estimated_call_s` | **the host's budget**: the engine declares steps and asks before each optional one (HOST-06..09) |
| Who writes the prose | the narration call on lane A | the host's own reply (`write`), drafted again only for the lint (HOST-10..12) |
| Where the world lives | `as_runs/<run>/world.sqlite`, saves, the autosave ring | in memory; the host keeps the bytes (HOST-02) |
| Branches | saves | forks rebuilt from the branch's recorded answers (HOST-21..23) |
| The network | the seal allows the model machines | the seal allows nothing but loopback; the engine opens no socket (HOST-24) |

## 2. The process

The host starts `python -I -m as_engine.bridge --content <packs>` and talks JSON lines on its pipes (§3). The process is
sealed before anything else runs; it writes no file, holds no key, logs no story text. One process holds one story.

## 3. The protocol

`host/protocol.py` has the framing and every request's fields. In short:

- **Host → engine**: `hello` (versions; `sealed`), `menu` (the character cards and RunSettings' schema), `begin` (a new
  world: worldgen in memory, the genesis back as bytes, the seed told first), `open` and `save` (worlds in and out),
  `turn` and `compose` (a move, with the tier 1–5 the player chose), `cancel` (Stop), `view`, `story`,
  `settings_get` / `settings_set`, `code_enter`, `cheat_dictionary`, `death_reveal`, `quiet` (the quiet hours, only when
  the host asks), `fork`, `close`, `ping`.
- **Engine → host**: `model.call` and `write` (each with its *work*: kind, role, step, think class, answer size,
  background / idle / optional, a label with no name in it, and for a review the call id it reviews), `budget.declare`,
  `budget.may`; notices `progress` and `begin.seed`.
- Every answer that changed the world carries the new world envelope, its sha256 and turn, and `keep` when the change
  cannot be replayed by a fork (the console between turns), so the host keeps that world.

## 4. A hosted turn

1. The host sends `turn {text, tier}`. The tier sets the turn's depth (a recorded settings change) and the governor.
2. The engine declares its steps: required (`intake`, `write`, every mandatory mind) and optional, each with a unique
   rank — the portrayal check goes first, then the room's remarks, later reaction waves, background minds (least
   salient first), anyone's full voice, and the second reading of the prose last.
3. Stage 4 plans who thinks: in focus (narrative) up to the tier's focus count, background minds (engineering) as far
   as the host allows; the people the turn is about always decide; nobody's competence, knowledge or morality changes
   with it (LOD-01).
4. Every call goes to the host. A call the host leaves out answers as an ablated call does, and the engine takes the
   path it already has.
5. The prose is a `write`: the host's own model writes it as the chat's reply; a lint failure is a second `write`;
   Stop during writing tells the moment plainly and never drafts again.
6. The answer carries the messages the Play UI would have shown (turn_result, story, view, doom, death …), the
   budget's decisions, and the world.

A host that crashed mid-turn sends the same turn again with the answers it gave and its decisions: no model call is
made twice and the world comes out the same.

## 5. Branches

The latest world of a branch holds every answer its branch got (the call log) and every budget decision (the ledger).
`fork {base, head, turn}` rebuilds the world at `turn` from the nearest kept world `base`, replaying each turn with no
model call and checking every turn's state hash; anything else is refused with the reason.

## 6. What a hosted story never does

- **It never asks the player a question** (INTAKE-10): an unclear move is read as the offered option nearest to it;
  a move that cannot be played is one plain statement, never a question. Out-of-character talk is the host's.
- **The one hard limit holds whatever model writes** (LIMIT-01): where anyone under 18 is present — alive or dead,
  the player's character included — a draft with sexual content is never shown; when every draft has it, the moment
  is told plainly by code. The words it looks for are only unambiguous ones, so ordinary survival prose ("he gropes
  for the flashlight", "the noise aroused the dead") passes. Nothing else is limited: the story may be as dark as the
  writer wants. An intimate act is offered only between two adults (D-292), and a pack that offers one otherwise does
  not load (CNT-18).
- **The writer never steps out of the story** (META-01): a draft that refuses, apologises, adds a note or talks about
  being a model is written again (a character may say any of it, in quotes).
- **No model is named in the engine's code**: the owner's two models are configuration
  (`contracts/default_lanes.json`); the hosted engine never uses them at all.

## 7. The world's own lore

The owner ruled "Keep the lore in": the engine ships with its world — the core pack, the Fall, the strains and the
infected, the hordes, the Doom and the Voice, Willis, its people and places — wherever it is hosted. The owner's own
saved stories and private documents are theirs and are never read by tests or builds.

## 8. Where the code goes

The engine moves into the owner's harness (the owner's choice), under that harness's own licence: the engine is the
owner's own code — nothing in it is Talemate's (BOUND-01) — so the AGPL of this repository's Talemate fork does
not reach it. Until the move, this repository is its home.
