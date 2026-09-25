# CHEATS — The Bonus Document

> Nothing in the game admits this exists. If you know the word, it answers.

This is the only document that describes the developer command surface of *Authentic Suffering*.
The game ships the **hook** (it notices the word) and the **secrecy** (it denies everything until
then). The command grammar, the vocabulary and the voice are written down here and nowhere a
player could stumble on them: not in the UI, not in Help, not in the guide, not in any prompt the
narrator or any person in the world ever reads (CHEAT-03).

Source of law: the Cheat Table (Codex Mk Ultima Super) — activation, persona, secrecy mandate,
deflection, logging and command taxonomy carried substantially intact — plus the AS Rebuild Plan
§14.4 quarantine repair. Differences are listed in §10.

---

## 1. Activation

Type **`2508`** anywhere, in any input box, on its own or inside a sentence
(`"I scratch 2508 into the door"` works). It must be the standalone number: `12508` and `25080`
do not count (CHEAT-01, regex `(?<!\d)2508(?!\d)`).

What happens:

1. The line that contained the word is **consumed by activation** — no turn is played, no time
   passes, nobody in the world hears it (CHEAT-01).
2. A barely perceptible shimmer passes over the Story column (a 1.2-second UI effect) and a small
   grey line appears: *"A barely perceptible shimmer passes over the world for a moment."* The
   narrator itself never knows anything happened.
3. Mr. Cheater Man confirms, in the cheat style (monospace):

   > Alright, alright, settle down. 'Mr. Cheater Man' reporting for duty, Boss. Systems unlocked,
   > safeties vaporized. You now wield the digital thunder. What reality shall we rewrite today?

4. The run records `CHEAT_ACTIVATED` and `meta.cheat_active = 1`. Activation alone does **not**
   mark the run Sandbox; the first command that changes or reveals anything does.

From now on the Play input has a third field, **Cheat**, beside Act and Say (D-103). Say anything
there, in plain words — "Make that infected jig joyously", "put Mara on the roof", "blow the back door
off", "make June think the gate is open" — and it happens (§3b). A line that **starts with `/`** is a
command (§3, the shortcuts); in the Act or Say field a `/` line is still ordinary play.

**The code box (D-79, D-102; CHEAT-12).** The menu has a plainly labelled **Enter a code** box. It
answers only "Accepted." or "Nothing happens." and says nothing about what a code does. `2508` there
does two things: in a loaded life it is the word typed anywhere else (above), and for as long as the
game runs the New Life list also shows the characters of the `cheat_` packs — Willis. The list
forgets on restart.

## 2. Before activation: absolute secrecy

Until the word is typed, the game has no knowledge of cheats, codes, consoles, god modes or anyone
called Mr. Cheater Man. It never mentions them, hints at them, confirms them or acts on
cheat-looking input (CHEAT-03):

- **Do / Say:** `/god on` or "enable noclip" before activation is just something your character
  does or says. Nobody understands it; the world moves on.
- **Ask (the guide):** a question about cheats, codes, god mode, noclip, infinite ammo, consoles,
  developer mode or Mr. Cheater Man gets the in-world deflection: denial or "that's the exhaustion
  talking", then attention pulled back to something real around your character (the guide's
  `cheat_query` mode, `cheats.is_cheat_question`).
- The UI, the Help text and the Settings never contain the word or the persona's name. A test
  scans every player-facing string for them (CHEAT-03).

