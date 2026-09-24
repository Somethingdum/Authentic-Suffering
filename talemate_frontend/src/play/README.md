# Play UI — human smoke checklist

This is the last step of the P8 gate (docs/as/13_BUILD_ORDER.md, P8). `tools/as/gate.py --phase 8`
has already passed: the protocol tests, the Play UI tests (vitest), the Talemate plugin test and
the upstream-diff check. This list covers what those tests cannot see: a real browser, real
models, your eyes. Go through §0–§6 once on the desktop after the P8 gate; §7 waits for P10 and §8
for P12. Tick each line in your own copy, then add "Play UI smoke checklist, P8 part — done <date>"
to the Human checklist in `docs/as/PROGRESS.md` (and the later parts when you do them).

If a line fails, write what you saw in `docs/as/SPEC_ISSUES.md` (what you did, what happened, what
you expected) and hand it back to the builder. Do not tick a line that "mostly" works.

The rule ids in brackets are what a failed line breaks; `docs/as/RULES.md` explains each one.

## 0. Before you start

- [ ] LM Studio is running on the desktop with Nemotron Cascade 2 30B-A3B loaded, and on the
      laptop with Nemotron 3.5 Lightning 30B-A3B loaded (LM Link on). `python tools/as/doctor.py --lanes`
      shows both lanes OK.
- [ ] Make a run to play (in P8 the New Life wizard does not exist yet): from the fork root, with
      Talemate's venv active, `as-engine new-scenario as_engine/tests/fixtures/scenarios/metal_fence.yaml`.
      It prints "Created run owen_marsh_… in …".
- [ ] Start Talemate the normal way (`start.bat`). Open **http://localhost:8082** (Talemate
      0.39.0's frontend port). Only this one tab: Talemate allows one frontend connection at a time.

## 1. Connect and Home

- [ ] The first screen is either Connect (if a model is not answering) or Home. There is no
      Talemate editor anywhere.
- [ ] On Connect, **Test** on each card reports "Working — answered in … s." or a plain reason.
      Stop the laptop's LM Studio server and test again: the card says it is not answering, in words,
      and **Continue** still works with only the Storyteller brain. Start it again. [UI-CLARITY-06]
- [ ] Open a second tab on the same address. It shows "The game is already open in another tab or
      window…" and does not keep reconnecting. Close it; the first tab still works.
- [ ] Home shows Continue (naming Owen Marsh, day 18, alive), New life, Your lives, Worlds, Your characters &
      world, Settings. Every button has words, not just an icon. [UI-CLARITY-03]
- [ ] New life and Worlds open a plain "not built yet" page with a Back button (P10 / P12 build them).

## 2. Play — the screen

- [ ] Top bar: your character's name, the day, the time with part of day and weather, one dot per
      model whose tooltip says "working" or "not answering". No "Sandbox" badge. [UI-CLARITY-04]
- [ ] "Where you are" lists the place, what you can see, the people here, ways out with their state
      in words, dangers you know about, and the noise level in words.
- [ ] Nowhere on the play screen (outside Developer mode) do you see: packet, affordance, percept,
      LOD, claim, intent, handle, lane, schema, token, stage, event, actor, dossier — or ids like
      `act_000123`. Check the story, the panels, the tooltips and any error. [UI-CLARITY-01, -02]
- [ ] Panel titles read exactly: Where you are · Your pack · Your body · People · Journal · Map.
      [UI-CLARITY-05]
- [ ] Nothing is shown only by colour: every coloured state also has a word. [UI-CLARITY-04]
- [ ] Resize the window to about 1000 px wide, then to phone width (~400 px): the layout changes as
      10_UI.md §2.5 says and nothing overlaps or scrolls sideways.

## 3. Play — turns

- [ ] **Do**: type something ordinary ("I check the back door"). While it runs, the progress bar
      shows friendly labels and elapsed seconds; **Stop** is visible until "Locking it in…". The
      narration arrives and reads as prose about what your character perceives.
- [ ] Press **Stop** on a second turn before "Locking it in…": the turn is cancelled, nothing in the
      world changed (same time on the clock), and you can type again. [PROTO-06]
- [ ] **Say** to someone in the room (pick them in "To:"): they answer in their own voice; a person
      in another room does not react to what they could not hear. [SKULL-01]
- [ ] **Ask** the guide a rules question ("how does bleeding work?"): the answer appears as a side
      note, the clock does not move, and nobody in the world reacts. [PROTO-07]
- [ ] Type something impossible for your character ("I fly over the fence"): you get a plain
      rejection banner with the reason (and a question if it is unclear), not a narrated failure.
- [ ] Suggestions are things your character could do right now ("Hide behind the counter"), never
      story prompts or plot choices. [UI-SUG-02]
