"""Death screen, Willis in the frozen moment, and the post-death truth reveal (P12; D-105, D-106).
May import kernel.truth ONLY for the reveal, which is shown after the player explicitly clicks
'Show me everything' (DEATH-10).

The owner (D-105): "When you die, regardless of Wildcard activation, you see Willis. He mocks and
roasts you joyously over your mistakes." (D-106): he comes to you in the frozen moment when your
death becomes certain — the Doom scene (service.voice) — and "when a non-Willis character uses
cheats, it's considered a loan from Willis. It's his power. He'll mock you twice as hard." Then
something takes him, and the Voice speaks. Rules DEATH-10..14.

CAUSE_WORDS: the DEATH causes (physical.bodies) in the dead person's own terms, second person.

build_death_view(store, pc_id) -> DeathView
  DEATH-11 From the newest DEATH event whose payload body_id is pc_id (ValueError "no death for
  {pc_id}" when there is none):
  - cause_text = CAUSE_WORDS.get(cause, "You died.") and then, each after one space, what the PC
    itself perceived of how it came to this: the texts of its own percept_log rows (holder pc_id)
    for the DEATH's cause event and the events the DEATH links as 'contributed', oldest first,
    distinct, at most 3 — nothing the PC never perceived;
  - pc_name = the PC's actors.display_name; day = world_time(death at).day; time_text =
    format_clock(death at);
  - last_turns = the texts of the last 3 narration rows, in turn order;
  - contributing = the PC's own choices (the non-empty labels of ACTION_START events whose actor is
    the PC): first those reached walking the cause chain back from the DEATH (cause_event_id and
    links, breadth first, at most 200 events), newest first; then the PC's latest before the death,
    newest first; distinct labels, at most 5;
  - willis = roast_stored(store, pc_id) or [] (he came in the frozen moment); willis_pending False;
  - voice = the story's 'voice' texts of the Doom scene's turn (service.voice.scene_turn), then its
    'voice_after' texts of the death's turn (service.voice VOICE-09), at most 8; voice_pending = the
    PC has a doom and no 'voice_after' yet;
  - can_new_life_here = can_load = the run is not Ironman (meta settings_json save_mode);
    world_id = meta world_id.

roast_facts(store, pc_id) -> RoastFacts
  DEATH-12 What Willis has in the frozen moment — the dead person's own record only (never
  kernel.truth: the world's secrets are the Voice's to tell). doom = physical.bodies.doomed(store,
  pc_id) (ValueError f"no doom for {pc_id}" when there is none); the DOOM event's seq bounds
  everything. This life began at the first PLAYER_INPUT after the PC's latest PC_CONTROL_CHANGE
  (payload pc_actor_id = pc_id), else at the first PLAYER_INPUT:
  pc_name; lived = lifespan_words(doomed_at - that start); turns = the PLAYER_INPUT events from that
  start to the DOOM; cause_text '' (he does not know how, and does not care); choices = the labels
  of the PC's last 5 ACTION_STARTs before the DOOM, newest first, distinct; typed = the raw_text of
  the player's last 5 'do' / 'say' player_inputs of this life, oldest first; bent_rules = meta
  sandbox '1'; borrowed = the cheat_log commands of this life (turn_index from the turn of that
  PC_CONTROL_CHANGE, else from 0), the last 8, oldest first; in_debt = borrowed is not empty and the PC is not in the reality
  exception (the power is his: a loan, D-106); ironman; rises False (not known yet); met_him = the
  PC has an acquaintance row for a body in the reality exception (physical.bodies.excepted);
  by_his_hand = a body in the reality exception is the actor of an event reached walking back from
  the doom's cause_event.

lifespan_words(ms) -> str
  < 1 hour: mind.affordance.duration_words(ms / 1000); < 2 days: f"{hours} hours" (rounded, at least
  1: "1 hour"); else f"{days} days" (rounded down).

roast_stored(store, pc_id) -> list[str] | None
  Willis's lines: the story_log texts of kind 'willis' at the turn of the PC's Doom scene
  (service.voice.scene_turn), in order; None when there are none (or no doom, or no scene yet).

async roast(session) -> list[str]
  DEATH-13 Willis in the frozen moment of every death of the PC (service.voice VOICE-07) —
  regardless of the Wild Card, the console, the difficulty or Ironman. Stored lines are returned
  as they are (no call). Otherwise ONE WILLIS_ROAST call (lane A; lanes.requests.build_request(config,
  WILLIS_ROAST, turn_index = the current turn, context = ctx = WillisRoastContext(facts =
  roast_facts(store, session.pc_id)), json_schema = lanes.schemas.to_lm_schema(WillisRoast))); lines
  = the output's lines, each stripped and cut to 300 characters, empty ones dropped, at most 3 —
  6 when in_debt ("twice as hard"). ANY failure of the call (the lane down, a timeout, an unparseable
  or empty answer, an exception from the transport) -> fallback_roast(facts): he always comes.
  Nothing is stored or recorded here: the pipeline stores the whole scene, in order, and records
  every call of its turn.

fallback_roast(facts) -> list[str]
  DEATH-14 Willis without a model, from the facts only. He never finishes: the last line ends in
  an em dash, where the thing takes him.
  in_debt (six lines, twice as hard): "Well, well, well. Look who's in my debt."; f"You borrowed
  my power {n} time(s), and you spent it on '{borrowed[-1]}'."; "That's not a loan, that's a
  confession."; "You had MY power. Mine. And you still ended up here, frozen, about to die like
  everybody else."; by_his_hand -> "And yes, I helped. You had it coming, and I had a free minute."
  else "Do you know what I do to people who owe me? Nothing. I watch. It's funnier."; "Ha! Now,
  about collecting. See, the thing about borrowing from me is—".
  met_him: "Oh, it's you from earlier."; by_his_hand -> "Yeah, that was me, by the way. Worth
  it."; "Yeah, this is going to be neat. Hold still. Well, you can't not, can you—".
  otherwise: "Huh."; "Why am I here? I don't know you. Who even are—".

truth_reveal(store, pc_id) -> list[str]
  DEATH-10 The canonical account of the final scene and what led to it, shown only when asked for
  (GameService.on_death_reveal). At most 30 lines:
  - who was where: every body in the PC's place at its death and in the places a portal joins to
    it (positions), by their true names (actors.display_name; one of the dead is "one of the dead"),
    grouped by place: "In the Sales floor: Mara Voss, Alice Reyes, one of the dead.";
  - who decided what: the ACTION_START events of anyone but the PC in the death's turn and the one
    before, in order: f"{name}: {label}" + (f' — "{goal}"' when the payload has a goal), prefixed
    "You never saw it: " when the PC has no percept of that event.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..contracts.calls import RoastFacts
    from ..contracts.view import DeathView
    from ..kernel.store import Store

CAUSE_WORDS: dict[str, str] = {
    "blood_loss": "You bled to death.",
    "head_wound": "A wound to the head killed you.",
    "neck_wound": "A wound to the neck killed you.",
    "thirst": "Thirst killed you.",
    "hunger": "You starved to death.",
    "cold": "The cold killed you.",
    "heat": "The heat killed you.",
    "infection": "The infection killed you.",
    "offscreen": "You died.",
    "suicide": "You took your own life.",   # D-107 (physical.bodies DOOM-15)
}


def build_death_view(store: "Store", pc_id: str) -> "DeathView":
    raise NotImplementedError("P12")


def roast_facts(store: "Store", pc_id: str) -> "RoastFacts":
    raise NotImplementedError("P12")


def lifespan_words(ms: int) -> str:
    raise NotImplementedError("P12")


def roast_stored(store: "Store", pc_id: str) -> list[str] | None:
    raise NotImplementedError("P12")


async def roast(session) -> list[str]:
    raise NotImplementedError("P12")


def fallback_roast(facts: "RoastFacts") -> list[str]:
    raise NotImplementedError("P12")


def truth_reveal(store: "Store", pc_id: str) -> list[str]:
    raise NotImplementedError("P12")


from ._impl_death import (  # noqa
    build_death_view,
    fallback_roast,
    lifespan_words,
    roast,
    roast_facts,
    roast_stored,
    truth_reveal,
)
