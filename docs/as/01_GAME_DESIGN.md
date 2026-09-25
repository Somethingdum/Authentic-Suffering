# 01 — Game Design

## 1. The pitch

*Authentic Suffering* is a single-player survival RPG set years after an engineered infection
ended the old world. You play one person you chose or wrote yourself. Two local AI models play
everyone else and tell the story; a hard-coded engine keeps the rules, the dice, the bodies, the
clocks and the memory. **The AI is the Dungeon Master. The engine is the rulebook, the logbook and
the physics.** Neither is allowed to do the other's job.

Everybody dies. The only question is when, and whether anyone remembers why.

## 2. Pillars (each one is a mechanism, not a mood)

| Pillar | What the player feels | The mechanism that makes it true |
|---|---|---|
| **People, not NPCs** | Every person has their own mind, wants, grudges and voice, and can say no | Each Actor thinks in its own model call with only what it could know (Skull Law); code offers each body only what it could attempt; requests reach it as speech, never as orders (05) |
| **You only know what your body knows** | You hear half a sentence through a wall; you guess wrong | Audibility and sight are computed per listener; the narrator only sees the player character's percepts (04, 07) |
| **The world remembers** | A broken promise follows you for weeks; a gunshot draws the dead; the stain stays where she died | Every change is an event; beliefs, lessons, grudges, rumours and traces persist and decay by rule, not by forgetting (03, 06) |
| **It is dangerous for everyone** | Named characters die off-screen; you die from a wound you ignored | One death test for every body; no plot armour; off-screen mortality (07) |
| **Fair and legible** | After you die you can see the three choices that did it | Death summary from your own record; a post-death "show me everything" reveal (10) |
| **Easy to read, hard to master** | The screen always tells you where you are, what you carry, how hurt you are | A code-rendered Where-You-Are panel, inventory and body panels that never depend on the AI (10) |

## 3. What a turn looks like

1. You read the scene in the **Story** column and glance at **Where you are**, **Pack** and **Body**.
2. You type into one of three boxes:
   - **Do** — an action: *"I crouch behind the counter and watch the back door."*
   - **Say** — words your character speaks, exactly (or "say it my way": your idea, their words).
   - **Ask** — a question to the in-game guide, which answers from what your character knows and
     never costs a turn.
   Or you click one of the **suggestions** the engine derived from what your body can attempt.
3. The engine shows honest progress ("People decide…", "The world moves…"). A medium scene takes
   roughly 40–90 seconds with both machines running (measured, not promised — see 08 §Bench).
4. One uninterrupted scene appears. Dialogue in it is exactly what people actually said.
5. The side panels update: you may have lost blood, a door may now be barricaded, a person you
   trusted may now be listed as "doesn't look at you".

