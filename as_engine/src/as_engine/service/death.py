"""Death screen, Willis at every death, and the post-death truth reveal (P12; D-105). May import
kernel.truth ONLY for the reveal, which is shown after the player explicitly clicks 'Show me
everything' (DEATH-10).

The owner: "When you die, regardless of Wildcard activation, you see Willis. He mocks and roasts you
joyously over your mistakes." Rules DEATH-10..14.

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
  - willis = roast_stored(store, pc_id) or []; willis_pending = nothing is stored yet;
  - can_new_life_here = can_load = the run is not Ironman (meta settings_json save_mode);
    world_id = meta world_id.

roast_facts(store, pc_id) -> RoastFacts
  DEATH-12 What Willis has to work with — the dead person's own record only (never kernel.truth:
  the world's secrets wait for 'Show me everything', DEATH-10). This life began at the first
  PLAYER_INPUT after the PC's latest PC_CONTROL_CHANGE (payload pc_actor_id = pc_id), else at the
  first PLAYER_INPUT:
  pc_name; lived = lifespan_words(death at - that start); turns = the PLAYER_INPUT events from that
  start to the death; cause_text and choices = build_death_view's cause_text and contributing;
  typed = the raw_text of the player's last 5 'do' / 'say' player_inputs from that start, oldest
  first; bent_rules = meta sandbox '1'; ironman; rises = the DEATH payload carries rise_pending;
  met_him = the PC has an acquaintance row for a body in the reality exception
  (physical.bodies.excepted); by_his_hand = a body in the reality exception is the actor of an event
  on the cause chain (as walked for contributing).

lifespan_words(ms) -> str
  < 1 hour: mind.affordance.duration_words(ms / 1000); < 2 days: f"{hours} hours" (rounded, at least
  1: "1 hour"); else f"{days} days" (rounded down).

roast_stored(store, pc_id) -> list[str] | None
  The stored roast: the story_log texts of kind 'willis' at the turn of the PC's death, in order;
  None when there are none.

async roast(session) -> list[str]
  DEATH-13 Willis at every death of the PC — regardless of the Wild Card, the console, the
  difficulty or Ironman. A stored roast is returned as it is (no call). Otherwise ONE WILLIS_ROAST
  call (lane A; lanes.requests.build_request(config, WILLIS_ROAST, turn_index = the current turn,
  context = ctx = WillisRoastContext(facts = roast_facts(store, session.pc_id)), json_schema =
  lanes.schemas.to_lm_schema(WillisRoast)), recorded with lanes.calllog.record; lines = the output's
  lines, each stripped and cut to 300 characters, empty ones dropped. ANY failure of the call (the
  lane down, a timeout, an unparseable or empty answer, an exception from the transport) ->
  fallback_roast(facts): the death screen never waits on a model that is not there. The lines are
  stored in the story (service.session.append_story, kind 'willis', turn_index = the death's turn;
  story_log is outside both state hashes, so a replay is unaffected) and returned.

fallback_roast(facts) -> list[str]
  DEATH-14 Willis without a model, built from the facts only, in this order:
  "Ha! Oh, that was beautiful. Do it again."; with typed: the last one in double quotes, then " —
  that's what you went with. Incredible."; the first sentence of cause_text, then " I've watched
  mayflies plan better.";
  by_his_hand -> "And yes, that was me. You had it coming, and I had a free minute."; bent_rules ->
  "You bent the rules of reality and STILL managed this. I'm genuinely impressed."; rises -> "Don't
  worry, you'll be back on your feet in a few hours. Just not as you."; last, ironman -> "Anyway.
  Coffee's getting cold. That was your only one, by the way." else "Anyway. Coffee's getting cold.
  Go on, try again. I'll be watching." At most 6 lines (the ones after the third are dropped first,
  never the last).

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