- [ ] Clicking an item in **Your pack** shows its actions; clicking one fills the Do box ("Put away
      the …") and does nothing else until you send it.
- [ ] **Your body**, **People**, **Journal** and **Map** show only what your character knows. Nothing
      in them reveals something you did not see, hear or learn. [UI-SKULL-01]
- [ ] Play ten turns. No sentence, description or quoted line of yours repeats back at you across
      those turns (echo), and the story never puts words in your character's mouth you did not write
      (with "Say it my way" off). [ECHO-01, NARR-01]

## 4. Saving and loading

- [ ] Save (top bar) under a name; "Saved as “…”." appears. Close the tab, reopen
      http://localhost:8082: Home shows Continue with the character, the day and "alive"; Continue
      brings you back to the same moment.
- [ ] Reload the page in the middle of a long turn: the game reconnects to the running turn and
      shows its result. [PROTO-02]
- [ ] **Your lives** (Home) lists every life; Delete asks once ("Delete … story? This can't be undone.")
      and **Keep it** changes nothing. After a delete the run's folder is gone from `as_runs/` and the
      Play UI shows nothing of it. [RUN-12]

## 5. Settings, content, developer mode

- [ ] Settings → Models works like Connect. Gameplay shows only settings a running game may change;
      changing Scene length makes the next scene longer. Show dice "Off" removes the receipt at once.
- [ ] Your characters & world → Check it on the core pack reports "No problems found." A pack with a
      broken record gives lines like "actors/mara_voss.yaml — … needs at least 3 lines (it has 1)".
- [ ] Settings → Advanced → Developer mode on: the bottom drawer shows the steps of the last turn,
      each person's choice, what happened, the check bits and raw model traffic. Turn it off: every
      trace of it is gone from the play screen.
- [ ] Settings → Advanced → Open Workshop opens Talemate's own interface (`?ui=workshop`) in this
      tab; going back to the plain address returns to the Play UI.
- [ ] After a few turns, `as-engine replay owen_marsh_…` says every turn is the same — including one
      where you changed a Gameplay setting between turns. [DET-02, SET-01]

## 6. When something goes wrong

- [ ] With the laptop's LM Studio stopped, a turn still plays on the desktop alone and the story shows
      the notice "Your second model is offline; turns will be thinner until it is back."
- [ ] With both stopped, a turn is refused with a plain sentence telling you to start LM Studio; the
      clock does not move.

## 7. New life and worlds (after P10)

- [ ] Step 1 lists the playable characters as cards (name, one line, "Survives by", "Starts as",
      "Note").
- [ ] Step 2: difficulty, era, world detail each explain themselves in one or two plain sentences.
      An era that cannot fit the chosen character is disabled *with the reason shown*.
- [ ] Step 3: the house rules read as plain choices; "More options" shows the rest.
- [ ] Step 4 → **Build the world**: the progress screen shows a friendly label, a percentage and a
      time estimate that moves. Cancel returns to the wizard — with every choice you made still
      there — without leaving a half-made run.
- [ ] The loading bar while the world builds: every step of the plan is listed in order, the one it
      is on is lit, a plain label says what it is doing ("Writing the people down", with "2 of 12"
      while it waits on the models), and a line under it changes every couple of seconds — a joke
      about that step, never a hint about your world, and never one of the last three lines again.
- [ ] The same bar during a turn ("Your move": Reading your move → … → Saving), and — when you answer
      quickly, before the others have finished thinking over the last moment — "Everyone else
      catches up" first, counting what is left. It never names anyone or says how many people are
      thinking (Developer mode may).
- [ ] An era your character cannot live in is greyed out in step 2 with the reason ("Addison's story
      needs a world 9-11 years after the Fall."); a days-since-the-Fall number outside the range
      is refused with the range.
- [ ] Build it for real (Standard detail). It finishes and opens Play.
- [ ] Make a run in **Ironman**: there is no Save button and no Load; closing the tab and choosing
      Continue picks up at the latest autosave.

## 8. Death, imports, worlds, cheats (after P12)

- [ ] **Make one quickly** (New life step 1) produces a draft you can accept, edit or discard.
- [ ] Die (an Actually Hell run and a bad idea is quickest, or cheats on a Sandbox copy).
      The death screen shows the cause, your last turns and what contributed. "Show what you never
      saw" warns about spoilers first, then reveals it. In Ironman the screen says "This life is over.
      The world is still out there." and offers no load.
- [ ] **Worlds**: the world you built is listed; Export downloads a `.asworld` file; importing that
      file lists it again; "Start a new life here" opens New life with that world already chosen.
- [ ] Your characters & world: importing a small character file shows a plain report; turning a
      document into a record shows progress and a draft for review.
- [ ] Only if you are testing the bonus document: before activation, a line like `/give rifle` in Do
      is treated as something odd your character says or does — no cheat response. After activation
      (docs/as/CHEATS.md), the story shows the activation line in the cheat style, the top bar shows
      **Sandbox**, and cheat commands answer in the console style.
