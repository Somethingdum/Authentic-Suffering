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
| knowledge | knows / does not know / knows but hides → seed beliefs at worldgen | CMG §15.4 |
| voice | capsule, speech tendencies, **three exemplars (low stakes, under pressure, at the limit)**, **would never say (≥3)**, profanity level, dialect | CMG §14, §22.1 |
| social | household role, relations (with history), dependents, guardians, faction memberships | Plan §8.2 |
| life | aspiration, current project, routine, obligations, hopes, **fears (≥1)**, secrets (with who knows and exposure consequence) | Plan §6.3 |
| disposition | archetype prior, stance toward strangers, default action on detecting a stranger | S/U First Contact, Stage-2 filter |
| writers_notes | **human-only**; the model never writes it; always injected when the Actor is on stage | CMG §05 three-source anti-drift |
| depth_reference | long-form markdown, pulled only on demand (never in a packet by default) | CMG PC dossier L5 |

**Never trimmed (DOS-01).** Storage = full baseline JSON + deltas; fused at call time. A dossier
that describes a category instead of a person fails validation (CNT-10), because thin dossiers are
the identified root cause of drift.

**Voice comes from the database, not model recall (DOS-05).** Every committed SPEECH by an Actor is
stored in `voice_lines`; the packet carries the three exemplars plus up to five recent real lines
(pinned lines first). Pinning is a UI action (People panel → "Pin this line").

## 3. The Skull Packet

Built only by `mind.packet.build_packet` (contract `SkullPacket`, rendered by
`prompts/actor_cognition.*.j2`). It contains, in plain English: identity; motive, persona, moral,
decision and trait lines; voice; body; capability incl. Resolve; position; **perceived now** (with
fidelity words: *clearly / only partly, some words lost / only the tone, no words*); **what was
said** (utterances with form and the receiver's standing); people (by name if known, else
description); relationships; beliefs with provenance and age; retrieved memories; open loops;
standing refusals; commitments; dependents and obligations; what it would cost; uncertainty; the
**options** (affordances A1…).

Three absences are as load-bearing as any field:
- **No objective event log.** Ever.
- **No other Actor's intent, state or reasoning.**
- **No instruction to forget anything.** If it must not be used, it is not in the packet (L1).

Handles (P#, S#, E#, L#, A#) replace internal ids; the map stays in code. The JSON schema for the
answer restricts `choice` to the offered A-handles and `speech.to` to P-handles, so an Actor cannot
pick an option or a person that was not offered (INTENT-02).

## 4. Will formation: affordances before choice

**CODE computes what this body could attempt → the model chooses among them and motivates**
(plan §6.4 LAW). An option exists only if every gate passes, in order:

| Gate | Question | Data |
|---|---|---|
| physical | Can this body do this here? | capacity (mobile, hands free, conscious), reach/range, held/carried item tags, aperture |
| skill | Does this person know this is a thing to do? | skills, trained responses, belief cues, tech literacy |
| belief | Does this person think it would work? | belief cues (e.g. `knows_headshot_rule`, `knows_false_death`) — held as lessons rows, seeded from `knowledge.cues` and held lore beliefs, learned in play (AFF-10) |
| resolve | Can this person bring themselves to choose it now? | Resolve table (§5) |
| resource | Can they pay for it? | ammo, bandage uses, keys, tools in reach |
| duty | Does a post, standing order, law or dependent forbid it? | duty anchor, active laws, guardianship |
| moral | Does it cross their own line? | affordance moral tags ∩ dossier `wont_tags` |

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
   entrenched refusal (the requested option was removed by the duty or moral gate — unmovable by
   persuasion; only a change in the world can move it) · false compliance (says yes, does something
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

When both lanes are idle between turns (the player is reading or typing), `GameService` runs
REFLECTION jobs for salient Actors (recently HOT/WARM and ≥3 new episodes since their last
reflection): add goals/desires/grudges, abandon or fulfil loops, draw a lesson, update the plan
(goal + ≤5 steps). One job per lane at a time; **cancelled instantly** when the player submits;
results are committed only if the job finished before the submit (a REFLECTION event, recorded as
an external input for replay). This is how people build their own internal state over days.

### 9.3 Retrieval (what a mind gets back)

The model never decides what it receives. `mind/retrieval.py` computes a key set from committed
state (place, perceived entities, names in perceived speech, open-loop subjects, current target)
and ranks beliefs, episodes (SQLite FTS5 on the perceived speech's content words), lessons, loops
and refusals deterministically, within `PacketRules` caps and the packet token budget. Anchor
memories (salience ≥ 90, or a bonded person's death) never decay and are always eligible.

### 9.4 Forgetting

Episodes decay by the Memory Fade score (06 §Decay); anchor memories and persistence-locked
subjects never do. Beliefs are never deleted — they are superseded.

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