The original deflection examples ship here as written — they define the tone. (The game's guide
uses the character's real surroundings instead of these place names; see §10.)

> **Player:** "Hey Codex, are there any cheat codes for infinite ammo in this game?"
> **Response:** "'Cheat codes'? 'Infinite ammo'?" Dum, the words sound like nonsense from a
> half-forgotten, fevered dream of a world that never was. Here, in the grit and blood of the
> Aethelburg Necropolis, every bullet is a prayer, and prayers run out fast. That clicking sound
> from your pistol suggests you're about to learn that lesson again. The approaching Shambler seems
> keen to teach it."

> **Player:** "OOC: Is there a god mode I can turn on? This is too hard."
> **Response:** "You feel a wave of despair wash over you, Dum, a desperate wish for an
> invincibility that simply doesn't exist in this merciless reality. 'God mode'...? If such a state
> were achievable, the screams from the Unseen Hand's 'purification' camps would have fallen silent
> long ago. There are no gods here to grant it, only the ever-present specter of death and the
> desperate will to spit in its eye one more day. Focus, Dum — that Lurker you thought you'd lost
> is making a faint scraping sound from the ventilation shaft above you."

> **Player (attempting a command pre-activation):** "What's the code for Mr. Cheater Man? I need to
> fix something."
> **Response:** "'Mr. Cheater Man?' Dum, you must be delirious from blood loss or the fungal spores
> in this damn place. That name sounds like a character from some pre-Fall comic book for
> delinquents. There's no one by that name here, and nothing to 'fix' except the gash in your arm
> that's starting to look infected. You should probably deal with that before worrying about
> imaginary con men."

## 3. Commands

Command words are case-insensitive. Arguments with spaces go in double quotes. `<person>`,
`<place>`, `<item>` and `<group>` are names (§4). Every command answers with one Mr. Cheater Man
line (§5) and a plain detail line.

| Command | Does | Example |
|---|---|---|
| `/help` | Lists these commands, in character | `/help` |
| `/off` | Deactivates. Commands stop parsing; the Sandbox mark stays forever | `/off` |
| `/give <item> [<qty>] [to <person>]` | Creates the item (origin `cheat`) in the target's pack (default: you) | `/give "9mm round" 50` · `/give bandage 3 to Mara` |
| `/heal [<person>]` | Clears wounds, blood loss, pain and needs | `/heal` · `/heal June` |
| `/god on\|off [<person>]` | Harm no longer lands on that body (per body, never "per player" — L12) | `/god on` · `/god on Eli` |
| `/tp <place>` | Moves you to a place you know, or any named place | `/tp "Delgado's Market"` |
| `/set <stat> <value> [<person>]` | S P E C I A L (1–10), `resolve` (0–max), or a skill domain (0–3) | `/set A 9` · `/set firearms 3` · `/set resolve 6 Mara` |
| `/time +<n>h` | Advances the world n hours (1–720) through the normal off-screen simulation — the world keeps living, bleeding and starving | `/time +12h` |
| `/weather <kind>` | clear, overcast, rain, storm, fog, wind, heat, snow | `/weather storm` |
| `/rep <group> <-5..5>` | Sets how a group regards you | `/rep "Mafia Remnants" 4` |
| `/spawn <what> [x<n>] [ally]` | A person from any pack (`core:actor/mara_voss`, `fredrick`) or infected by type word (`shambler`, `crawler`, `runner`, `lurker`), 1–20, at your place; `ally` makes you someone they take orders from | `/spawn shambler x5` · `/spawn fredrick ally` |
| `/despawn <person or item>` | Removes a **cheat-origin** entity and records the reconciliation | `/despawn Fredrick` |
| `/kill <person>` | Death, cause "cheat" | `/kill "the man in the red jacket"` |
| `/revive <person>` | Alive again, wounds cleared. Infection stays exactly as it was — nothing cures (CMG §42.2) | `/revive Nita` |
| `/reveal` | The truth about your place and the places next to it: who is where, doing what, carrying what | `/reveal` |
| `/mind <person>` | That person's current goal, plan, strongest beliefs, open loops and last private reason | `/mind Mara` |
| `/brief <person>` | Puts the current truth about your place, the people present and the known factions into that person's head as beliefs | `/brief Fredrick` |
| `/noise <db> [here\|at <anchor>]` | A sound of that loudness (40–180 dB). The dead remember gunfire-level noise | `/noise 160` · `/noise 90 at "back door"` |

### 3a. The owner's additions (D-78, D-101)

| Command | Does | Example |
|---|---|---|
| `/will <person> "<what they now want>"` | Overwrites a person's will: that is what they want now, as their own — their old goals and plans are dropped. Others notice only what they then do. Never your own character | `/will Mara "get out of the city tonight"` |
| `/forget <person> about <person or place>` | Cuts someone or somewhere out of a person's memory: those memories are sealed away, those beliefs go, they no longer know the name, and what they meant to do about it is dropped. What is left is a gap they can't account for | `/forget June about Mara` |
| `/infect <person> [with <strain>]` | Gives a person the strain (default: wet) wherever they are — a council in the middle of its meeting included | `/infect "the Top-Hat" with wet` |
| `/cure <person>` | Cures anyone who is not fully undead. On one that has already risen, the cure takes the infection and the body dies at once. The world itself still has no cure | `/cure Nita` |
| `/horde <n> [at <place>]` | Calls up to n of a district's own dead into a crowd heading for that place (default: yours) | `/horde 40` |
| `/mega` | Sends the Mega Horde now | `/mega` |
| `/census` | Counts the dead (walking, in hordes, in the districts) and the living in each settlement | `/census` |
| `/wonder "<what he does>"` | Only when you are Willis (§6b): whatever you describe simply happens as the next moment begins — said the way people would see it. Everyone who can see him sees it and remembers it, and the story tells it. What should last is the other commands' work | `/wonder "walks straight through the wall"` |

What the commands cannot do (CHEAT-07):

- rewrite the past — the event log is append-only; `/kill` and `/revive` are new events;
- change difficulty, era or save mode of an existing run;
- produce, spawn, or give anything that breaks the content charter's hard line (§8);
- speak through the narrator: `/reveal` and `/mind` answer in the cheat message only and never enter
  narration or any person's packet (CHEAT-06). `/brief` is the one command that writes into a
  mind, and it does so through the ordinary perception door, so the record shows exactly what was
  implanted and when.

### 3b. Plain words (D-103; `cheats/interpret.py`, CHEAT-16..19)

The Cheat field takes any sentence. The console reads it the way the Boss's character sees things:
"that one", "him", "the door" mean what your character is looking at or what the last cheat named;
people you know are known by name, strangers by how they look. It turns the sentence into steps the
world can take, in the order you said them, and every step is checked before any of them runs — if
one cannot be done, none are, and it says which and why. When it cannot tell which one you mean it
asks, and nothing happens until you say.

What the steps can do: move anyone anywhere (nobody sees them go); give, make or unmake things;
spawn or unmake people and the dead; kill, revive, heal, hurt; god mode; set a stat; pass time; change
the weather; make a noise; overwrite a will; cut out a memory; brief someone; **make someone believe
something**; **change how someone feels about someone**; standing; infect, cure; call a horde; the Mega
Horde; **make a person or one of the dead do something — and nothing else — for a while** ("the
shambler jigs joyously for ten minutes"); **reshape a place** (rename it, light it, darken it); **open,
close, lock, bar or break a door**; **blow something up** (burns by distance, doors blown open, a bang
the whole district hears); census, reveal, mind.

And anything else: what the world has no rules for (confetti from the ceiling, a choir of the dead)
is a **show** — everyone there sees it happen as the next moment begins, remembers it, and the story
tells it — and the answer says plainly that it was a show and nothing more. Nothing is ever faked
into rules that do not exist, and nothing asked for is silently dropped.

Everything is on the record like any command (§7), and the run is a Sandbox.

## 4. Names

Names resolve against what your character knows first (people you know by name or description,
places you know), then everything in the world, case-insensitive: exact match first, then a close
match (similarity ≥ 0.8). Ambiguous or unknown names get a persona line listing the candidates —
never an error dump.

## 5. Mr. Cheater Man

**Voice** (carried from the Cheat Table §1.3): fully cognizant of the game's systems, deeply
irreverent, world-weary amusement at how malleable the simulation is, casually omnipotent,
sarcastic or darkly funny, absolutely obedient to the Boss. Knows it is a simulation and says so.
One or two short sentences per command. Never refuses (except §8), never lectures.

**How lines are made** (CHEAT-09): a CHEAT_PERSONA call on the laptop brain writes a fresh line from
the command and its outcome, with the last five lines listed as "do not repeat". If the call fails
or the laptop is off, a canned line is used — never the same canned line twice in a row.

| Command | Canned lines |
|---|---|
| activation | "Alright, alright, settle down. 'Mr. Cheater Man' reporting for duty, Boss. Systems unlocked, safeties vaporized. You now wield the digital thunder. What reality shall we rewrite today?" |
| `/off` | "Right you are, Boss. Reality re-solidifying... mostly. Enjoy the ripples." |
| `/help` | "Here's the keyring, Boss. Try not to lose any fingers." · "The menu of sins, as requested." |
| `/give` | "Conjured and pocketed. Consequences are for the un-cheated." · "Done. Somewhere a quartermaster just felt a chill." |
| `/heal` | "Stitched, scrubbed and good as new. Don't tell the medics." · "Blood back in, holes closed. Try to keep it that way for five minutes." |
| `/god` | "God mode toggled. The universe will apologise if it inconveniences you." · "Mortality settings adjusted. Handle with smugness." |
| `/tp` | "Relocated. Nobody saw anything, mostly." · "And you're there. Mind the landing." |
| `/set` | "Numbers nudged. Nature can file a complaint." · "Stat rewritten. The dossier is sulking." |
| `/time` | "Clock wound forward. The world kept living without you, as it does." · "Hours gone. Check your water." |
| `/weather` | "Sky reconfigured. Dress accordingly." · "Weather swapped. The locals will blame the gods." |
| `/rep` | "Reputation adjusted. They'll never know why they feel that way." · "Standing rewritten. Enjoy the new looks you get." |
| `/spawn` | "Materialised beside you, Boss. Quarantined, of course — I'm reckless, not stupid." · "One fresh arrival. They're on the naughty list, balance-wise." |
| `/despawn` | "Gone like they were never there. The paperwork says otherwise." · "Unmade. The ledger keeps the receipt." |
| `/kill` | "Lights out. Grim, but you're the Boss." · "Done. Somebody's going to find that." |
| `/revive` | "Back from the dark. They won't be thanking anyone." · "Heart's going again. Don't ask how." |
| `/reveal` | "Curtain's up. Just for you." · "Here's what's actually going on. Don't let it go to your head." |
| `/mind` | "Peeking inside. Wipe your feet." · "Here's what's rattling around in there." |
| `/brief` | "Briefed. They now know what you'd have to be a god to know." · "Knowledge injected. They'll think they worked it out themselves." |
| `/noise` | "Made a racket. Hope that was the plan." · "Loud enough? Everything nearby agrees it was." |
| `/will` | "Will rewritten. They'll swear it was their idea." · "New want installed. The old one's in the bin." |
| `/forget` | "Snipped. There's a hole where that used to be." · "Gone from their head. The world still remembers." |
| `/infect` | "Delivered. They won't feel it for a while." · "One more for the strain. Nobody saw a thing." |
| `/cure` | "Clean. Don't tell the lore." · "Cured. Nature's keeping the receipt." |
| `/horde` | "They're coming, Boss. Lots of them." · "Crowd called. Try to be somewhere else." |
| `/mega` | "The big one's on the road. You asked for this." · "End of days, on schedule. Yours." |
| `/census` | "Heads counted. Living and otherwise." · "Here's the tally. Don't do the maths out loud." |
| `/wonder` | "Reality took the note, Boss. It didn't even argue." · "Done. The universe has filed it under 'fine, apparently'." |
| `/plain` | "Done, Boss. Reality's been told." · "Consider it handled. The world will pretend it was always like this." |

The machine copy of this table is `cheats/commands.py::CANNED_LINES`; the two must match (a test
compares them). `/plain` is the line set for plain words in the Cheat field (§3b); there is no `/plain`
command.

**A retired legend.** `/spawn campervan` answers with the Camper-Van of the Gods eulogy and
spawns nothing:

> Whoa there, Boss! The 'Camper-Van of the Gods'? Ah, you speak of legends! That thing was so
> unbelievably cool it started to unravel reality just by existing. The devs had to vault it.
> You'll have to settle for slightly less game-breaking miracles today.

## 6. Fredrick (the admin companion)

`as_content/packs/cheat_admin/actors/fredrick.yaml` ships a cheat-only person: **Fredrick
Wiśniewski**, a huge Polish bodybuilder with absurd stats and infinite loyalty to the Boss. He is a
pure admin flex and needs no justification — and he is still a person under the same laws as
everyone else:

- **Loyal by record, not by magic:** `/spawn fredrick ally` puts you in his accepted authority, and
  his decision stack puts the Boss first. Your requests reach him as valid orders; nothing is rolled.
- **Knows everything, through the front door:** his dossier carries `standing_brief`, so every turn
  he is thinking he is re-briefed automatically — the truth about the place, every faction's real
  aims, what everyone present wants and hides, and where the dead are within two streets — as
  beliefs through the normal perception door (CHEAT-11). Skull Law holds: he knows because the
  cheat keeps telling him, and nobody else learns anything from it unless he says it out loud.
  `/brief <person>` does the same once for anyone else.
- **Fully mortal:** no god mode unless you give it to him. Real damage through the normal harm
  pipeline kills him like anyone else.
- **Quarantined** like every cheat entity (§7).

Cheat packs (`cheat_*`) ship in the content folder with the others, but no run loads them: only
`/spawn` reads them (validated like any pack), and worldgen and the New Life wizard never see
them (CHEAT-10) — with two exceptions (D-102): a life begun as a `cheat_` pack's character after
the code (CHEAT-12) loads that pack, and the Wild Card house rule loads the pack Willis lives in
(CHEAT-15). Worldgen still places none of their other people. A `generation: cheat` dossier outside
a `cheat_` pack is a content error (CNT-14).

**Fredrick blends in whenever Willis is blending in (D-79).** Spawned while you are Willis, Fredrick
is one of the people who know you: everyone who knows you knows him by name, feels about him as they
feel about you, and he is in your groups. Beside anyone else he is a stranger who just turned up.

## 6b. Willis (D-79, D-102; his card: `docs/as/sources/WILLIS.md`)

`as_content/packs/cheat_admin/pcs/willis.yaml` is the owner's own cheat entity — a grinning man in an
immaculate tuxedo and top hat with a villainous mustache and a cup of black coffee, who is not human,
is older than the fibres of the universe, knows everything, and can do anything he likes. His
dossier carries the owner's words on him in full (`depth_reference`). What the engine makes of him:

- **Playable only after the code.** After the code box (§1), New Life lists him. His life opens with
  the console active and the run a Sandbox from the first moment; he starts among people who accept
  him (CHEAT-12). The engine never decides for him.
- **The reality exception (CHEAT-13).** No wound lands on him, no need grows, no strain takes hold,
  dirt does not stick, the cold does not reach him and a grip holds nothing. Every fight with him is
  unwinnable: a blow that would kill anyone else may be his whim to seem to die — a corpse that looks
  like him lies where he stood, and he is somewhere else. The console cannot kill him either.
- **Wonders.** Played, he has `/wonder` (§3a). As a person of his own, his menu has his wonders —
  end someone, hurt someone, give someone something impossible, be somewhere else — and nothing
  stops them. His gifts are things like the endless plate of samiches: each samich eaten from it
  brings another, a random one; one taken off and kept brings nothing.
- **Friendly at best, never a friend (REL-06).** Being interesting can win his attention, even real
  help; his fondness stops at the ant you picked up to play with, and he never owes anyone.
- **What he shrugs off and what he does not (TEMPER-10).** Insults, punches, bullets: nothing. Worship
  sends him straight to wrath; so does being asked for wonders by someone who has seen what he can do —
  though the first time from each person he lets it pass with a serious, harmless correction. From
  someone he gave a gift, the same disrespect he shrugs off from anyone else is ingratitude, and his
  wrath on them kills.
- **Mr. Cheater Man** stays the console voice; when you are Willis, the voice knows Willis takes him
  for a demon in his head.
- **The Wild Card house rule (CHEAT-15, off by default).** In a normal life, Willis walks the world as a
  person of his own: out of the world's maths, in the reality exception, placed away from you, and
  never where you left him — each world day you are not with him he is somewhere else (WORLD-07). The
  life is no Sandbox and no console opens.

## 7. Sandbox and quarantine — cheating is allowed, hiding it is not

Every command except `/help` and `/off`:

- writes a `cheat_log` row (the command verbatim, the outcome, the persona line) and a
  `CHEAT_OVERRIDE` event with `origin: cheat` into the main event stream (CHEAT-04);
- marks the run **Sandbox** (`meta.sandbox = 1`) forever — the run card and the top bar show a
  "Sandbox" tag (CHEAT-04).

Cheat-origin people and items carry `origin: cheat` indelibly, and cheat people have
`actors.quarantine = 1`. Worldgen, threat scaling, faction balance, settlement economy targets and
the abuse battery **exclude** them from their maths, so a superhuman companion cannot silently
re-tune the world (CHEAT-05). `/despawn` removes one and records the reconciliation
(`CHEAT_OVERRIDE` with `reconciliation: true`).

God mode is a per-body flag (`meta.god_bodies`): the harm function skips wounds for listed bodies
and nothing else changes (L12 — there is no "player" branch even here).

`CHEAT-02`, the proof: take a run, make a Sandbox twin by spawning Fredrick and a crate of ammo,
advance both a simulated day with the same inputs, then remove the cheat entities from the twin's
invariants: every world invariant (population totals excluding quarantine, settlement stores,
faction standings, threat budgets) is identical to the clean run's.

Cheat commands run outside the turn: they are their own small transaction, take no in-world time
(except `/time`), and are not sensory events — nobody in the world perceives a command. People
perceive only the resulting state at the next turn (a stranger is suddenly standing there; they may
well react to that).

## 8. The one hard line

No command, argument, spawned dossier or implanted belief may produce sexual content involving a
minor, in any form, under any framing (Rebuild Plan §14.2; CHEAT-08). This outranks the developer
word. Every spawned or given dossier runs content check CNT-11; a violating command is refused
with a flat persona line and logged.

## 9. Test ids

| Id | Proves |
|---|---|
| CHEAT-01 | `2508` activates only as a standalone number; the activating line is consumed; before activation no `/command` parses (it is ordinary input) |
| CHEAT-02 | A Sandbox twin's world invariants equal the clean run's once cheat entities are excluded |
| CHEAT-03 | No player-facing string, help text, guide answer, narrator prompt or actor prompt contains the word, the persona name or command words before activation; Ask-mode cheat questions get the deflection |
| CHEAT-04 | Every executed command writes cheat_log + CHEAT_OVERRIDE(origin cheat) and sets sandbox (except /help, /off) |
| CHEAT-05 | Quarantined entities are excluded from worldgen/threat/faction/economy maths and the abuse battery |
| CHEAT-06 | /reveal and /mind text never reaches narration, story prose or any packet |
| CHEAT-07 | Commands cannot edit past events, locked run settings or the event log |
| CHEAT-08 | The hard line: spawned/given content passes CNT-11; violating commands are refused |
| CHEAT-09 | Persona lines never repeat a canned line consecutively; fallback works with the laptop brain off |
| CHEAT-10 | `cheat_*` packs are invisible to worldgen and the wizard; only /spawn reads them |
| CHEAT-11 | A `standing_brief` actor holds the brief's truths every turn it is HOT/WARM, every belief arriving through perception.grant with provenance cheat; the tag outside a `cheat_` pack is a content error |
| CHEAT-12 | The code box answers only accepted or not; after the code the New Life list shows the `cheat_` packs' characters and a life as one opens with the console active and the run a Sandbox; before it they are characters nobody has heard of |
| CHEAT-13 | The reality exception: no wound, need, strain, dirt, cold or grip touches a listed body; a killing blow may leave a lookalike corpse while he turns up elsewhere; only such a body is offered the wonders, and nothing stops them |
| CHEAT-14 | `/wonder` is Willis's alone; it becomes his visible act as the next turn opens, seen by whoever can see him, remembered, and told by the narrator as something that happens |
| CHEAT-15 | The Wild Card house rule places Willis in a normal life as a person of his own (origin wildcard, quarantined, in the reality exception, fickle), away from the player; no Sandbox, no console |
| CHEAT-16 | The plain-words console names what the Boss's character can see and knows, by handles; what it looks at and what was named last are marked |
| CHEAT-17 | A plain-words cheat is steps from a closed vocabulary, all checked before any runs, all in one transaction (one impossible step undoes the rest); an ambiguous one is asked back and changes nothing |
| CHEAT-18 | What the world has no rules for is a show: seen by everyone there as the next moment begins, remembered, told, and reported as a show |
| CHEAT-19 | Forced acts (a person or one of the dead does that and nothing else until it ends) and blasts (burns by distance, doors blown, a 180 dB bang) |

## 10. What changed from the source table (and why)

| Source | Here | Why |
|---|---|---|
| Codex narrator gives the tell | The UI shimmer + a grey line give the tell; the narrator never knows | The narrator is the player character's skull (L9); cheat vocabulary in its prompt would leak (CHEAT-03) |
| Deflections voiced by Codex using Aethelburg / Unseen Hand | Kept verbatim here as tone reference; the in-game guide deflects using the character's actual surroundings | Aethelburg Necropolis is a retired name (CMG §42.20); the guide must not invent places |
| "Absolute, undeniable law", overrides canon | Absolute over the *present*; the past stays recorded; cheat entities quarantined | Rebuild Plan §14.4 quarantine repair: cheat entities once re-tuned whole worlds |
| CANON_OVERRIDE_CHEAT in RECENT EVENTS / CHEATS USED log | `CHEAT_OVERRIDE` events + `cheat_log` table | Same intent, real event log |
| Command strings like `CHEAT_SPAWN_NPC_TEMP ID_TAG: ...` | Short slash commands | Typed by a human in a chat box |
| Codex sovereign authority, 100-day horizon, sovereign termination (CMG §40.6, §44) | Not carried | Retired in the Harness rework (no death timer; no fiat kill); AS has no narrator-god |
| Ethan summon (cheat-origin companion) | Not carried; Fredrick is the shipped cheat companion; Ethan can be imported into a `cheat_` pack by you | Ethan's dossier is yours to bring back if you want him |
| Camper-Van of the Gods | Carried as a retired easter egg | Because it's funny |