If you ask for something your body cannot do — shoot with no gun, climb with a broken leg, pick a
lock you have never seen — nothing is spent: the game tells you plainly why ("You're not holding a
gun.") and lets you choose again.

## 4. Choosing who you are

Every run starts by choosing a character:

- **From your packs.** Each playable character appears as a card — the format carried from the
  Codex Master Guide §61: *NAME — one-line identity / Survives by / Starts as / Note*. Addison
  Flores ships as a playable dossier (see `as_content/packs/core/pcs/addison_flores.yaml`).
- **Import.** Drop in a dossier file (YAML or Markdown), a SillyTavern/Chub character card (PNG or
  JSON, v2/v3), or a long document. The importer turns it into a draft and lists, in plain
  language, what is missing ("needs three voice lines: easy, under pressure, at the limit").
- **Quick make.** Name, age, look, what they did before, three skills, a flaw, a fear, a few items.
  Cascade writes the rest; you review it before playing.

Your character is processed exactly like every other person in the world (L12). Their dossier
shapes how your actions are carried out (manner), what options your body even has (skills and
nerve gate the menu), and — if you turn on **"say it my way"** — how your spoken ideas come out.
Your words never change *what* you do or *who* you do it to.

## 5. The world

Canon carried from the Codex Master Guide §42–43 and Lore v1.0:

- **The Fall.** A man-made pathogen complex escaped. **There is no cure and never will be.** Three
  layers: an *air strain* nearly everyone carries (corrupted sleep, cold intolerance, clustering
  for warmth, fixation), the *wet strain* passed by bites and saliva (a living-spreader phase of
  weeks, then collapse, death and rise), and *cold-start* rising of the unbitten dead after about
  three days.
- **The infected.** Shamblers (blind, sound-led, horribly strong hands), Crawlers (what is left
  when the legs are gone), Runners (fast, clumsy, tragically almost-present), and Lurkers — a
  living, thinking predator species that learns your routines and leaves messages. "Dead" is a
  claim, not a fact: false death and reanimation windows make every corpse a question.
- **People.** Survivors live in households and settlements with work, rations, laws, grudges and
  children. Canonical factions (Mafia Remnants ship in the core pack; the Ghosts are waiting for
  you to import your own corpus) have real doctrine: how they challenge strangers, treat the
  visibly sick, and punish theft. Survivor contamination culture — no shared bottles, tongue-strip
  assays at the gate, quarantine that never releases — is law in most places.
- **Eras.** Early (weeks to a year), Established (1–4 years), Mature (5+ years, default). The era
  changes who exists, what still works, and how people think (a *post-Fall-born* teenager has
  never seen a working hospital and does not believe in one).

## 6. People who live

Every Actor:

- **Thinks in their own skull.** Their model call contains only what reached them: exact words if
  they heard them clearly, fragments if they heard them through a wall, a tone if that is all.
- **Can only attempt what their body and training allow.** Code builds their menu first — an
  untrained shooter is never offered "aim for the head"; a terrified person at zero nerve is only
  offered flight, freezing, surrender, or shielding someone they love.
- **Decides for themselves.** When you ask them for something, they hear it as speech from someone
  with a standing *they* assign (a stranger's order is a demand). Their costs are in front of them:
  the task they would drop, the child asleep in the next room. They may agree, bargain, stall,
  lie, or refuse — and **a refusal is remembered**; asking again is friction, never a reroll.
- **Remembers their own version.** After every scene each Actor writes their own memory from their
  own perception. Two people remember the same night differently; one of them remembers it wrong.
- **Grows an inner life.** Memories can create goals, desires, grudges, fears, questions, plans and
  promises (each citing the moment that caused it). In quiet hours a background "reflection" pass
  lets them decide what they now want. Lessons change what they believe works.
- **Has a stable voice.** Three example lines in three moods, a "would never say" list and their own
  recent real lines, every time they decide — the writer's notes guide the people who write them,
  never the model. Nobody quotes your last sentence back at you (the echo ledger rejects it).
- **Has a public face and a private truth.** Deception is a sustained state that can be pierced.
- **Lives off-screen.** Shifts, meals, watch rotations, childcare, scavenging runs, arguments. Their
  relationships drift without you. They can die without you.

## 7. Danger and death

- **No hit points.** Wounds have anatomy, type, severity, bleeding rate and clocks. A severe wound
  untreated is critical in minutes; catastrophic bleeding kills in one to four. Nothing heals
  inside a scene. Pain, blood loss, thirst, hunger, sleep and cold stack into impairment, which
  removes options from your menu rather than secretly lowering numbers.
- **One death test for every body**, the player included, run whenever harm lands or a clock comes
  due. There is no protection for named characters during play.
- **The world is lethal off-screen too**: each person faces daily risk by difficulty and activity.
  Deaths leave traces and rumours.
- **The Doom** (D-106): the moment a death becomes certain — bleeding nothing can stop now, the
  wet strain's last minutes, or the killing blow itself — the world stops for the one who will die:
  the dust hangs, the lights go out, Willis wanders in to mock them and is taken by something out of
  the dark, and a voice with no name walks them through every cause that led here and tells them how
  long they have, never how. Nothing undoes it. Then the world moves again. Everybody dies this
  way, and nobody in the world knows why — what the world knows (D-107) is only that since the Fall
  most people start screaming a short while before they die. The talk usually breaks the mind:
  shattered, broken, or — rarely, for the strong — held; the broken can barely speak (their words
  come out in pieces) or bring themselves to do anything but hide, flee, freeze or wait. And the
  Voice is cruel: sometimes it comes at the bite, and the bitten live the strain's four weeks
  knowing — or can't take it, and end it (a check a day for everyone else's mind; the player decides
  for themselves, with a gun or a blade in hand, only at the end of their rope).
- **When you die**: an honest death scene, then a death screen with the cause, your last three
  turns and the choices that led there (from your own record). One button more — **"Show me
  everything"** — reveals the truth you never perceived: who was behind the wall, what they
  decided and why. Then: start a **new life in the same world** (your old body stays where it fell;
  people remember you), start fresh in the world as it was first generated, begin a new world, or
  load a save. In **Ironman** death is final for that run: no loading, no new life in it — only a
  fresh start in the same world's original state, or a new world.

## 8. The world remembers

- **Events are permanent.** Every change in the world is one event with a cause.
- **Mistakes spread.** The people who saw what you did form beliefs; rumours carry it (and bend it)
  to people who did not; factions keep a standing toward you; your broken promises cost trust
  with everyone who was owed.
- **Noise is memory.** A gunshot steers the infected toward where it happened.
- **Places keep scars.** Blood, broken doors, missing stock, graffiti, graves. A persistence lock
  keeps what matters (the stain where someone died, a dead companion's weapon where they fell).
- **Forgetting is diegetic.** Trivial detail fades; an unguarded item in a public place gets taken
  ("someone took it"); a place nobody visits for a month may change hands — each an event.
- **Your journal** lists promises you made and are owed, goals, rumours you heard (including
  about yourself), lessons, and the dead you know of.

## 9. Rules without clutter

One universal check: **target = attribute tier + skill + tag + situation − impairment −
resistance** (clamped 1–9), roll a d10, and the margin decides: **clean**, **success with a cost**,
**fail**, or **fail with a new problem**. A failed roll never hurts you by itself — harm always
comes from something real. Identity is never rolled: nobody's loyalty, consent or morality is a die
roll. Stealth uses a six-step ladder where the good play lives in the middle ("fleeting
suspicion", "heightened suspicion"). Turn on **Show dice** for a small receipt under the scene.

## 10. Time

Time is continuous. A turn is a decision, not a tick: "keep watching the door" advances the world
to the next thing that actually happens. Talking takes real seconds and does not freeze anyone;
the person counting cans keeps counting while you argue.

## 11. World generation

Pick **difficulty** (Bitch Mode, Easy, Normal, Realism, Actually Hell, Fuck You), **era**, and a
**world detail** level from "Gotta go to work soon" (about 3 minutes) to "I don't intend to use my
laptop much today" (about an hour). The generator runs the Codex Master Guide §61 parameter blocks,
contradiction table and plausibility gate, then builds zones, a causal history (every shortage and
feud traces to something that happened), factions, settlements, households, people, local law and
an opening pressure made of real placed threats. It never decides who betrays, dies or befriends
you. Your character arrives with a survival history of their own — real memories of how they lived
through the Fall. Every generated world is kept as a **world file**: start another life in it, or
export it and hand it to someone else.

## 12. Cheats (just in case)

There is a developer mode that nothing in the game admits exists. If you know the word, it answers.
See `CHEATS.md` (the bonus document). Cheating is allowed; hiding it is not: a cheated run is marked
**Sandbox** forever, and cheat-spawned people and items are quarantined from the world's balance.

## 13. Your content

Everything that makes a world — people, playable characters, factions, lore with a truth layer and
a belief layer, items, laws, buildings, infected variants, cascade rules — lives in **content
packs**: plain YAML/Markdown folders you can write by hand. A validator tells you exactly what is
missing in plain language. Big documents (like a faction bible) go through **dossier intake**:
Cascade reads it section by section and drafts the record; you review it before it becomes canon.

## 14. Honest limits

- **Local model quality is the ceiling.** The engine raises the floor (grammars, audits, lint),
  not the ceiling.
- **Turns take time**: roughly 40–90 s with both machines, longer in crowded scenes; the "Turn
  depth" setting trades depth for speed. If the laptop is off, the game still runs on one machine,
  slower and thinner, and tells you so.
- **Content volume is the long pole.** The core pack ships enough to play; a rich world wants your
  dossiers.
