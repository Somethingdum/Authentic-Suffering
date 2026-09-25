"""The guide: answers the player's Ask questions (P8). Rules PROTO-07, UI-SKULL-01, GUIDE-01..03.
docs/as/04_TURN_PIPELINE.md §1 (Ask is not a turn), docs/as/10_UI.md §2.5 (guide entries).

MUST NOT import kernel.truth. Everything the guide model is told about the character comes from the
PlayView the player is already looking at (built from the PC's own perception, UI-SKULL-01) and the
last narration they read; the rules it may explain come from GUIDE_TOPICS below.

GUIDE-01 Ask is not a turn: no event is committed, no time passes, nobody in the world hears it.
  The only writes are bookkeeping: the call in lm_calls and two story_log entries.
GUIDE-02 The guide knows only what the character knows (pc_facts) plus plain rules text
  (rules_for); it never sees the world's hidden state.
GUIDE-03 A failed call is not an error: the player gets GUIDE_DOWN and can ask again.

rules_for(question) -> list[str]
  words = the set of lowercase runs of letters a-z in the question. Every GUIDE_TOPICS entry with at
  least one keyword in ``words``, in table order, at most MAX_TOPICS; each contributes its text.
  None matched -> [GENERAL].
pc_facts(view, last_narration) -> list[str]   (in this order, then the first MAX_FACTS)
  f"Where you are: {place_name}" + f", {area_name}" when area_name is not empty, + '.';
  every location.description_lines entry, as is;
  f"You can see: {items}." when can_see is not empty — items = each thing's name, + f" ({detail})"
    when it has one, joined by ', ';
  per location.people chip: f"{label} is here" + f" ({status words joined by ', '})" when any + '.';
  per location.exits: f"Way out: {label}" + f" ({state words joined by ', '})" when any +
    f", leads to {leads_to}" unless leads_to is 'unknown' + '.';
  per location.dangers entry: f"Danger you know about: {text}.";
  per inventory.hands item: f"In your hands: {name}" + f" ({detail})" when it has one + '.';
  per body.wounds entry: f"Wound: {severity_word} {what} on the {where}, bleeding: {bleeding_word}"
    + ', treated' when treated + '.';
  per body.needs entry with level >= 2: f"{name}: {word}.";
  f"You feel {impairment_word}." unless it is 'clear-headed';
  f"Resolve: {cur} of {max} ({word}).";
  f"What just happened: {last_narration}" when last_narration is not None.
answer(session, question, view) -> str   (async)
  last = the text of the newest story_log entry of kind 'narration' (None when there is none);
  turn = world_clock.turn_index. ctx = GuideContext(question = question, pc_name = view.pc_name,
  pc_facts = pc_facts(view, last), rules_snippets = rules_for(question), cheat_query =
  cheats.commands.is_cheat_question(question) and meta cheat_active != '1' (P12, CHEAT-03: a
  question about cheats before activation gets the in-world deflection)). request =
  lanes.requests.build_request(session.config, CallClass.GUIDE, turn_index=None, context=ctx,
  ctx=ctx); response = await session.client.call(request) (no output model: the answer is prose).
  text = response.text stripped when parse_status is 'ok' and it is not empty, else GUIDE_DOWN.
  Then ONE store transaction: lanes.calllog.record(tx, request, response) (turn_index None is
  recorded as 0: a call outside any turn); service.session.append_story(tx, turn, 'player',
  question, 'ask'); append_story(tx, turn, 'guide', text). Returns text.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..contracts.view import PlayView
    from .session import Session

MAX_TOPICS = 3
MAX_FACTS = 30
GUIDE_DOWN = "The guide couldn't answer just now. Try again in a moment."

GENERAL = ("Use Do for actions (\"I check the back door\"), Say for words spoken aloud (choose who you are talking "
           "to), and Ask for questions like this one; Ask never costs time. Your character can only try what their "
           "body and training allow, and only knows what they saw, heard or were told.")

# (keywords, text). Plain rules summaries of docs/as/07_RULES.md for the guide model; never shown verbatim.
GUIDE_TOPICS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("roll", "rolls", "dice", "check", "checks", "chance", "chances", "odds", "succeed", "success", "fail",
      "failed", "failure", "skill", "skills"),
     "Every risky action is one roll of a ten-sided die against a target built from the character's ability, "
     "training, a fitting trait and the situation. There are four results: a clean success, a success with a "
     "cost, a failure, and a bad failure that adds a new problem. A failed roll never hurts by itself; what "
     "hurts is what the world does next."),
    (("bleed", "bleeding", "blood", "wound", "wounds", "wounded", "hurt", "injury", "injured", "bandage",
      "tourniquet", "heal", "healing", "medkit"),
     "There are no hit points. A wound bleeds at a rate set by how bad it is: a minor one clots on its own, a "
     "serious one needs help within about half an hour, a severe one within about ten minutes, a critical one "
     "within minutes. Pressure slows bleeding a lot, a bandage halves it, packing or a tourniquet on a limb "
     "nearly stops it. Wounds heal only after they are treated and days have passed."),
    (("die", "dies", "death", "dying", "dead", "kill", "killed"),
     "Every body dies the same way: too much blood lost, a critical wound to the head or neck, or too long "
     "without water or food. Heavy blood loss knocks a person out first. Death is never a dramatic choice; it "
     "is what the body's state adds up to."),
    (("hide", "hiding", "sneak", "sneaking", "stealth", "seen", "unseen", "notice", "noticed", "spotted"),
     "Hiding is a roll against the sharpest eyes watching. A great result means nobody notices anything; a "
     "middling one means someone senses movement and grows alert; a bad one means you are seen clearly. "
     "Darkness, cover and moving slowly help; noise and hurry hurt."),
    (("hear", "heard", "hearing", "sound", "sounds", "noise", "noisy", "loud", "quiet", "whisper", "listen"),
     "Sound is worked out for each listener: distance, walls, doors and background noise decide whether they "
     "hear the words, fragments, only a tone, or nothing. Someone who hears only part of what you said may "
     "understand it wrong. A gunshot carries far; a whisper can still be seen."),
    (("resolve", "nerve", "afraid", "fear", "scared", "panic", "brave", "courage"),
     "Resolve is the character's nerve. Frightening and painful things wear it down; at zero they can only "
     "flee, freeze, surrender or protect someone they love."),
    (("hunger", "hungry", "thirst", "thirsty", "water", "food", "eat", "eating", "drink", "drinking", "tired",
      "sleep", "sleeping", "fatigue"),
     "Thirst rises every twelve hours without water, hunger every three and a half days without food, "
     "tiredness every eight hours awake. From the middle stages on each one makes the character slower and "
     "clumsier; going far enough without water or food kills."),
    (("time", "turn", "turns", "wait", "waiting", "clock", "long", "seconds", "minutes"),
     "A turn is one decision, not a fixed slice of time. Talking takes real seconds, a search takes minutes, "
     "and waiting runs until something happens. Other people act at the same time, and they only know what "
     "they saw or heard."),
    (("save", "saves", "saving", "load", "loading", "ironman", "autosave"),
     "The game saves itself after every turn. In a normal run you can also keep named saves and load them; "
     "in an Ironman run there is only the automatic save, and death ends the run."),
)


def rules_for(question: str) -> list[str]:
    raise NotImplementedError("P8")


def pc_facts(view: "PlayView", last_narration: str | None) -> list[str]:
    raise NotImplementedError("P8")


async def answer(session: "Session", question: str, view: "PlayView") -> str:
    raise NotImplementedError("P8")
from ._impl_guide import rules_for, pc_facts, answer  # noqa
