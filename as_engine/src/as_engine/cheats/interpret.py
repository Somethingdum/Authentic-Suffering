"""Plain-words cheats (P12, D-103). Rules CHEAT-16..19. Owner 'cheats' (cheat_log); every change is an
event of the module that owns what it writes, origin 'cheat', as in cheats.commands.

The owner: "The whole schtick with cheats in the Narrative game is that you can do ANYTHING ... if I
have to type out structured cheat commands, there will be issues. I want to be able to say 'Make that
infected jig joyously' and have it happen." The Play input is at most Act / Say / Cheat
(service.game_service on_turn_compose); the Cheat field exists only while meta cheat_active is '1'
(CHEATS §2: before the word nothing admits there is anything to cheat with). A Cheat line that starts
with '/' is still a slash command (cheats.commands.parse); anything else comes here.

scene(tx, session) -> CheatScene   (CHEAT-16: who and what "that", "him", "the door" mean)
  Handles, from the PC's side of the glass (the console may name what the PC can name, and what
  the PC can see):
  me = 'P0' (the PC: its display name, kind, where 'L0'). here = 'L0' (the PC's place: name, kind).
  people: 'P1', 'P2', … — every other body the PC sees now (mind.optics.visibility != 'none', alive
    or not, the infected included), then every actor the PC knows by name (acquaintance) that is
    elsewhere; each {handle, label = perception.word_for(the PC, it) (a known name, or how it looks:
    'a shambler', 'a tall woman'), kind (human | infected | animal | lurker), where (its place's
    handle, '' when unknown), note: 'looking at' for the PC's attention target — none: the nearest
    body it sees — 'last named' for the first body the previous plain-words cheat named, 'dead' for
    a dead one, joined by ', '}; ordered: seen ones by distance, then known ones by name.
  places: 'L0', then the places a portal joins to here, then the PC's known_places, by place_id:
    {handle, label = name, kind}.
  doors: 'D1', … the portals of here, by portal_id: {handle, label = name, kind, note = 'open' |
    'closed' | 'locked' | 'barricaded' | 'broken'}.
  items: 'I1', … the items the PC holds or carries, then the items lying here, by item_id: {handle,
    label = the def name}.
  groups: 'G1', … every group, by group_id: {handle, label = name}.
  makeable: every canon item name (sorted); spawnable: every actor and pc record name of the run's
  canon and the cheat_ packs (content.pack.cheat_records), then every infected type name, sorted;
  strains: the canon pathway ids; weather: cheats.commands.WEATHER_KINDS.
  willis: the PC is in the reality exception (physical.bodies.excepted).

async interpret(session, tx, text, seen) -> CheatPlan | CheatParseError
  One CHEAT_INTERPRET call (lane A; lanes.requests.build_request(config, CHEAT_INTERPRET,
  turn_index = T, actor_id = None, context = ctx = CheatInterpretContext(request = text, scene = seen),
  json_schema = lanes.schemas.to_lm_schema(CheatPlan)), output CheatPlan), recorded with
  lanes.calllog.record. parse_status != 'ok' -> CheatParseError("That didn't come through, Boss. Say
  it another way."). The prompt (prompts/cheat_interpret.*.j2) lists OP_DOCS and the scene.

async run(session, text) -> CheatResult   (CHEAT-17..19)
  In ONE store transaction: scene; plan = interpret. plan.clarify -> CheatResult(False, clarify)
  and nothing is written (the Boss is asked which one; nothing guessed). No ops -> CheatResult(False,
  "Nothing to do there, Boss."). Every op is checked before any runs (CHEAT-17): its op name is in
  OPS, every handle it names is one of the scene's of the right kind (who: P; to: L or P; target: the
  kinds OP_DOCS allows), an item / being name is in makeable / spawnable (case-insensitive; else the
  nearest by difflib at cutoff 0.8), numbers inside OP_DOCS' ranges. A bad op -> CheatResult(False,
  f"I got tangled up at step {i}, Boss: {why}.") and nothing runs. Then each op in order, through
  the same effect the matching slash command has (cheats.commands handlers, ids passed directly)
  or the ops below; an op that turns out impossible after others ran rolls the whole plan back
  (the '_Refuse' of cheats.commands) and says why. A plan that ran: one cheat_log row {command =
  the text as typed, outcome = the outcomes of the ops joined by '; ', persona_line} and the
  Sandbox mark (as cheats.commands.execute); the persona line (cheats.commands.persona with the
  command name 'plain'); detail = one plain line per op of what happened and to whom, named as the
  PC would name them ("The shambler by the door jigs joyously for ten minutes."), and, for every
  'show' op, " (a show: the world has no way to do more than let it be seen)" (CHEAT-18: what the
  simulation cannot hold is shown and remembered, and said to be a show — never faked into rules
  that do not exist, never silently dropped). meta 'cheat_last_named' = the body the plan named
  first (for 'him', 'that one' next time).

OPS (the closed vocabulary; OP_DOCS is the text the prompt shows; handles as above; 'me' = P0):
  teleport who -> to (L: its first anchor, else its centre; P: beside that body) — anyone, nobody
      sees them go or arrive (physical.space: DEMATERIALIZE, then a MOVE from nowhere).
  give     item (makeable) x n (1..999, default 1) to who (default me) — as /give.
  make     item x n lying at to (an L, default here) — physical.objects.create into the place.
  destroy  target (an I) — physical.objects.destroy.
  spawn    item (spawnable) x n (1..20) at to (L or P, default beside me); state 'ally' for an ally —
      as /spawn (a place other than here: at that place's first anchor).
  despawn  target (a P made by a cheat) — as /despawn.
  kill / revive / heal  who — as /kill, /revive, /heal.
  hurt     who, state = severity (minor | significant | severe | catastrophic; default severe) — a
      blunt wound through physical.bodies.apply_harm at an anatomy drawn from CENTRE_MASS.
  god      who, state on | off — as /god.
  set      who, stat (a SPECIAL letter, 'resolve' or a skill domain), n — as /set.
  time     n hours (1..720) — as /time.       weather  state (a weather kind) — as /weather.
  noise    n dB (40..180) at to (an L, default here) — as /noise.
  will     who, text (what they now want) — as /will.
  forget   who, target (a P or an L) — as /forget.
  brief    who — as /brief.
  believe  who, text (what they now believe), target (optional: the P or L it is about) — one belief
      through perception.grant (event = a CHEAT_OVERRIDE, VISUAL, EXACT, 'You simply know it.',
      confidence 3, beliefs = [(about, text)], provenance 'cheat') — the ordinary door (CHEAT-06).
  feel     who toward target (a P), stat = an axis (trust, fear, respect, affection, resentment,
      obligation), n = the change (-6..6) — mind.mind.relate.
  rep      target (a G), n (-5..5) — as /rep.
  infect   who, state = strain (default 'wet') — as /infect.     cure  who — as /cure.
  horde    n (1..500) at to (an L, default here) — as /horde.     mega — as /mega.
  force    who (any body: a person, one of the dead, an animal; never the PC), text = what they do,
      as they would be seen doing it ('jigs joyously'), n = minutes (1..600, default 10) —
      physical.bodies.force_act: until then that body does exactly that and nothing else (CHEAT-19).
  reshape  target (an L), text = its new name (optional), state = lit | dark (optional) —
      physical.space.change_place (reason 'cheat').
  door     target (a D), state = open | closed | locked | unlocked | barricaded | unbarricaded |
      broken — physical.space.portal_change_event.
  blast    at to (an L, a P or a D), size small | large | huge (default large) — physical.bodies.blast.
  show     text — anything the world has no rules for, said the way anyone there would see it
      ("confetti pours out of the ceiling"): queued (meta 'pending_shows', a JSON list) and, as the
      next turn opens, turned into what everyone in the PC's place sees (take_shows); with willis,
      his own act instead (cheats.commands /wonder's take_wonder). CHEAT-18.
  census / reveal — as /census, /reveal (detail only); mind  who — as /mind (detail only; CHEAT-06).

take_shows(tx, pc_id, turn_index, at) -> list[str]   (turn.pipeline S0, after take_wonder)
  meta 'pending_shows' empty -> []. Else, per text in order: a CHEAT_OVERRIDE (writer 'cheats',
  payload {show: text}) and, for every conscious body in the PC's place and the PC itself (by
  body_id), perception.grant(VISUAL, EXACT, text capitalised with a full stop, source None,
  detail {show: true}) — seen by everyone there, remembered, and in the narrator's packet as the
  PC's percept; then meta 'pending_shows' = '[]'. Returns the percept ids.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..contracts.calls import CheatScene
    from ..contracts.mind import CheatPlan
    from .commands import CheatParseError, CheatResult

OPS: tuple[str, ...] = (
    "teleport", "give", "make", "destroy", "spawn", "despawn", "kill", "revive", "heal", "hurt", "god", "set",
    "time", "weather", "noise", "will", "forget", "brief", "believe", "feel", "rep", "infect", "cure", "horde",
    "mega", "force", "reshape", "door", "blast", "show", "census", "reveal", "mind",
)

OP_DOCS = """\
teleport: who -> to (a place L# or a person P#). Anyone, instantly; nobody sees them go.
give: item (a makeable name), n (how many), who (who gets it; default P0).
make: item, n, to (a place L#; default L0) — it lies there.
destroy: target (an item I#).
spawn: item (a spawnable name), n (1-20), to (L# or P#; default beside P0), state 'ally' to make them loyal.
despawn: target (a P# made by a cheat).
kill | revive | heal: who.
hurt: who, state = minor | significant | severe | catastrophic.
god: who, state = on | off.
set: who, stat (S P E C I A L, resolve, or a skill), n.
time: n hours.   weather: state (a weather kind).   noise: n decibels, to (L#).
will: who, text = what they now want.   forget: who, target (P# or L#).   brief: who.
believe: who, text = what they now believe, target (optional P# or L# it is about).
feel: who, target (P#), stat = trust | fear | respect | affection | resentment | obligation, n = change (-6..6).
rep: target (G#), n (-5..5).   infect: who, state = strain.   cure: who.
horde: n, to (L#).   mega.
force: who (any body but P0: a person, one of the dead, an animal), text = what they do, as seen ('jigs joyously'), n = minutes.
reshape: target (L#), text = new name (optional), state = lit | dark (optional).
door: target (D#), state = open | closed | locked | unlocked | barricaded | unbarricaded | broken.
blast: to (L#, P# or D#), size = small | large | huge.
show: text = anything else, said as anyone there would see it happen ('confetti pours out of the ceiling').
census | reveal: nothing else.   mind: who.
"""


def scene(tx, session) -> "CheatScene":
    raise NotImplementedError("P12")


async def interpret(session, tx, text: str, seen: "CheatScene") -> "CheatPlan | CheatParseError":
    raise NotImplementedError("P12")


async def run(session, text: str) -> "CheatResult":
    raise NotImplementedError("P12")


def take_shows(tx, pc_id: str, turn_index: int, at: int) -> list[str]:
    raise NotImplementedError("P12")


from ._impl_interpret import interpret, run, scene, take_shows  # noqa
