# LORE_STRUCTURE — how to write a lore document the engine can use

For the owner's next lore document (and any later one). It says what the document must contain
and how to lay it out so that **dossier intake** (09_CONTENT_PACKS §8.1: the Content screen →
"Turn a document into a record") turns it into records without guessing. Intake splits the text on
headings, and the main model fills each record's fields from the section in front of it. It never
invents a field the section does not support, so what is not written stays empty and shows up in
the draft's `.gaps.md` file.

Nothing here limits what the world can contain. It only makes sure what you write reaches the
simulation intact.

---

## 1. The rules that apply to everything

1. **One heading per record.** A creature, a quirk, a faction, a law, an infection process, a
   condition, a place, a person, a canon event: each gets its own heading, with its kind in the
   heading — `## Lurker (infected type)`, `## Lurker venom (condition)`, `## Becoming a Lurker
   (infection process)`. Sub-headings under it belong to it. Never split one record across two
   top-level headings, and keep each record under about 12,000 tokens (intake reads that much at
   once).
2. **Stable ids.** Give every creature, quirk and infection process a permanent id and never
   reuse or rename it (`ZOMBIE_VARIANT_ID_LURKER01`, `LUR_MIMICRY_LURE`). Everything else can go
   by its name; the engine makes the id.
3. **Two layers, always.** For every topic, say separately:
   - **Truth** — what is actually so. The engine simulates this and never shows it to a mind.
   - **Beliefs** — what people think, **who** thinks it (everyone; a faction; people born after
     the Fall; one region) and **how sure** they are (0–3). Wrong beliefs are welcome; say they are
     wrong. A topic with no belief layer cannot be loaded (LORE-01).
