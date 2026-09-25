# 05 — Actors, Minds and Narration

> **Could this fact have reached this mind, through this world, in this time?**
> If not, and the mind used it anyway, the turn is invalid. (Plan §1, the one-sentence test.)

## 1. What an Actor is

"Actor" is a statement about how a body is processed, not a category of entity. The PC is processed
as an Actor with exactly one difference: its intent comes from a human. There is **no player branch**
in perception, affordances, resolution, harm, death, memory or social code (L12, SYM-01 AST scan).
Infected Shamblers/Crawlers/Runners are bodies driven by code policy (`controller='policy'`);
Lurkers are Actors with model cognition (they learn, remember and plan — Lore §4).

## 2. The dossier

Contract: `contracts/dossier.py` (`ActorDossier`, `PCDossier`). Authoring guide: 09. Sections:

| Section | Carries | Source of law |
|---|---|---|
| identity | name, aliases, age, sex, cohort (pre-Fall adult / Fall child / post-Fall born), birthplace, occupation before/now, one-line | Plan §6.3 |
| appearance | size, build, **distinguishing marks (≥1)**, movement under stress, habit/gesture, relation to own appearance | CMG §15.3 |
| capability | SPECIAL 1–10, skills (domain, rank 1–3, **evidence**), capability tags, trained responses, literacy, tech literacy, Resolve trait modifier | Plan §6.3, §6.4 |
| motive | motive · method · moral line (will / won't + machine tags) · inner conflict · past wound · signature behaviour · risk threshold · resource constraints | IRONCLAD Step 5 verbatim shape |
| persona | public (shown traits, claimed history, presented affiliation) vs private (true goals, concealed history, real affiliation) | S/U Public/Private |
| traits | each trait individually defined: manifests / triggers / causes / costs / example (≥2) | CMG §15.1 |
| contradictions | ≥1: belief A vs belief B and when each wins | CMG §15.2 |
| decision stack | ≥4 ordered layers, inversion conditions, a past example | CMG §15.5 |
| silence | when they go quiet (≥2), body when silent, topics refused, comfortable vs uncomfortable | CMG §15.6 |
| knowledge | knows / does not know / knows but hides → seed beliefs at worldgen; *does not know* is an authoring check only and never reaches a prompt (naming a hidden fact supplies it, IDN-02) | CMG §15.4 |
| voice | capsule, speech tendencies, **three exemplars (low stakes, under pressure, at the limit)**, **would never say (≥3)**, profanity level, dialect | CMG §14, §22.1 |
| social | household role, relations (with history), dependents, guardians, faction memberships | Plan §8.2 |
| life | aspiration, current project, routine, obligations, hopes, **fears (≥1)**, secrets (with who knows and exposure consequence) | Plan §6.3 |
| disposition | archetype prior, stance toward strangers, default action on detecting a stranger | S/U First Contact, Stage-2 filter |
| writers_notes | **human-only**: the model never writes it and never reads it — editorial guidance for authors, kept out of every prompt (IDN-02, Actor Spec AC02). What a note asks for belongs in the fields the card is made from | CMG §05 three-source anti-drift; Actor Spec §4 |
| depth_reference | long-form markdown, pulled only on demand (never in a packet by default) | CMG PC dossier L5 |

**Never trimmed (DOS-01).** Storage = full baseline JSON + deltas; fused at call time. A dossier
that describes a category instead of a person fails validation (CNT-10), because thin dossiers are
the identified root cause of drift.

**Voice comes from the database, not model recall (DOS-05).** Every committed SPEECH by an Actor is
stored in `voice_lines`; the card carries the three exemplars and the packet adds up to five recent
real lines (pinned lines first). Pinning is a UI action (People panel → "Pin this line").

### 2.1 The identity card (Actor Spec §4, AC02 / AC04; `mind/identity.py`, IDN-01..05)
A call shows a person the whole of who they are, compiled from the fused dossier by code
(`compile_identity`, implemented in the kit): who they are and where they come from; what matters
to them (their motive, the order of their priorities and when it flips, the risks they take); their
limits (will / won't, what they owe); **where they are pulled both ways** (each contradiction and
when each side wins); their own life (what eats at them, what they carry, hope, fear, the face they
show and what they hide, their secrets); **their habits** (each trait with what it makes them do and
what it costs, their habits of hand and movement); **how they talk** (capsule, tendencies, the three
exemplars, what they would never say, swearing, accent); **when they go quiet**; and what they know
how to do, ending *"No established specialist training beyond this list."* Every line names the
dossier fields it came from (the source map), so the card never says anything the dossier does not.

What it keeps out (IDN-02): the writers' notes, what the person does not know, who knows their
secrets, reflexes (code's), counts that go stale (what they carry comes from their body and items),
the numbers the rules use, and the generation labels. A reaction gets the **minimum card** — the
same lines, fewer of them: who, what comes first, the limits, the voice under pressure, when they go
quiet, their skills. No budget trims the card (SKULL-09); a card that will not fit is a reason for
a larger context, never for a smaller person.

Authoring (09): the fields the card is made from describe tendencies, never senses or knowledge of
the present. "Knows where everyone is without looking" would grant a sense; Mara's vigilance reads
"keeps checking where each person in the room is, with quick looks nobody notices", and where people
actually are comes from what she perceives.

## 3. The Skull Packet

Built only by `mind.packet.build_packet` (contract `SkullPacket`, rendered by
`prompts/actor_cognition.*.j2`). It contains, in plain English, under the Actor Spec's headings and
in this order — identity first, then memory, then the moment (§6 of the spec): **Who you are** (the
card, §2.1, and the lines they said lately); **What you remember** (beliefs with provenance and
age, retrieved memories, lessons); **What matters to you now** (commitments, dependents and
obligations, what it would cost, open loops, standing refusals); the time (the hour only for
someone with a timepiece on them — anyone else knows the day and the part of it); **Your body**
(with Resolve and what they carry); where they are; **What reaches you** (percepts with fidelity
words: *clearly / only partly, some words lost / only the tone, no words*); **What you heard**
(utterances with form and the receiver's standing; a flood of words past 800 characters is cut
where a word ends, with " …" — heard, not obeyed, and never crowding the person out of their own
context); **People you can account for** (by name if known, else description, and where they are
as far as this mind knows: *here* — seen now —, *heard, not seen*, *last seen in the office 2 hours
ago*, or *not seen*: being someone's son never puts him in the room, Actor Spec AC14; for someone
*here*, a line under theirs says what this person sees and smells of them — hair, clothes, a badge,
a gun on the belt, blood and filth, the reek of the dead — at that distance and in that light,
LOOK-06, SMELL-04); **Your
understanding of them**; **What remains uncertain**; and the **Possibilities you notice**
(affordances A1…).

The instructions around it are a person's own (Actor Spec §6, AC01): *"You are the person described
under Who you are. The current moment is yours to respond to…"* — cooperate, refuse, hesitate, keep
working or stay silent as follows from who they are; an order is someone asking for conduct; do not
search for a dramatic outcome; choose an attempt, never its success. Nothing in them names a story,
a narrator, a player, an author or an audience. A reaction adds one last paragraph ("Something just
reached you…"). The answer's fields follow the instructions as a technical note.

Four absences are as load-bearing as any field:
- **No objective event log.** Ever.
- **No other Actor's intent, state or reasoning.**
- **No instruction to forget anything.** If it must not be used, it is not in the packet (L1).
- **Nothing from later than the moment it decides** (SKULL-10, P10). A wave writes its landings
  when it resolves, so a percept from a second later can already be in the log when an earlier
  reaction decides; the packet, the options, recall and salience read only percepts up to the
  mind's own moment (D-63).

**What the budget may cut** (SKULL-09, Actor Spec AC16). Over its token budget the packet drops
memories, lessons, beliefs, the lines about people who are not here, old refusals and uncertainty
lines, in that order — never the card, the moment, the body, the options, what they are in the
middle of, their open loops, or a standing refusal of someone who is here or speaking now: what
bears on this decision is pinned. Every line it cut is kept, in order, in the packet's `omitted`
list (never rendered), so what a person was not shown can be audited.

Handles (P#, S#, E#, L#, A#) replace internal ids; the map stays in code. The JSON schema for the
answer restricts `choice` to the offered A-handles and `speech.to` to P-handles, so an Actor cannot
pick an option or a person that was not offered (INTENT-02).

## 4. Will formation: affordances before choice

**CODE computes what this body could attempt → the model chooses among them and motivates**
(plan §6.4 LAW). An option exists only if every gate passes, in order — except duty, which only
says what an option would cost:

| Gate | Question | Data |
|---|---|---|
| physical | Can this body do this here? | capacity (mobile, hands free, conscious), reach/range, held/carried item tags, aperture |
| skill | Does this person know this is a thing to do? | skills, trained responses, belief cues, tech literacy |
| belief | Does this person think it would work? | belief cues (e.g. `knows_headshot_rule`, `knows_false_death`) — held as lessons rows, seeded from `knowledge.cues` and held lore beliefs, learned in play (AFF-10) |
| resolve | Can this person bring themselves to choose it now? | Resolve table (§5) |
| resource | Can they pay for it? | ammo, bandage uses, keys, tools in reach |
| duty | What would keeping a post or a law they know cost them? (a note; it removes nothing) | duty anchor, the laws of the place they know, guardianship |
| moral | Does it cross their own line? | affordance moral tags ∩ dossier `wont_tags` |

**A menu built from what the person knows** (AFF-11; Actor Spec AC06, AC07; fidelity C05). Two
worlds that differ only in something a person has not seen or been told offer them the same options
in the same words: whether a closed door is locked (opening it is offered; the attempt finds the
lock), whose an item is on record ('owned', and so stealing, is what they *believe* about it), a
law nobody told them, what someone carries out of sight (a weapon in a hand counts only when seen
clearly: in the dark, anyone may be unarmed), an infection that shows nothing yet. What they do know is a
cost next to the option, never a missing option: a member of a settlement's group knows its laws;
anyone else only the ones they were told; a law's `forbid` and `cost` both add its note, and the
world answers when it is broken. Only their own immutable lines (the moral gate) and their body take
options away. When several costs apply they are all said: the post's, then the laws', then the
nerve's.

**The answer** (Actor Spec §7, §8, AC05; D-74). The first menu is short and diverse (24 options,
`PacketRules.max_affordances`); what it hides stays in the set's pool. A person answers with a
decision — one offered attempt, its pace (careful or rushed only where the attempt allows it; the
one manner that changes time, noise and the check), what they say (at most 100 words, 12 in a
reaction), a goal and a private reason — or, only when offered, with one consultation first: recall
something of their own, or see more attempts of one family the menu names. A consultation reads
their own head and menu, never the world, and nothing happens until the decision (`mind/consult.py`,
CONSULT-01..06).

**A failed answer never becomes a choice** (AC15; HOLD-01..02; D-75). If a person's answer cannot be
used even after its repair, code never picks for them: what they already took on goes on (their
task, a plan step, a watch at their post), or they make no attempt; and when someone had just asked
them something or they faced a threat, the turn is not played at all.

Consequences: two people with different stats want different things because different things were
on their menus; a weak Actor never selects a strong Actor's plan; incompetence is portrayable
without being narrated as stupidity. The catalog is content: `as_content/packs/core/affordances/`.
Selection rules (grouping, caps, the always-present wait/observe) are in `mind/affordance.py`.

## 5. Resolve

`Resolve.max = 3 + floor((E + C) / 4) + resolve_trait_mod` (RulesConfig.resolve). Drains (each
cites its event): witnessing a bonded person's death 2, sustained fear scene 1, public humiliation 1,
severe pain 1, betrayal 2, first kill 1, killing a child 3, a starving day 1, a sleepless night 1,
losing a dependent 3, being made to watch 2, being coerced 1. Recovery: +1 per night asleep in a
place the Actor *believes* is safe; +1 fulfilled obligation; +1 protecting a dependent.

**Resolve gates options; it never modifies a roll.**

| Resolve | Options generated |
|---|---|
| 0 | only flee, escape, surrender, wait (freeze), protect-a-dependent, comply-under-threat |
| 1 | everything except options needing sustained exposure to the fear source |
| 2 | everything; options opposing an authority they accept carry a cost note |
| 3+ | everything |

A hard refusal is made of Resolve: coercion drains it; an Actor with Resolve left can refuse
indefinitely; at 0 they comply — and the compliance is logged as **coerced**, becoming grievance,
fear and an open loop, never consent (WILL-08).

## 6. The Request Firewall

> A request never becomes an action. It becomes an event perceived by an Actor, who then
> independently chooses a response. (L6)

1. **Representation.** The request enters the packet as a perceived utterance with speaker, exact
   words (at the fidelity heard), volume, form and standing. There is no field named request,
   order, task or ask, and the answer grammar has no comply/accept/refuse field.
2. **Classification (code).** Form: request · demand · order · threat · offer · question ·
   statement (`mind/firewall.py::classify_form`). Standing is read from the **receiver's** record:
   hostile · valid order · subordinate · claimed authority · peer · stranger. A stranger's
   imperative is a demand, not an order (WILL-04).
3. **Cost is present.** When an utterance is addressed to the Actor, the packet's commitments,
   stakes and resources sections are mandatory (WILL-C).
4. **The response ladder** is computed *after* the choice by comparing the chosen option with the
   request's signature: ready compliance · reluctant compliance · counter-offer · refusal ·
   entrenched refusal (the requested option was removed by the moral gate — one of their own
   immutable lines, unmovable by persuasion; only a change in the world can move it) · false compliance (says yes, does something
   else — logged as a lie) · coerced compliance.
5. **Threats are not persuasion.** Coercion never routes through a social check; it drains
   Resolve, raises fear and resentment, and the fear-response options (comply-and-resent,
   comply-and-lie, flee, freeze, pre-emptive violence, seek allies) are what the menu offers.
6. **Asking again is never better** (WILL-05). A standing refusal loads into the packet on any
   related ask; `times_asked` increments; from the third ask resentment rises; any negotiable
   check on the same signature gets `-(times_asked - 1)`.
7. **Asking has consequences even when refused** (WILL-06): boundary-crossing requests (abandon a
   dependent, betray family, surrender a weapon, leave a post) move at least one relationship axis.
8. **Defection pressure** = f(grievance, obligations owed to me unpaid, material deprivation,
   dependent endangerment, ideological divergence, perceived group viability, fear of leaving).
   Crossing the risk threshold triggers **planning** (a private goal, hoarding, contact,
   reconnaissance) which leaves traces before it fires.

Camp entry screening by the officer's traits, "NOT by a roll", ships as the canonical example of
L7 (identity is never rolled): the Mafia Remnants' intake doctrine in the core pack uses it.

## 7. Involuntary response and impairment

Involuntary actions (flinch, freeze, trained response, panic) happen without a decision when a
percept crosses a startle threshold and the Actor holds a matching trained response or has Resolve
≤ 1; they are timed, caused and recoverable (`INVOLUNTARY` events). Impairment (0–6, from pain,
blood loss, needs, intoxication, concussion, exhaustion, panic, cold) removes options and adds cost
notes; the player sees impairment in what the body does, never as a hidden penalty.

**A compulsion is involuntary too** (P10, `turn/cognition.py` decide step 3; Lore v2). A wet-strain
host in the third week of the living-spreader phase is made, now and then (at most every
`compulsion_cooldown_min` minutes), to offer food or drink from their own mouth to someone near —
an `INVOLUNTARY {kind: 'compulsion'}` act built by code from the core `give_item` option, whatever
the person would have chosen. It is never done to the player's character: the PC feels the urge in
the story (the stage's `felt` sentence) and the player decides. The earlier weeks' pull shows only
in what the host feels and in the packet's body lines.

### 7.1 Breaking points, grudges and betrayal (H1, D-84; `mind/temper.py` TEMPER-01..08)

The owner: people here are smart, but *human* smart. Humans fight — wars, bar-room brawls,
bickering. The logical thing is to suck it up and get along, and not everyone can. Everybody has a
breaking point; disrespect the wrong person too much and you get decked in the jaw. Somebody can be
furious for a reason that is not fair and mean it with their whole heart. Consequences are not
always violence. And when the dead come, someone may push the person who has been getting on their
nerves into them to buy a few seconds.

The engine never tells a mind to make trouble (Actor Spec §10). It keeps the pressures true and
makes the snap, when it comes, code's act:

- **Stress** (`actors.stress` 0–10) is what wears a person down: seeing someone die (more the closer
  they were, CAS-019), hunger, thirst and exhaustion past the first pangs (CAS-020), being struck or
  threatened, seeing their people hurt. A night's sleep takes the edge off (CAS-021).
- **Temper** (dossier `temper`: `fuse` 1–5, `outlet` fists / words / cold / flight / tears,
  `grudge` 0–3, `pet_peeves`, `cools_down_by`) is how this person breaks. It is on their card
  ("What sets you off").
- **Heat** (`tempers`, per person toward another) builds from what they perceive done or said to
  them — struck, shoved, grabbed, threatened, ordered about by someone they don't answer to,
  insulted, their own people hurt, their things taken — each once, and fades an hour at a time;
  a grudge keeps it warm. The breaking point is `fuse x 2 - stress // 3`: the more stressed, the
  shorter. (F1c, TEMPER-09) Heat also builds from what someone *is*, not only what they did: the
  reek of the dead on a person close by grates again every ten minutes, faster than it fades; a
  naked adult in plain sight is a jolt of strain and heat, again every half hour.
- **The packet says it**: "You are close to breaking." / "You are at the end of your rope."; beside
  each person, "they are getting under your skin", "you are furious with them", "you hold a grudge
  against them". The actor core now says it plainly: you are a person, not a planner; you can lose
  your temper, hold a grudge that is not fair, say the cruel thing, look after yourself first.
- **The snap**: past the breaking point a person may swallow it (a chance from their Resolve, which
  it costs) or it comes out — `INVOLUNTARY {kind: 'outburst', outlet}`. Fists: a punch, whatever
  they had decided and whatever nerve is left (never at a child, never at someone in their care).
  Words: they must have it out, raised or shouted, in their own words. Cold / flight: they walk out.
  Tears: they sit down and break down. A snap leaves a grudge (it deepens if one was there) and
  resentment. The player's character is never made to snap; their anger is on record.
- **Off-screen friction** (STL-15): in a settlement, two people who resent each other have a row on
  any given day more often the more strained they are; a brawler's rows come to blows (bruises, lost
  standing); either way people talk.
- **Betrayal**: with the dead within 8 m, *shove someone toward the dead* is an option like any
  other, ranked right after running (AFF-07): win the shove and they land on their back up to 2 m
  closer, and the dead turn on them. *Shoot someone in the leg*: they go down and cannot run. A
  person's own lines (`feed_to_dead`, `kill_human`, `kill_child`) take the shove off their menu.
  Everyone who saw it stops trusting the one who did it, the story travels (CAS-022), and whoever
  lived through it never forgets (CAS-023).

### 7.2 Timing, gestures and attention (Actor v2 B4, D-87; Actor Spec §9)

One primary attempt at a time is a limit on the body, not on the person: words, a small gesture and
where they look can go with it when their voice, hands and eyes are free. The resolver owns the
timing; the person chooses only what goes with what.

| Rule | What it says |
|---|---|
| SEG-01 | A long speech arrives in segments of at most eight words, cut at the last pause (. , ; : ! ? … —) among the 4th to 8th words (`action.intent.segments`). |
| SEG-02 | Words take 2.5 a second, however few: alongside an attempt they overlap it (the longer of the two), before or after it they add; nobody hides or sneaks while talking (their words come first) (`action.intent.to_intent`). |
| SEG-03 | Each segment is a SPEECH of its own, said when the words before it have been (the rest queued as SPEECH_SEGMENT); words 'after' an attempt start when it lands (`action.resolve`). |
| SEG-04 | A segment is said only if the speaker is alive and conscious then; a new attempt cuts what is left (one voice, one utterance); one SPEECH_CUT records where the words stopped, and listeners only ever hear what was said. |
| GEST-01 | The packet offers the gestures the person's free hands allow — nod, shake of the head, shrug; pointing, beckoning or waving someone off toward each person here; a finger to the lips; both empty hands shown (`mind.packet`). |
| GEST-02 | A gesture takes the hands the attempt leaves free (`INTENT-09`: 'no_free_hand'); contact is never a gesture — a touch, a grab, covering a mouth is an attempt of its own. |
| GEST-03 | A gesture goes out with the attempt as a GESTURE event: seen at clear or partial, never heard; 'Mara points at you.' (`action.resolve`, `mind.perception`). |
| FOCUS-01 | The packet offers where to keep your eyes: each person here, each door of the room you can see (`mind.packet`). |
| FOCUS-02 | Eyes on one thing: it is seen one step better, everything else one step worse, until the next attempt (`sense.optics.visibility`). |

## 8. The player's side

- **Manner, never target/verb/refusal** (SYM-02): the PC's dossier colours how an action is done.
- **"Say it my way"** (setting): the Dialogue Seed Protocol (CMG §53) — the player's idea goes
  through the PC's voice; the result is `intact / softened / garbled / withheld`.
- The PC's options are gated exactly like everyone's: a PC with no firearms training who has
  never learned that only the head stops them is never offered a head shot; a PC at Resolve 0 cannot choose to charge the thing that terrifies them. The
  UI explains a rejected input in plain words.
- The PC has the same record as any Actor (promises, obligations, reputation, relationships,
  lessons, open loops) so the world can hold the player to what they said three days ago.

## 9. Memory: how minds persist and grow

### 9.1 Aftermath → writeback (every turn)

After commit, each mind that perceived anything gets an `AftermathPacket` with only its own
percepts (L8). WRITEBACK (lane B) returns: an episode in the mind's own voice with salience; beliefs
(each citing the percepts that caused it); relationship changes (−2..+2 on one axis, citing a
percept); new open loops — **goals, desires, grudges, fears, questions, plans, promises, debts,
secrets kept** — each citing a percept; closed loops; an optional lesson with cue tags. Items that
cite a percept the mind does not have are dropped and logged (G14). Two people remember the same
event differently because they perceived it differently; a partial overhear produces a partially
wrong belief by design.

### 9.2 Reflection (quiet hours, background)

Between turns, while the player reads (`service/background.py`, BG-01..07; Actor Spec AC12), a
person reflects when the world gives them reason — a new memory that mattered (salience ≥
`material_salience`, or an anchor), or a night's sleep since at least three ordinary new ones — at
most two people a boundary, the freshest experiences first: add goals / desires / grudges, abandon
or fulfil loops, draw a lesson, update the plan (goal + ≤ 5 steps). **Simulated time decides, never
the player's reading speed** (BG-07): which reflections a boundary owes is fixed by the world as the
turn left it, and the next turn first finishes whatever is still owed, so answering at once and
waiting an hour give the same people the same thoughts. Results are REFLECTION events (recorded as
an external input; replay re-applies them without a model call). A reference to anything the packet
did not offer is dropped and logged. This is how people build their own internal state over days.

### 9.3 Retrieval (what a mind gets back)

The model never decides what it receives. `mind/retrieval.py` computes a key set from committed
state (place, perceived entities, names in perceived speech, open-loop subjects, current target)
and ranks beliefs, episodes (SQLite FTS5 on the perceived speech's content words), lessons, loops
and refusals deterministically, within `PacketRules` caps and the packet token budget. Anchor
memories (salience ≥ 90, or a bonded person's death) never decay and are always eligible.

### 9.4 Forgetting

A mind forgets by retrieval (§9.3): old, unremarkable episodes rank lower and stop coming back,
while anchor memories always stay eligible. Nothing is deleted from the record — the world keeps its
whole history (06 §4, fidelity C02) — and beliefs are never deleted either: they are superseded.

## 10. Lies, persona, conviction, rumours

- Actors lie without a lying system: they say what they choose; the world records "X claims Y".
- Render and dialogue express the public persona unless a perception event has pierced it (a
  contradiction observed, a slip, a document read, a believed testimony) — `PERSONA_PIERCED`.
- Convictions (faith, blame, prophecy, theories about the infected) are adopted under uncertainty
  and expressed only where conditions permit (S/U Stage-1 Theorizers generalised).
- Rumours pass hop by hop with provenance and optional distortion (06 §Rumours).

## 11. Narration

The narrator is a mind whose skull is the PC's (L9). `narration/narrator.py`:

- **Input**: only the PC's percepts of this transaction, in order; speech lines carry the exact
  words the PC heard (fragments included). Place details only when establishing a place.
- **Rules** (prompt + code lint): write only what is listed; never another mind's interior; never
  "unknown to", "meanwhile", "while you were gone"; quoted speech must match committed speech
  (DISC-SPEECH); names only if the PC knows them (DISC-NAME); one uninterrupted scene; no headings,
  lists, stats or menus.
- **Comprehension layer** (NARR-05): the PC's Perception and Intelligence decide how much of a
  tactic the prose explains ("Anya shoots the raider" vs "Anya lays down measured fire on the
  doorway, keeping his head down while Mara crosses"). Raising PC Intelligence changes the
  explanation and changes no fact (DISCLOSE-03).
- **Narrator continuity state** is saved with the run (pacing, density, register, recently used
  images) so texture survives save/load (STYLE-03).
- **Measurable prose quality** (07 §Style) is computed in code; a failing draft is regenerated from
  the same committed events (max 3 attempts); state is untouched.
- **Echo** (the "quoted back a thousand times" problem): an n-gram ledger of the player's input
  (last 20 turns) rejects any generated Actor line or narration that repeats a 4-word run with two
  or more content words, unless it is a licensed deliberate quotation (once per phrase).
