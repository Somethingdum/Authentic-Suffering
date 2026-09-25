"""The Doom scene, Willis in the frozen moment, and the Voice (P12; D-106). The owner's words are
kept whole in docs/as/sources/THE_VOICE.md. Rules VOICE-01..09.

Canon (never on any screen, never in any prompt, never in the world): the Voice is Codex, the god
above all gods, above Willis — the creator that has designed every facet of every life since the
atoms, and got sick of its creation the way an architect gets sick of a building he has built
eleven trillion times. Its genius and its one limit: it cannot just place things. Everything has to
have a cause. So every death is a plan that has been cascading for ages, and the further it
cascades the more pleased it is with itself. It never intervenes; it gives you the upper hand, and
you die anyway. In the game it has no name.

When a person's death becomes certain (physical.bodies DOOM-01..04) the world stops for them — an
outside-of-body moment that takes no time at all. For the player's character it plays as the Doom
scene, in the story just before that moment's narration (turn.pipeline, VOICE-07):

VOICE-01 scene(store, pc_id, willis_lines, voice_paragraphs) -> list[DoomBeat], in this order:
  1. 'scene' FREEZE_TEXT (+ ' ' + FIGHT_TEXT when the PC holds a grip on a body or a body holds one
     on it: grips), pause 0;
  2. 'scene' DARK_TEXT, pause DARK_PAUSE_MS (about three seconds, the owner's);
  3. 'scene' STEPS_TEXT, pause 1500;
  4. 'willis' one beat per line of willis_lines, pause 900 each;
  5. 'snatch' SNATCH_TEXT, pause SNATCH_PAUSE_MS (a quarter of a second);
  6. 'scene' ALONE_TEXT, pause 2000;
  7. 'voice' one beat per paragraph of voice_paragraphs, pause 1200 each;
  8. 'scene' RESUME_TEXT (the doom kind 'instant': RESUME_INSTANT_TEXT), pause 1500.

VOICE-02 Willis in the frozen moment: service.death.roast (DEATH-13) — who he is to them decides
  what he says: in his debt (the console used this life, the PC not Willis) he mocks them twice as
  hard; met him before: "oh, it's you from earlier"; never met: "why am I here? I don't know you."
  He is cut off mid-sentence: the thing takes him.

voice_facts(store, pc_id, moment) -> VoiceFacts
  VOICE-03 Everything the Voice brags with, from the record. doom = physical.bodies.doomed(store,
  pc_id) (ValueError f"no doom for {pc_id}" when there is none):
  - pc_name = the PC's actors.display_name; lived = service.death.lifespan_words(doomed_at - the
    life's start as service.death.roast_facts finds it);
  - seconds_left: 'before' -> max(0, (expected_at - doomed_at) // 1000); 'after' -> 0;
  - chain = chain_beats(store, pc_id, doom);
  - threat, threat_near (VOICE-04); upper_hand (VOICE-05);
  - manner: 'after' only — service.death.build_death_view(...).cause_text; 'before' None: the Voice
    never says how;
  - said_before: 'after' only — the story's 'voice' texts of the scene's turn (scene_turn), in
    order, at most 3.

scene_turn(store, pc_id) -> int | None
  The turn whose story holds the PC's Doom scene: the lowest turn_index of a story_log row of kind
  'doom' at or after the doom's turn_index; None when the PC has no doom or its scene has not played.

chain_beats(store, pc_id, doom) -> list[ChainBeat]
  VOICE-04 The chain, oldest first, at most 24 beats: the events reached walking back from the
  doom's cause_event (cause_event_id and links, breadth first, at most 300 events), and the PC's
  own last 5 ACTION_STARTs before the doom, in seq order; when = f"day {world_time(at).day},
  {format_clock(at)}":
  - an ACTION_START of the PC -> 'choice', text = its label, said = the raw_text of that turn's
    player_inputs row when its mode is 'do' or 'say';
  - a DEATH or HARM of anyone but the PC -> 'consequence': f"{name} died" / f"{name} was hurt";
  - any other event on the chain the PC has no percept of -> 'unseen', text = describe(event);
  - a percept of the PC's, with no source it could tell (source_id NULL), of an event on the chain
    -> 'clue', text = the percept's text.
  Names are the true ones (service.death's: actors.display_name, else "one of the dead").
  threat = the name of the actor of the first event on the chain (walk order) that is not the PC,
  or None; threat_near = service.death.lifespan_words(doomed_at - since) where since = the time
  that actor last came into the building the PC is in (the top of the PC's place's parent_id
  chain) — the latest of its MOVE / MATERIALIZE events into a place outside that building
  (else its first event) — and the PC was in it too (the later of the two); None when the actor is
  not in that building.
VOICE-05 upper_hand: the names of the weapons the PC holds or carries (canon firearm or melee), then
  the known names of the living people in its place whom it knows by name (not the threat); at
  most 8.

async voice(session, moment) -> list[str]
  VOICE-06 ONE THE_VOICE call (lane A; lanes.requests.build_request(config, THE_VOICE, turn_index =
  the current turn, actor_id = None, context = ctx = VoiceContext(moment, voice_facts(store, pc_id,
  moment)), json_schema = lanes.schemas.to_lm_schema(VoiceMessage))); paragraphs = the output's,
  each stripped and cut to 2000 characters, empty ones dropped. ANY failure of the call ->
  fallback_voice(moment, facts). Nothing is stored or recorded here (the callers do: the pipeline
  records every call of its turn; GameService.on_death records its own).

fallback_voice(moment, facts) -> list[str]
  VOICE-08 The Voice without a model, from the facts only. 'before': three paragraphs — ARCHITECT;
  the chain walked, each text without its closing . ! ? ("{when}: you chose to {text}" + (,
  thinking "{said}") / "{when}: {text}." / "{when}: {text}. You never saw it." / 'There was
  "{text}". You noticed it. You did nothing.'), the last 8 beats, then "I didn't have to touch you once." + (the upper hand: "I gave you {a, b and
  c}.") + " And still."; then the threat ("Did you know {threat} has been in here with you? For
  {threat_near}. You never noticed.") when there is one, then f"In {when_words(seconds_left)}
  you are going to die. I won't tell you how. You should have paid more attention. Like I did."
  'after': one paragraph: f"And that is how. {manner} Every piece had a cause. Every piece was mine."
when_words(seconds) -> str: 0 -> 'this very instant'; < 10 -> 'a few seconds'; < 90 -> f'about
  {s} seconds'; < 5400 -> f'about {round(s / 60)} minutes' ('about a minute' for 1); else f'about
  {round(s / 3600)} hours'.

async doom_scene(session) -> list[DoomBeat]
  VOICE-07 For the first turn that ends with the PC doomed and its scene not yet played (scene_turn
  None) — the turn in which it was doomed, or, for a doom made between turns (the console), the
  next one (turn.pipeline, after the commit, before the narration): lines = await
  service.death.roast(session) (Willis), paragraphs = await voice(session, 'before'); ->
  scene(store, pc_id, lines, paragraphs). Any exception from the scene costs only the scene: no
  beats, and the pipeline logs a repair (kind 'degraded', stage 13, rule 'VOICE-07', detail
  {error}) with the story. The pipeline stores the
  beats in the story just before the narration — 'willis' beats as kind 'willis', 'voice' beats
  as kind 'voice', the rest as kind 'doom' — and returns them (TurnOutcome.doom) for the service to
  push (doom {beats}) before the turn's result.

VOICE-09 After the death (GameService.on_death): voice(session, 'after'), stored as kind
  'voice_after' at the death's turn; the death screen shows Willis's lines and the Voice's words,
  before and after (service.death.build_death_view).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..contracts.calls import ChainBeat, VoiceFacts
    from ..contracts.protocol import DoomBeat
    from ..kernel.store import Store

FREEZE_TEXT = ("Everything stops. The dust hangs in the air. The air itself has stopped moving; somewhere under you the "
               "planet has stopped turning. You can still move, but not here. Not in your body.")
FIGHT_TEXT = "The thing you were fighting is stopped mid-motion, close enough to touch."
DARK_TEXT = ("Then the lights go out. Lights that weren't even there. The sun goes out. Everything is black but the "
             "faintest glow of the room you're in.")
STEPS_TEXT = "Something is walking toward you."
SNATCH_TEXT = ("Something huge and jointed takes him out of the dark. A quarter of a second, if that: something like a "
               "mantis. A crack, like a shell giving way.")
ALONE_TEXT = "Then nothing. There is nothing. It is just you."
RESUME_TEXT = "Then the dust moves again. You are screaming."
RESUME_INSTANT_TEXT = "Then the dust moves again."
DARK_PAUSE_MS = 3000
SNATCH_PAUSE_MS = 250
ARCHITECT = ("You want to know why. Everyone does. Imagine you are the best there ever was at one thing, and it is all "
             "you do. Say you build. You build the same building eleven trillion times, so you build a new one, and a new "
             "one, until you have built every building that could ever be, a few times over. And then the sight of it "
             "makes you ill. All you want is to knock it down. So: dominoes. The most fun game of dominoes there ever was. "
             "Until my next game, when there's none of you left.")


def scene(store: "Store", pc_id: str, willis_lines: list[str], voice_paragraphs: list[str]) -> list["DoomBeat"]:
    raise NotImplementedError("P12")


def voice_facts(store: "Store", pc_id: str, moment: str) -> "VoiceFacts":
    raise NotImplementedError("P12")


def chain_beats(store: "Store", pc_id: str, doom: dict) -> list["ChainBeat"]:
    raise NotImplementedError("P12")


async def voice(session, moment: str) -> list[str]:
    raise NotImplementedError("P12")


def fallback_voice(moment: str, facts: "VoiceFacts") -> list[str]:
    raise NotImplementedError("P12")


def when_words(seconds: int) -> str:
    raise NotImplementedError("P12")


def scene_turn(store: "Store", pc_id: str) -> int | None:
    raise NotImplementedError("P12")


async def doom_scene(session) -> list["DoomBeat"]:
    raise NotImplementedError("P12")


from ._impl_voice import (  # noqa
    chain_beats,
    doom_scene,
    fallback_voice,
    scene,
    scene_turn,
    voice,
    voice_facts,
    when_words,
)
