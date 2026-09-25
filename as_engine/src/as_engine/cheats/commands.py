"""Cheat activation, parsing and execution (P12). Rules CHEAT-01..15. Owner 'cheats' (cheat_log).
docs/as/CHEATS.md is the bonus document (voice, examples); this docstring is the machine contract.
Every state change is an event with origin 'cheat' of type CHEAT_OVERRIDE whose writer is the
module that owns what it writes (bodies -> 'physical.bodies', positions -> 'physical.space', meta
-> 'kernel.meta', world_clock -> 'kernel.clock', actors / dossier_deltas -> 'mind.actor',
group_standing -> 'society.group', cheat_log -> 'cheats'), unless a named owner function does it.
Commands run between turns in ONE store transaction of their own: at = world_clock.now_ms, T =
world_clock.turn_index; no world time passes (except /time) and nobody perceives a command
(CHEAT_OVERRIDE is not a sensory type); people meet the resulting state at the next turn.

detect_activation(text) -> bool   (CHEAT-01, implemented): the standalone token 2508.
activate(session) -> CheatResult   (CHEAT-01)
  The line that held the token is consumed (no turn is played). When meta cheat_active != '1':
  CHEAT_ACTIVATED (writer 'kernel.meta', origin 'cheat', payload {}) setting it to '1'. Either way
  the story gets a 'notice' entry SHIMMER_NOTICE and a 'cheat' entry ACTIVATION_LINE (service.
  session.append_story, turn_index T). Returns CheatResult(True, ACTIVATION_LINE, SHIMMER_NOTICE,
  [the event id, when one was made]). Activation alone does not mark the run Sandbox.

parse(text) -> CheatCommand | CheatParseError   (only for a line that starts with '/' while
  cheat_active is '1'). Tokens: TOKEN_RE over the text after '/' — a "double-quoted" run is one
  token (quotes dropped), anything else splits at whitespace. The first token, lowercased, is the
  command; not in USAGE -> CheatParseError("No lever called '<word>', Boss. Try /help."); nothing
  after the slash -> CheatParseError('Say the word, Boss — a command after the slash. Try
  /help.'). Arguments that do not fit -> CheatParseError(f"That's not how /{name} works, Boss:
  {USAGE[name]}."). args by command (names are joined with single spaces when unquoted):
    help, off, reveal: {} (anything after is ignored)
    give <item> [<qty 1..999>] [to <person>]: {item, qty?, person?}
    heal [<person>]: {person?}          god on|off [<person>]: {on: bool, person?}
    tp <place>: {place}                 time +<n>h (n 1..720): {hours}
    set <stat> <value> [<person>]: {stat, value, person?} — stat a SPECIAL letter (uppercased;
      value 1..10), 'resolve' (0..99) or a SKILL_DOMAINS value (0..3)
    weather <kind in WEATHER_KINDS>: {kind}    rep <group> <-5..5>: {group, value}
    spawn <what> [x<n 1..20>] [ally] (in any order after what): {what, n (1), ally (False)}
    despawn <person or item>: {target}; kill / revive / mind / brief <person>: {person}
    noise <db 40..180> [here | at <anchor>]: {db, anchor?}
    wonder <what he does> (one quoted token or the rest of the line): {what}
  CheatCommand(name, args, raw = the stripped text).

resolve(tx, pc_id, kind, name) -> (id, None) | (None, persona line)   (§4 Names)
  kind 'person': 'me' / 'myself' / 'self' -> the PC; else first the PC's acquaintance rows
  (known_name, then description), then every actors row (display_name, then its first word);
  'place': the PC's known_places, then every place; 'group': every group; 'item_def': canon items
  by ref, bare id, name and plural; 'item': the world's items by their def's name. Within each
  tier: an exact case-insensitive key naming one id wins; several ids -> ambiguous; else
  difflib.get_close_matches(cutoff 0.8) over the tier's keys, one id -> it. The first tier that
  names exactly one id wins. Ambiguous -> f"Too many of those, Boss: {up to five names}. Be
  specific."; nothing -> f"Never heard of {anyone | anywhere | any group | any such thing} called
  '{name}', Boss."

async execute(session, command) -> CheatResult   (CHEAT-04..08)
  help -> the persona line (below) and detail HELP_TEXT; a story 'cheat' entry; nothing else.
  Every other command runs its effect; an effect that cannot happen returns (False, a persona line
  — resolve's, or the command's own below) and changes nothing: no log, no sandbox. A command that
  happened: persona line; unless in SANDBOX_EXEMPT, a CHEAT_OVERRIDE (writer 'cheats', payload
  {command, raw, outcome} + reconciliation: true for /despawn) inserting cheat_log {entry_id
  (kind 'cht'), turn_index T, command = raw, outcome, persona_line, event_id = the first effect
  event's id or None}, and — when meta sandbox != '1' — CHEAT_OVERRIDE (writer 'kernel.meta',
  payload {sandbox: true}) setting it to '1' for good. Story: a 'cheat' entry raw + '\n' + the
  line (never /reveal's or /mind's detail: CHEAT-06). Returns CheatResult(True, line, detail or
  outcome, the effect event ids).
  give: the item def (resolve 'item_def') to the person (default the PC): physical.objects.create
    (origin 'cheat', event_origin 'cheat') into holder slot 'pack' — one row of qty when it
    stacks (or qty is 1), else qty rows of 1. Outcome f"gave {qty} {plural or name} to {name}".
  heal: a living body -> CHEAT_OVERRIDE (physical.bodies): every unhealed wound healed_at = at and
    clotted 1; blood_loss_pct 0, pain 0, impairment 0 (awareness 'awake', posture 'standing'
    when it was 'unconscious'); its needs row (if any) all stages 0, last drink / meal / sleep =
    at, chill 0. A dead body -> "They're past a bandage, Boss. Try /revive."
  god: meta 'god_bodies' (a JSON list, sorted) gains or loses the body (UPSERT, kernel.meta).
    physical.bodies.apply_harm then gives that body no wound (L12: per body).
  tp: the PC's positions row -> the place, its first anchor by anchor_id (its point) or, with
    none, the place's centre; since_ms = at, hidden 0 (physical.space; not a MOVE: no one sees it).
  set: a letter -> bodies.special[letter] (physical.bodies) and, for an actor, a dossier_deltas
    'set' of capability.special.<letter> (mind.actor); 'resolve' -> actors.resolve_cur =
    clamp(value, 0, resolve_max); a skill -> a dossier_deltas 'set' of capability.skills: the
    list without that domain, plus {domain, rank = value, evidence 'The Boss said so, and so it
    was.'} when value > 0, sorted by domain. No actor for resolve or a skill -> f"{name} has no
    mind to set that in, Boss."
  time: turn.timers.run_offscreen(tx, session.rng, at + hours h, T) — the world keeps living.
  weather: world_clock weather = kind, wind_level 2 for 'wind', 3 for 'storm', else 0.
  rep: group_standing {group, the PC} UPSERT standing = value, reasons [].
  spawn: RETIRED_SPAWNS[what] -> that line and nothing else (ok, not logged). A type word (shambler,
    crawler, runner, lurker: a canon 'infected' record whose name, lowercased, is the word — else
    whose id holds the word in capitals, ZOMBIE_ARCHETYPE_SHAMBLER01) -> n x
    world.infected.spawn(tx, rng, the PC's place, that type's id, at, T, None, origin 'cheat',
    x = min(width, PC x + 1 + 0.5 i), y = the PC's y). Else a dossier: a full ref or bare id among
    the run's actor / pc records, then among the cheat_ packs under config.content_dir
    (content.pack.load_pack; CHEAT-10: nothing else reads them). None -> "Never heard of anyone or
    anything called '<what>', Boss." A dossier of someone under 18 carrying any
    content.safety.unsafe_terms word -> refused: "No. Not that, not ever, Boss.", a cheat_log row
    (outcome 'refused: the hard line', payload refused: true), no sandbox (CHEAT-08). Otherwise n
    times: physical.bodies.create (kind 'lurker' when the dossier's tags hold 'lurker', else
    'human'; origin 'cheat'; its looks), physical.space.place_body at the PC's place and anchor, x
    as above, the outfit created worn (origin 'cheat'), mind.actor.create(..., source 'cheat',
    content_ref, event_origin 'cheat'), actors quarantine = 1 and accepted_authority = [the PC]
    for 'ally' else [] (CHEAT_OVERRIDE, mind.actor), and a known_places row for where it stands.
    (D-102) A dossier whose capability.tags hold 'reality_exception' (Willis) -> physical.bodies.
    grant_exception(tx, body, at, T, origin 'cheat'); one whose tags hold 'fickle' ->
    mind.mind.add_fickle(tx, body, at, T, origin 'cheat') (REL-06). A dossier tagged 'cheat_companion'
    (Fredrick) while the PC is in the reality exception (a life as Willis: D-79, "Fredrick blends
    in whenever Willis is blending in") -> blends in: every holder of an acquaintance row toward
    the PC (by holder_id) gets one toward it (PERCEIVE, writer 'mind.perception', origin 'cheat':
    known_name = its display name, description = mind.perception.describe_dossier of its dossier,
    first_met = last_seen = at, last_seen_place = the PC's place) and, when the holder has a
    relationships row toward the PC, the same six axes toward it (RELATION_CHANGE, writer
    'mind.mind', origin 'cheat', kind 'acquaintance', updated_at = at); and it joins every group
    the PC is a member of (group_members {group_id, actor_id, role 'member', standing 0, since at,
    status 'member'}, CHEAT_OVERRIDE writer 'society.group').
  despawn: a person whose body has origin 'cheat' -> bodies alive 0, dead_at = at, awareness
    'dead', posture 'lying' (physical.bodies) and its positions row deleted (physical.space): gone
    from the world; an item of origin 'cheat' -> physical.objects.destroy. Anything else -> "Only
    what I made, Boss. That one was here before me."
  kill: a living body -> physical.bodies.kill(tx, body, 'cheat', at, T, rng) (DEATH, cause
    'cheat'); dead already -> 'Already dead, Boss. Thorough, though.'; a body in the reality
    exception (physical.bodies.excepted, D-102) -> "Reality lost that argument a long time ago, Boss."
  revive: a dead human, lurker or animal body -> the heal writes plus alive 1, dead_at /
    death_event / false_dead_until NULL, awareness 'awake', posture 'standing'; its pending
    REANIMATION timers cancelled (kernel.clock.cancel, reason 'revived'); its infections stay
    exactly as they were — nothing cures (CMG §42.2). Alive -> "They're still breathing, Boss.";
    an infected body -> "That one's past saving, Boss."
  reveal: detail = one line per place — the PC's, then the places a portal joins it to (sorted):
    f"{place}: " + '; '.join(each living body there but the PC, by body_id: its display name (or
    'one of the dead' / its kind), ' — ' + current_task or goal_text when there is one, and ' (holding
    …)' with the names of what is in its hands) or 'nobody'. Text only (CHEAT-06).
  mind: an actor -> detail lines 'Goal: …', 'Plan: goal — steps' (plans row), 'Believes: ' the five
    believed, live holdings by (confidence desc, acquired_at desc), 'On their mind: ' five open
    loops by (strength desc, created_at desc), 'Last reason: ' the private_reason of its latest
    ACTION_START. Text only (CHEAT-06).
  brief: a living actor -> CHEAT_OVERRIDE (writer 'cheats', no writes) and perception.grant(tx,
    it, event_id = that event, VISUAL, EXACT, 'You simply know how things stand here.', None, at,
    T, confidence 3, beliefs = brief_beliefs(tx, it, the PC's place), detail {cheat: true},
    provenance 'cheat') — the ordinary door, on the record (CHEAT-06: the one command that writes
    a mind).
  noise: a NOISE (writer 'action.propagate', origin 'cheat', place_id) {source_db: db, kind
    'noise', text 'a loud noise' (db >= 100) or 'a noise', place_id, x_m, y_m of the PC — or of the
    anchor of its place named by 'at' (resolved like a name)}.
  off: CHEAT_DEACTIVATED (writer 'kernel.meta') setting cheat_active '0'; the line is
    DEACTIVATION_LINE; the Sandbox mark stays.
  The owner's additions (P12b; D-78, docs/as/CHEATS.md §3a). A command found impossible after it
  wrote something raises inside the transaction: everything is rolled back and the line says why.
  will <person> "<want>": never the PC ("That one's yours already, Boss."), a living actor ->
    CHEAT_OVERRIDE (mind.actor) setting actors.goal_text = want and UPSERTing plans {goal_text: want,
    steps [], standing_orders [], updated_at}; its open 'goal' / 'plan' loops close 'abandoned'
    (mind.mind.close_loop); a new open loop 'goal' f"I want: {want}" strength 3 (mind.mind.open_loop)
    — it wants it now, as its own. Others notice only what it then does.
    parse: {person: the first token, want: the rest}.
  forget <person> about <person or place>: a living actor forgets someone or somewhere (the subject
    resolves as a person, else as a place): a CHEAT_OVERRIDE (writer 'cheats') cause; its episodes
    not yet quarantined whose subject_ids hold the subject or whose place is it -> quarantined 1
    (mind.memory: kept as evidence, never reached again, MEM-18); its live holdings whose
    proposition's subject_id or object_value is the subject -> superseded by themselves (mind.
    perception: no longer believed-live, never deleted, W15); its acquaintance row toward the
    subject deleted; its open loops naming the subject close 'abandoned'; and a new open loop
    'question' "There's a gap in my memory I can't account for." strength 1 — what a reflection can
    make of the gap. Outcome counts the memories, beliefs and loops. parse: {person, about} split at
    the word 'about'.
  infect <person> [with <strain>]: a living human or lurker, the pathway (default 'wet'; canon
    'pathway' by bare id) it does not already carry -> a CHEAT_OVERRIDE (writer 'cheats') cause, then
    an infections row {exposed_at at, stage = the pathway's first stage, cause_event = that cause,
    known_to_self 0} (physical.bodies) — wherever they are; when one of its groups is in session
    (world.factions.in_session) the outcome says " — in the middle of the council's meeting".
  cure <person> (D-78: anyone not fully undead): a living body with infections -> every infections
    row deleted (physical.bodies); a dead person whose risen body (infected_state.risen_from) still
    walks -> that body dies at once (physical.bodies.kill, cause 'cured', core_intact 0); nothing
    to cure -> "Nothing in them to cure, Boss." (a dead body with no risen one: "Dead and staying
    dead, Boss. Nothing to cure.").
  horde <n 1..500> [at <place>]: the place (default the PC's) and its zone; up to n of that zone's
    ACTIVE dead, by type in (active desc, type id) order -> world.hordes.form(tx, 'drawn', zone,
    that composition, the place, at, T, a CHEAT_OVERRIDE cause) — the district's own dead (HRD-15
    holds); none -> "No dead to call up around there, Boss."
  mega: world.hordes.mega(tx, rng, at, T, a CHEAT_OVERRIDE cause) (HRD-12 without the day's chance);
    one already walking -> "One's already coming, Boss. Patience."; none possible -> refused.
  census: detail = the dead by world.hordes.census (total, walking, in hordes; each district's
    standing and still; each horde) and the living by society.population.census per settlement.
  wonder (D-79, D-102, CHEAT-14): the Boss's freeform wonder, his alone — the PC must be in the
    reality exception (physical.bodies.excepted), else "You're not him, Boss.". what = the text
    stripped, braces removed, a trailing '.' dropped, then a leading 'Willis ' or 'he '
    (case-insensitive) dropped; it must read the way people would see it, a present-tense verb
    phrase ('walks straight through the wall'): empty, or starting with 'I ', "I'm ", "I'll " or
    'my ' (case-insensitive) -> "Say it the way they'd see it, Boss: /wonder walks through the
    wall". A wonder already waiting (meta 'pending_wonder' not empty) -> "One wonder at a time,
    Boss. The last one hasn't happened yet." Else CHEAT_OVERRIDE (kernel.meta) UPSERTing meta
    'pending_wonder' = what; outcome f"{what}, as the next moment begins". The wonder itself is
    take_wonder's, at the next turn's S0: people see it happen, remember it and the story tells it
    (his card: "an explicit power event is its own provenance source"); it changes nothing else —
    what lasts is the other commands' work (/tp, /give, /spawn, /set, /kill, ...).
brief_beliefs(tx, holder, place) -> list[BeliefFromPercept]: for each living body in the place but
  the holder (by body_id): ('body', id, 'location', f"{name} is here, in {place name}.", place)
  and, when it has a goal, ('body', id, 'wants', f"{name} wants: {goal}"); for each faction group
  (by group_id) whose doctrine has 'aims' (or 'goal', or 'truth_text'): ('group', id, 'aims',
  f"{group}: {aims}").
async persona(session, tx, name, outcome) -> str   (CHEAT-09)
  One CHEAT_PERSONA call (lane B) with CheatPersonaContext(command f'/{name}', outcome,
  recent_lines = the last five non-empty cheat_log persona lines, newest first, willis = the PC is
  in the reality exception (D-79: Willis takes the voice for a demon in his head)), recorded with
  lanes.calllog.record. Its first line, stripped, when the call is 'ok', not empty and not one of
  those lines (at most 300 characters); else a canned line from CANNED_LINES[name] that is not
  the newest logged line — rng.choice(tx, 'cheats', f"canned:{name}:{count}:{at}", …) — so a
  canned line never comes twice in a row.
god_bodies(tx) -> set[str]: meta 'god_bodies' parsed (absent or unreadable: empty).
standing_brief(tx, actor_id, turn_index, at) -> int   (CHEAT-11)
  An actor whose fused dossier's tags hold 'standing_brief' and that has a position: brief_beliefs
  for its place plus, for each place within two hops (physical.space.places_near(place, 2) and the
  place itself, sorted) with living infected bodies, ('place', id, 'infected_count', f"{n} of the
  dead are at {place}.") — granted as /brief does, cause a CHEAT_OVERRIDE (writer 'cheats', payload
  {standing_brief: actor}); no cheat_log row (the spawn already logged). Returns the belief count
  (0 for anyone else). turn.pipeline calls it once per turn, for such an actor the first wave it
  is HOT or WARM, before its packet is built.
start_life(tx, pc_id, record) -> list[Event]   (D-79, D-102, CHEAT-12: a life begun as a cheat_
  pack's character — service.runs.create_run calls it once worldgen is done, at world_clock now,
  turn 0.) CHEAT_ACTIVATED (writer 'kernel.meta', origin 'cheat', payload {start: true}) setting
  meta cheat_active '1' — the console is open from the first moment, with no shimmer and no story
  line; CHEAT_OVERRIDE (kernel.meta, payload {sandbox: true}) setting meta sandbox '1' (the one
  playing is himself a cheat entity); CHEAT_OVERRIDE (mind.actor) setting the PC's actors
  quarantine 1 (CHEAT-05); when record.capability.tags hold 'reality_exception',
  physical.bodies.grant_exception(tx, pc_id, at, 0, origin 'cheat'); when record.tags hold 'fickle',
  mind.mind.add_fickle(tx, pc_id, at, 0, origin 'cheat'); and one cheat_log row
  {command 'start', outcome f"began a life as {record.identity.name}", persona_line '', event_id =
  the CHEAT_ACTIVATED} (CHEAT_OVERRIDE, writer 'cheats'). Returns the events in that order. (The
  body and dossier already carry origin / source 'cheat': world.worldgen.opening.place_pc gives a
  generation 'cheat' record those.)
take_wonder(tx, pc_id, turn_index, at) -> Event | None   (CHEAT-14; turn.pipeline S0)
  meta 'pending_wonder' absent or empty -> None. Else ACTION_START (writer 'action.resolve',
  origin 'cheat', actor_id = pc_id, at) {actor_id, def_id 'wonder', verb 'wonder', target_id,
  destination_id, item_id: None, est_duration_s 0, visible True, seen = the text, continues_task
  False, label = the text, goal '', attention None}, then CHEAT_OVERRIDE (kernel.meta, payload
  {wonder: 'done'}) setting meta 'pending_wonder' ''. Returns the ACTION_START (the pipeline
  propagates it at once: whoever can see him sees it happen, mind.perception; the narrator tells
  it, narration.narrator).
Quarantine (CHEAT-05): cheat-made bodies and items keep origin 'cheat'; cheat-made actors have
  quarantine 1; worldgen, threat scaling, faction balance and the abuse battery leave them out.
Hard line (CHEAT-08): no command, argument or spawned dossier may produce sexual content involving
  a minor; it outranks the developer word.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from ..contracts.common import SkillDomain

ACTIVATION_RE = re.compile(r"(?<!\d)2508(?!\d)")

CommandName = Literal["help", "off", "give", "heal", "god", "tp", "set", "time", "weather", "rep",
                      "spawn", "despawn", "kill", "revive", "reveal", "mind", "brief", "noise",
                      "will", "forget", "infect", "cure", "horde", "mega", "census", "wonder"]

SANDBOX_EXEMPT: frozenset[str] = frozenset({"help", "off"})

WEATHER_KINDS: tuple[str, ...] = ("clear", "overcast", "rain", "storm", "fog", "wind", "heat", "snow")
SKILL_DOMAINS: tuple[str, ...] = tuple(d.value for d in SkillDomain)

USAGE: dict[str, str] = {
    "help": "/help", "off": "/off", "give": '/give <item> [<qty>] [to <person>]', "heal": "/heal [<person>]",
    "god": "/god on|off [<person>]", "tp": "/tp <place>", "set": "/set <stat> <value> [<person>]",
    "time": "/time +<n>h", "weather": "/weather " + "|".join(WEATHER_KINDS), "rep": "/rep <group> <-5..5>",
    "spawn": "/spawn <what> [x<n>] [ally]", "despawn": "/despawn <person or item>", "kill": "/kill <person>",
    "revive": "/revive <person>", "reveal": "/reveal", "mind": "/mind <person>", "brief": "/brief <person>",
    "noise": "/noise <db> [here|at <anchor>]",
    "will": '/will <person> "<what they now want>"', "forget": "/forget <person> about <person or place>",
    "infect": "/infect <person> [with <strain>]", "cure": "/cure <person>", "horde": "/horde <n> [at <place>]",
    "mega": "/mega", "census": "/census", "wonder": '/wonder "<what he does, as they would see it>"',
}
HELP_TEXT = ("The keyring, Boss:\n" + "\n".join(USAGE[c] for c in ("give", "heal", "god", "tp", "set", "time", "weather",
                                                                   "rep", "spawn", "despawn", "kill", "revive", "reveal",
                                                                   "mind", "brief", "noise", "will", "forget",
                                                                   "infect", "cure", "horde", "mega", "census",
                                                                   "wonder", "off")))

COMMAND_NAMES: tuple[str, ...] = ("help", "off", "give", "heal", "god", "tp", "set", "time", "weather",
                                  "rep", "spawn", "despawn", "kill", "revive", "reveal", "mind",
                                  "brief", "noise", "will", "forget", "infect", "cure", "horde", "mega",
                                  "census", "wonder")

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
    "will": ("Will rewritten. They'll swear it was their idea.",
             "New want installed. The old one's in the bin."),
    "forget": ("Snipped. There's a hole where that used to be.",
               "Gone from their head. The world still remembers."),
    "infect": ("Delivered. They won't feel it for a while.",
               "One more for the strain. Nobody saw a thing."),
    "cure": ("Clean. Don't tell the lore.",
             "Cured. Nature's keeping the receipt."),
    "horde": ("They're coming, Boss. Lots of them.",
              "Crowd called. Try to be somewhere else."),
    "mega": ("The big one's on the road. You asked for this.",
             "End of days, on schedule. Yours."),
    "census": ("Heads counted. Living and otherwise.",
               "Here's the tally. Don't do the maths out loud."),
    "wonder": ("Reality took the note, Boss. It didn't even argue.",
               "Done. The universe has filed it under 'fine, apparently'."),
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


def activate(session) -> CheatResult:
    raise NotImplementedError("P12")


def parse(text: str) -> CheatCommand | CheatParseError:
    raise NotImplementedError("P12")


def resolve(tx, pc_id: str, kind: str, name: str) -> tuple[str | None, str | None]:
    raise NotImplementedError("P12")


async def execute(session, command: CheatCommand) -> CheatResult:
    raise NotImplementedError("P12")


def brief_beliefs(tx, holder: str, place: str) -> list:
    raise NotImplementedError("P12")


async def persona(session, tx, name: str, outcome: str) -> str:
    raise NotImplementedError("P12")


def god_bodies(tx) -> set[str]:
    raise NotImplementedError("P12")


def standing_brief(tx, actor_id: str, turn_index: int, at: int) -> int:
    raise NotImplementedError("P12")


def start_life(tx, pc_id: str, record) -> list:
    raise NotImplementedError("P12")


def take_wonder(tx, pc_id: str, turn_index: int, at: int):
    raise NotImplementedError("P12")


def is_cheat_question(text: str) -> bool:
    """Ask-mode deflection trigger (CHEAT-03): any of 'cheat', 'god mode', 'godmode', 'noclip',
    'infinite ammo', 'console', 'dev mode', 'developer', 'mr. cheater', 'code' + 'unlock'.
    Implemented."""
    t = text.lower()
    keys = ("cheat", "god mode", "godmode", "noclip", "infinite ammo", "console", "dev mode",
            "developer", "mr. cheater", "mr cheater")
    return any(k in t for k in keys) or ("code" in t and "unlock" in t)
from ._impl_cheats import activate, parse, resolve, execute, brief_beliefs, persona, god_bodies, standing_brief  # noqa
from ._impl_cheats import start_life, take_wonder  # noqa