4. **Who can ever know it.** Mark each truth: *common knowledge*, *learnable* (by what: seeing it,
   being told, a document, an experiment) or *never knowable* (Codex's kind). The engine enforces
   this: a never-knowable truth never reaches a mind by any door, the console included.
5. **Numbers, not moods.** The simulation cannot run "a while" or "usually". Give a number or a
   range for every time, chance, distance, count and strength: hours or days, a percentage,
   metres, decibels, 1–10 scales. "Most people (about 85%)" is perfect; "most people" alone is a
   gap.
6. **Canon status per statement.** Mark anything unsettled as *provisional*. The engine keeps it
   but flags it, so it can change without breaking a run.
7. **Era.** If something differs by era (Early: under a year; Established: 1–4 years; Mature: 5+
   years), say how for each era.
8. **Examples are marked as examples.** A rule and an example of it look alike to a model. Put
   examples under a line that says "Example:"; the engine uses them as portrayal samples, not as
   rules.
9. **One precedence line** at the top: what wins when two statements disagree (for example:
   canon events > this document > older documents). Where it contradicts an older document on
   purpose, say so once.
10. **Retired ideas go in their own section** at the end ("Retired — do not use"), each with what
    replaced it. The validator warns if a retired name shows up anywhere.

---

## 2. What each kind of record needs

Headings in *italics* are the fields the engine reads. Anything more is welcome as depth text:
the engine keeps it and pulls it into a prompt only when that topic is in play.

### 2.1 Infected type (`## <name> (infected type)`)
- *Id*, *name*, *rarity* (common / uncommon / semi-rare / rare), *what it inherits from* (if any).
- *Stats* as ranges (S, P, E, C, I, A, L on 1–10) and what scales them (age, state).
- *Senses*: the quietest sound it reacts to (dB), how far it sees (m), how it sees (motion only,
  shapes, heat, full sight), whether it sees heat.
- *Speed*: walking and sprinting (m/s); *grip* (1–10); *climbing*: highest climb (cm), widest gap
  (cm), highest drop (m), chance of falling on each (%).
- *Alive or dead*; *false death* (yes/no, how many hours before it gets up); *what truly kills it*.
- *Player-facing knowledge* (beliefs) and *truth*, as separate lists.
- *Tactics*, *weaknesses*, *quirks* (by id).
- *How it chooses a target*: what makes it engage, what makes it wait, what makes it leave. For
  thinking hunters, write these as rules ("never engages an armed person"; "disengages after a
  failed ambush and returns within N days").
- *Life stages* if it has them: name, age range, what changes (size, strength, what it knows,
  how it hunts).
- *Society* if it has one: groups, ranks and what each rank does, how many per group, how groups
  relate.
- *Where it lives* and *how many there are*, per era and per region type.
- *How to write it*: what the narrator may show (fragments, sounds, smells), what it must never
  show, and its tells. The owner's canon events are the reference; cite them.

### 2.2 Quirk (`## <ID> (quirk)`)
- *Id*, *which types have it*, *what it does* (one or two sentences), *what sets it off* (a
  situation), *what a witness sees or hears*, *how common* (relative weight).
- If it changes what the creature does, say how in numbers (how long, how far, how often).

### 2.3 Infection process (`## <name> (infection process)`)
One record per way of becoming something else — the wet strain, the air strain, the unbitten
rise, becoming a Lurker.
- *Id*; *how it is caught*: each exposure (a bite, a slash, saliva, a shared bottle) with its
  chance of infection (%).
- *Stages*, in order. For each:
  - *when it starts* (hours or days after exposure);
  - *what changes* in the body and the mind;
  - *what the host feels*, as one sentence in the second person ("Your wound itches under the
    skin");
  - *what someone else can see* up close;
  - *contagious or not*, and how;
  - *compulsion* (0–3: how hard it drives them) and *impairment* (0–6);
  - *what the dead do* around them at this stage;
  - *what the host does on their own* (hides the wound, drifts away, seeks a place).
- *The end*: death and when, or the transformation and how long it takes; what they rise or
  emerge as; who (if anyone) ever witnesses it.
- *What can change the course*: nothing, time bought, pain — the no-cure rule applies unless you
  say otherwise.

### 2.4 Condition (`## <name> (condition)`)
Anything a body can be put into: venom paralysis, shock, a fever, a broken mind.
- *What causes it* (and the chance, dose or threshold).
- *How fast it takes hold* and *how long it lasts*; what ends it early.
- *What the person can still do*: move, speak, blink, see, hear, feel pain, think clearly.
- *What they perceive* and *what it feels like*, in their own terms.
- *What others see*.
- *What it leaves behind* afterwards (injury, memory, fear, a mark).

### 2.5 Lore topic (`## <title> (lore: history | place | faction | infected | culture | rumour | tech | person)`)
- *Truth* (one paragraph); *beliefs* (who, what, how sure); *who can know*; the entities it
  concerns.
- (D-130) *What brings it to mind*: the words or short phrases people would use when talking about it
  ("cure", "the Steward", "crying for help"), and the moments that bring it up unasked (a scream heard,
  a bite seen, a body on the ground). A person who holds one of its beliefs remembers it when they hear
  one of those words, see one of its entities, or live one of those moments — never otherwise.

### 2.6 Faction or group (`## <name> (faction)`)
- *What they want* beneath *what they say they want*; *methods*; *what they will not do*.
- *What they have*, *what they need*, the *pressure* on them.
- *Leaders* (titles and what each decides), *how leadership is contested*, *fault lines*.
- *Relations* with each other faction (allied, cooperative, neutral, wary, hostile, at war,
  unaware) and the history behind each.
- *Doctrine*: how a stranger is challenged; the escalation steps; how unknowns, the visibly sick
  and prisoners are treated; intake steps.
- *Laws* (see 2.7), *places they hold* (kinds), *where and when they exist* (reach, the era and
  world conditions), *how many* (members at world start), *kinds of members*.
- *What ordinary survivors say about them* and *what is actually true*.

### 2.7 Law (`## <name> (law)`)
- *The rule*, *who it binds* (members, visitors, everyone), *what it forbids or makes costly*,
  *how it is enforced*, *the punishment*, *how locals describe it*.

### 2.8 Person or playable character (`## <name> (person | playable character)`)
Addison's writer's bible is the model: the more of it a person has, the better they play. The
minimum the engine needs:
- *Identity*: name, aliases, age, sex, where they were born, what they did before the Fall and
  now, one line.
- *Body and looks*: height, weight, build, hair, eyes, skin, marks, what they wear; how they move
  under stress; a habit gesture.
- *Capability*: stats (1–10), skills with where each came from, trained reactions, tags.
- *Motive*: what they want, how they go after it, what they will and will not do, the inner
  conflict, the old wound, their risk tolerance.
- *Traits* (two or more), each with how it shows, what sets it off, what it costs, and an example.
- *Contradictions*, *decision priorities*, *silences*, *knowledge* (what they know, don't know,
  hide).
- *Voice*: how they sound, speech habits, three sample lines (low stakes, under pressure, at the
  limit), things they would never say, profanity, accent.
- *Temper*: how much it takes to crack them, how it comes out, how long they hold it.
- *Life*: routine, hopes, fears, secrets; *people* they know and what each is to them.
- For a playable character, also: the selection card, the start facts, the starting inventory,
  and the behaviour rules (approach, topics, risk, plans, distortion, pressure, knowledge limits,
  performance).

### 2.9 Canon event (`## <title> (canon event)`)
Something that happened and that minds remember — like "Addison and the Lurker".
- *When*: days since the Fall, or how long before a run can start ("any time after").
- *Where* (kinds of places, so any generated world can hold it).
- *Who was there* and *who else it touched*.
- *What happened* (the story itself is the depth text).
- *What each person knows afterwards* — and what they got wrong.
- *What it left*: injuries, items gained and lost, relationships, fears and triggers, routes
  known or compromised, open questions.
- *What is secret*, and from whom.

### 2.10 The meta layer (`## <name> (meta)`)
Codex, the Voice, Willis, the No Zone, Mr. Cheater Man.
- *What is true*; *what is never knowable*; *what happens to anyone who comes to know it*.
- *What they can do* and *what they never do*; *their register* (how they sound).
- *When they appear* (at death, in the console, never).

---

## 3. Questions the next document should answer

Found while reading the current documents against the engine (2026-09-26). Each one is a gap
the engine currently fills with a placeholder or leaves out.

**Lurkers**
- Becoming a Lurker, as an infection process (2.3): the chance per slash, every stage and its
  timing, what the victim notices and does, when the dead stop treating them as prey, where they
  go, how the change completes, how long a new Lurker stays a "newbie".
- The venom, as a condition (2.4): the bite, how fast it takes, how long it lasts, what the
  victim can still do and feel (the owner: paralysed, fully awake, feels everything), whether it
  ever wears off during feeding, whether anyone survives it.
- Engagement rules in numbers: what counts as "a weapon that's worth a shit", how long a stalk
  runs in the wild and inside a settlement, how often voices are used inside settlements
  ("sparingly").
- How many per region in each era, and how thin the old dead are in the Mature era (never zero).
- Nests, ranks and clans: how many, where, what each rank does in play.
- The Lurker tactics slots (20) and any tells.

**The world**
- The air strain in numbers: sleep lost, cold intolerance (at what temperature, what it does),
  how strongly people cluster.
- Tongue strips: who can still make them.
- The numbered quirk slots (idle loops, environmental reactions, pre-charge tells) — or say they
  stay empty.

**Codex and the meta layer**
- The Codex points: the escape, the inner monologue (true — the owner), the death horizon,
  sovereign offences and termination, Mr. Cheater Man.

**Addison**
- Her family at the Fall; how she got from Boston to the heat; the driving story (she was ten at
  the Fall); where her music came from; whether the stickered bag is her childhood backpack;
  handedness; how the first-year incident sits in her memory; when and where the three mega
  hordes she survived happened.
