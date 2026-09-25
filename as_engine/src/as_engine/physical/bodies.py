"""Bodies, wounds, needs, infection, death (P2). docs/as/07_RULES.md §Harm, §Needs, §Death.
Owner 'physical.bodies'. L12: every function here treats the PC exactly like any body; the words
'pc', 'player', 'is_pc', 'controller' are forbidden in this module (SYM-01, AST scan).
R = the store's RulesConfig (store.rules / tx.rules); H = R.harm, N = R.needs.

Wounds (HARM-01..06) — no hit points:
  A new wound (apply_harm) gets: bleed_pct_per_min = H.bleed_pct_per_min[severity];
  pain = H.pain_per_severity[severity]; function_loss = H.function_loss[severity] when
  ANATOMY_GROUP[anatomy] is a limb group (arm, hand, leg, foot), else 0; contamination from the
  WoundSpec; treatment '[]'; clotted 0; created_at = at; next_due_at = at + H.minor_clot_min
  minutes for a MINOR wound (its clot time), else NULL; cause_event = cause_event_id.
  Effective bleed of a wound = bleed_pct_per_min x the SMALLEST multiplier among its treatments
  (none -> 1.0): pressure H.pressure_mult, packing H.packing_mult, tourniquet H.tourniquet_mult,
  bandage H.bandage_mult, suture H.suture_mult; 'clean' does not change bleeding. A clotted or
  healed wound bleeds 0. Every MINOR wound clots at created_at + minor_clot_min minutes (treated
  or not): clotted = 1, next_due_at NULL.
  bodies.pain = min(6, sum of pain over unhealed wounds). Function loss is per wound.
  Healing (progress): a wound heals when it is treated (treatment non-empty) AND
  (now - created_at) >= H.heal_days_per_severity[severity] days x recovery factor, where
  recovery factor = 1 + (5 - recovery_slack) x 0.1 and recovery_slack = world_params
  sim.recovery_slack (5 when the run has no world_params row, e.g. scenarios):
  healed_at = the moment it qualified, pain and bleed stop counting. Nothing heals inside a scene
  because no scene lasts days.

Impairment (HARM-07) = clamp(pain // 2 + blood steps + needs steps, 0, H.impairment_max), where
  blood steps = the value of the highest H.impairment_from_blood_loss threshold <= blood_loss_pct
  (0 below the first) and needs steps = the value of the highest N.impairment_at_stage key <=
  max(thirst_stage, hunger_stage, fatigue_stage, cold_stage (F1c, LOOK-09)) (0 below 3). (Intoxication, concussion and
  exhaustion terms join this sum when their systems exist; until then they are 0.)
  bodies.impairment is rewritten whenever pain, blood loss or a need stage changes, by the event
  that changed it.

Capacity (``capacity``):
  conscious  = alive and awareness in (alert, awake, drowsy)
  mobile     = conscious and not restrained and NOT (both legs carry a wound with function_loss 2)
  can_run    = (H1) mobile and no unhealed wound on a leg or foot with function_loss >= 1 (a shot leg
               hobbles: you can walk, not run)
  hands_free = the number of hands (l, r) that hold nothing (no item in hand_l / hand_r) AND are
               not disabled; a hand is disabled when an unhealed wound on that side's arm or hand
               has function_loss 2 (ANATOMY_SIDE)
  can_speak  = conscious and no unhealed catastrophic neck wound
  impairment = bodies.impairment

Time (``progress``) integrates in steps of 60 000 ms from bodies.progressed_at to to_ms (the last
  step may be shorter) and sets progressed_at = to_ms. Per step, in this order:
  1. blood: each bleeding wound adds effective_bleed x (the part of the step it bled, in minutes)
     — a minor wound bleeds only until its clot time, then clots (WOUND_PROGRESS);
  2. needs (P10: only for bodies of kind human, lurker or animal that have a needs row — an infected
     body's needs never change): stage = min(6, max(0, floor(hours since last_drink/last_meal/
     last_sleep / the stage period))) (P9: a meal or drink may be later than a step's end — the
     settlement's daily draw — so a stage is never below 0)
     with periods N.thirst_stage_every_h (x (1 + (climate_heat - 5) x 0.08), climate_heat 5 when
     there are no world_params), N.hunger_stage_every_h, N.fatigue_stage_every_h; a changed stage
     -> NEED_STAGE {body_id, need, stage}; fatigue reaching 6 while conscious -> AWARENESS_CHANGE
     {body_id, awareness: 'asleep', from} with posture 'lying' (collapse; fatigue never kills);
     then (F1c) the condition over time (LOOK-08) and the cold (LOOK-09);
  3. infection: each infections row's stage = the last pathway stage whose starts_at_h <= hours
     since exposed_at; a change -> INFECTION_STAGE {body_id, pathway, stage};
  4. false death: an infected body whose bodies.false_dead_until <= step end and core_intact = 1
     -> REANIMATION {body_id}: awareness 'awake', posture 'standing', false_dead_until NULL,
     blood_loss_pct 0, and every unhealed wound gets clotted = 1 — the body rises with its wounds
     (their function loss stays), but they no longer bleed and no longer count as a trigger, so a
     risen body does not drop again from the wound that dropped it (world.infected adds the
     'injured' state when it next ticks, P10);
  5. the death test. A threshold crossed inside a step takes effect at that step's END, so the
     DEATH / AWARENESS_CHANGE event's ``at`` is the end of the step in which it was crossed.
     Inside progress the cause event of a blood-loss death is the ``cause_event`` of the unhealed
     wound with the highest bleed_pct_per_min (ties: lowest wound_id) — the attack that killed;
     need and infection deaths have cause_event_id NULL.
  The results must equal stepping minute by minute, but an implementation may jump over steps in
  which nothing can change (no bleeding wound, no stage or timer boundary) — a 6-hour off-screen
  tick must not cost 360 database round trips per body. (F1c: for a body LOOK-08/09 apply to, the
  weather and cold steps and the next day of grime are boundaries too.)
  Heal checks run once, at to_ms. Returned events are committed, in the order produced.
  The call ends with one physical.bodies event at to_ms that writes progressed_at (and pain /
  impairment when they changed): IMPAIRMENT_CHANGE {body_id, impairment} when impairment changed —
  that one is in the returned list — else WOUND_PROGRESS {body_id, change: 'clock'}, which is not.
  Bleeding within a step is one WOUND_PROGRESS {body_id, change: 'bleeding', blood_loss_pct}
  (not returned either); clotting and healing are WOUND_PROGRESS {body_id, wound_id, change:
  'clotted' | 'healed'} and ARE returned.

Death test (DEATH-01..05) runs whenever harm lands and at every progress step, for every body:
  alive kinds (human, lurker, animal):
    DEATH if blood_loss_pct >= H.death_at_blood_loss_pct (40)
       or an unhealed HEAD or NECK wound is catastrophic
       or thirst/hunger/cold/heat stage >= N.death_stage (6)
       or a 'wet' infection reached the pathway's death_at_h
    else AWARENESS_CHANGE to 'unconscious' (once) if blood_loss_pct >= H.unconscious_at_blood_loss_pct.
  infected (not lurker):
    true DEATH if an unhealed HEAD or NECK wound is catastrophic and of type gunshot, stab, crush
       or blunt (brainstem / upper-spine junction destroyed) -> bodies.core_intact = 0;
    FALSE_DEATH if any other unhealed catastrophic wound that is not clotted, or blood_loss_pct >=
       H.infected_false_death_at_blood_loss_pct (60), when not already false-dead:
       bodies.false_dead_until = at + range_int('infected', f'false_death:{body_id}', lo, hi) min,
       lo/hi = the type's reanimation_window_h (the type is infected_state.type_id, read-only
       here) converted to minutes (round(h x 60)); the body's
       awareness becomes 'unconscious' and posture 'lying' (it LOOKS dead — perception renders a
       still body); a type with reanimation_window_h null never false-dies (it truly dies).
  DEATH writes bodies: alive 0, dead_at = at, death_event = the cause event id (the HARM or
  progress-step trigger), awareness 'dead', posture 'lying'; payload {body_id, cause, cause_event_id}
  with cause in blood_loss | head_wound | neck_wound | thirst | hunger | cold | heat | infection |
  offscreen (P10: ``die``).
  DEATH-06 (fidelity C10, Actor v2 B5c: every wound that bled is a cause) a DEATH whose cause is
  blood_loss carries links (contracts.events.EventLink, role 'contributed', kernel.store STORE-12)
  to the cause_event of every wound of the body with healed_at NULL and bleed_pct_per_min > 0
  (clotted or not) whose cause_event names an event in the log and is not the DEATH's own
  cause_event_id — each once, by (created_at, wound_id). Any other DEATH has no links.
  P10 — the dead rise (INF-04, CMG §42.16): after the DEATH of a body of kind 'human', when it has
  no unhealed catastrophic head or neck wound, pathway = 'wet' when it has a 'wet' infections row
  whose pathway death_at_h has been reached, else 'cold_start'; (lo, hi) = that canon pathway's
  rise_after_death_h in minutes (round(h x 60)); kernel.clock.schedule(tx, dead_at +
  rng.range_int(tx, 'infected', f"rise:{body_id}", lo, hi) x 60 000, 'REANIMATION', body_id,
  {'body_id': body_id, 'pathway': pathway}, the DEATH event id) — its TIMER_SET is committed but not
  among the returned events — and the DEATH payload carries rise_pending: true (world.infected
  raises the body when the row comes due). Lurkers are alive
  and never rise; an infected body's true death ends it.
  FALSE_DEATH payload {body_id, false_dead_until}. A dead body never gets another death event.
  Death is a state result, never a dramatic decision. There is no protection for named bodies
  during play (worldgen protection is a different, worldgen-only rule).

D-106 — the Doom (DOOM-01..06). The owner: "by the point you got the message, there was no evading
it. No, nothing you have done or could do could evade it ... And that's how everybody dies." A
person — a body of kind human or lurker that is alive, has no dooms row, is not in the reality
exception (``excepted``) and not in god mode ('god_bodies') — is doomed at the first moment its
death is certain. The death test (above) checks it every time it runs, and ``progress`` at the start
of every step (a death inside a step would otherwise come before its doom):
DOOM-01 bleeding (the death test left the body alive): per unhealed wound that bleeds now, best
  care = min(the current treatment multiplier, harm.tourniquet_mult on a limb (ANATOMY_GROUP arm /
  hand / leg / foot), else harm.packing_mult) — the best anyone could do, at once. A minor wound
  counts only until its clot time (created_at + harm.minor_clot_min) and adds a fixed amount
  (its bleed x the minutes it has left to clot); every other wound bleeds at bleed_pct_per_min x
  that multiplier. to_lose = harm.death_at_blood_loss_pct - blood_loss_pct. When the non-minor
  best-care rate is > 0 and (to_lose - the minor amount) / that rate <= harm.doom_horizon_min
  minutes, the death is certain: kind 'bleeding', death_by = at + that time rounded up to the
  second (the latest it can come), expected_at = at + the same with the current rates (the course
  as it is; never after death_by), cause_event = the cause_event of the wound bleeding hardest now
  (ties: lowest wound_id).
DOOM-02 infection: a 'wet' infections row whose pathway death_at_h moment (exposed_at + death_at_h)
  is within harm.doom_infection_lead_min minutes after ``at``: kind 'infection', expected_at =
  death_by = that moment, cause_event = the row's cause_event.
DOOM-03 instant: the death test is about to kill the person and it has no dooms row: kind
  'instant', doomed_at = expected_at = death_by = at, cause_event = the death's cause, committed
  just before the DEATH.
DOOM-04 A doom commits DOOM {body_id, kind, expected_at, death_by, cause_event_id} (writer
  'physical.bodies', actor_id = body_id, cause_event_id = the death test's) inserting dooms
  {body_id, doomed_at = at, expected_at, death_by, kind, cause_event, turn_index}. For 'bleeding'
  and 'infection' the doomed then start screaming, and nobody ever learns why: NOISE {source_db:
  RulesConfig.infected.scream_db, kind 'screaming', text 'someone screaming', place_id / x_m / y_m:
  the body's point} (writer 'action.propagate', actor_id = the body, cause = the DOOM) — only when
  ``at`` is not before the world clock's now (a doom found in catch-up, at a moment already past,
  screams unheard: nothing may react in the past). It is not propagated here: a doom that lands in
  a wave is one of the wave's events (turn.pipeline S9-S11 draw the dead to it and let everyone
  hear it); one found in a body's progress at S12 is heard there (turn.pipeline) and draws nobody,
  because that window's timers are spent; mind.perception.grant(body, the DOOM, channel 'auditory',
  fidelity 'exact', text "You are screaming.", source None); force_act(body, 'screams', death_by
  + harm.doom_overdue_min minutes, origin 'sim') — a mind does nothing else until it dies
  (turn.cognition and world.infected obey forced acts; the player's body is not a mind, so the
  input still works, but a doomed player cannot tell anyone: turn.intake DOOM-07). No mind is
  ever told why (no belief, no claim): the doomed can no longer make words about it.
DOOM-05 Nothing undoes a doom (the console refuses to heal, cure or god-mode a doomed body:
  cheats.commands, rule DOOM-08). As a safety net that must never fire, a doomed body the death
  test finds alive at or after death_by + harm.doom_overdue_min minutes dies there of the doom's own
  cause ('infection' for an infection doom, else 'blood_loss'), after audit.log.repair(kind
  'degraded', rule 'DOOM-05', detail {body_id, death_by}) — a bug to fix, never a feature.
DOOM-06 Only the doomed know, and only in the frozen moment: the Doom scene is the player's alone
  (service.voice) and stands only in the story (bookkeeping, outside both state hashes); no event,
  percept, belief, claim or memory of anyone else says why a person screamed.
doomed(store, body_id) -> dict | None: the dooms row as a dict (None when there is none).

Treatment (``treat``): method in {'pressure','packing','tourniquet','bandage','suture','clean'};
  tourniquet only on a limb (ValueError otherwise); suture only on a minor or significant wound
  (ValueError otherwise); 'clean' lowers contamination by 1 (min 0). The method is appended to
  wounds.treatment (a JSON list; repeats allowed). Payload {body_id, wound_id, method, by_actor}.

P10 — bodies made during play, exposure, deaths nobody saw, and the dead that rise:
create(tx, *, kind, sex, age_years, height_cm, mass_kg, special, at, turn_index, origin,
       cause_event_id=None, awareness='awake', posture='standing', content_ref=None, looks=None) -> str
  body_id = tx.mint('act'). One MATERIALIZE {body_id, kind, source: origin} (writer
  'physical.bodies', event origin 'worldgen' when ``origin`` (the bodies.origin value) is
  'worldgen', else 'sim'; actor_id = body_id) inserting bodies {body_id, kind, content_ref, sex, age_years, age_band =
  contracts.common.age_band_for(age_years) (NULL without an age), height_cm, mass_kg, alive 1, awareness,
  posture, blood_loss_pct 0, pain 0, impairment 0, restrained 0, special (JSON), progressed_at = at,
  core_intact 1, origin} — and (F1a) looks = ``looks`` (a contracts.dossier.Looks) as canonical JSON
  of its model_dump(mode='json') with outfit [] (NULL when None; the outfit is items, dressed by
  physical.objects.dress), and for kind 'infected' grime 5, blood 3, gore 5 (the dead are filthy
  and caked in gore, LOOK-04; every other kind starts at 0), washed_at = at (F1c) — and, for kinds human, lurker and animal, needs {body_id, all stages 0,
  chill 0, last_drink_ms = last_meal_ms = last_sleep_ms = at}. origin in bodies.origin's CHECK values
  (ValueError otherwise). Returns body_id.
expose(tx, rng, body_id, pathway, exposure, at, cause_event_id, turn_index) -> Event | None
  (action.effects bite, world.infected.) The canon pathway record ``pathway`` (ValueError when it has
  no ``exposure`` key of that name). A dead body, or one that already has an infections row for that
  pathway -> None; (I1) so is a body whose kind is not 'human' or 'lurker': only people take the
  strain — the dead eat animals, and animals never turn (world.infected INF-18). infected = rng.chance(tx, 'infected', f"exposure:{body_id}:{cause_event_id}",
  record.exposure[exposure]). INFECTION_EXPOSURE {body_id, pathway, exposure, infected} (actor_id =
  body_id, cause as given) inserting, when infected, infections {body_id, pathway, exposed_at = at,
  stage = the record's first stage name, cause_event = cause_event_id, known_to_self 0}.
die(tx, rng, body_id, at, cause_event_id, turn_index, *, cause='offscreen') -> Event | None
  (a death with no wound to show for it — the P12 cheats; P10 has no death lottery any more.) A
  dead body -> None. Otherwise DEATH {body_id, cause, cause_event_id} written like any death
  (alive 0, dead_at, death_event, awareness 'dead', posture 'lying'), and the rise is scheduled
  as for every death above.
rise(tx, corpse_id, type_id, at, cause_event_id, turn_index) -> str   (world.infected.rise)
  A new body: create(kind 'infected', sex / age_years / height_cm / mass_kg from the corpse,
  special = {letter: (lo + hi) // 2} of the canon infected type, origin 'reanimation',
  cause_event_id, looks = looks_of(corpse) (F1a: the face people knew)) — the corpse stays a dead
  body (its history is its own); the new body is what got up. Returns the new body id.
  (world.infected moves it into the corpse's place and gives it the corpse's things.)
contagious(store, body_id) -> bool   (W1, D-77: from day three EVERY fluid of a host carries the
  strain — blood, saliva, mucus — and the dead's fluids too) True for a body of kind 'infected'
  (alive or destroyed: what comes out of them carries it), and for a living human or lurker with a
  'wet' infections row whose stage (stages()) has saliva_infectious; else False. Who touches their
  blood or has it in the eyes or mouth is exposed (action.effects treat_wound / strike_melee).
stages(store, body_id) -> list[tuple[str, InfectionStage]]   (what each infection is doing to the
  host now: mind.cues signs, the packet's and the narrator's felt lines, action.effects mouth
  contact, turn.cognition compulsion)
  Per infections row of the body, by pathway: (pathway, the canon pathway record's stage whose name
  is the row's stage — as ``progress`` last left it). No rows -> [].

F1a — how a body looks and what is on it (the owner: "never judge a book by its cover is a bold-faced
lie"; everyone and everything has a visual identity, and it helps people judge each other):
LOOK-01 bodies.looks holds the body's contracts.dossier.Looks WITHOUT its outfit (JSON; NULL = height
  and build are all anyone sees): what anyone can see — hair, facial hair, eyes, complexion, visible
  marks (where and what, never how). create(..., looks=None) writes it (the dossier's
  appearance.looks, or a scenario body's looks); rise copies the corpse's; the
  dossier's prose appearance fields are the person's own (mind.identity) and never describe them to
  anyone else.
  looks_of(store, body_id) -> Looks | None: the parsed column (outfit empty — what is worn is items,
  physical.objects.worn).
LOOK-04 Condition: bodies.grime / blood / gore (0..5) and wet (0..3) — what is on the body and its
  clothes; washed_at = when it was last washed (F1c).
  condition_of(store, body_id) -> BodyCondition(grime, blood, gore, wet, washed_at).
  soil(tx, body_id, *, grime=0, blood=0, gore=0, wet=0, source, at, cause_event_id, turn_index)
    -> Event | None: each value += its argument, clamped to its range (arguments may be negative);
    nothing changes -> None. Else BODY_CONDITION {body_id, grime, blood, gore, wet, source} (the new
    values; writer 'physical.bodies', actor_id = body_id, cause as given) updating bodies. ``source``
    is a short reason ('harm', 'rain', 'smeared', 'washed'). A new body starts at 0 everywhere, an
    infected one at grime 5, blood 3, gore 5 (create).
F1c (D-86) — what gets on people, what comes off, and the cold. C = RulesConfig().condition.
LOOK-07 Who gets bloodied: apply_harm, after the HARM and before the death test, soils the wounded
  body: blood += C.blood_from_wound[severity] (source 'harm', cause = the HARM; nothing when that is
  0; committed, not returned: apply_harm's list stays HARM then the death test's event). The rest is what people do (action.effects: a blow that opens someone splashes the one who
  struck; treating a wound, butchering and smearing yourself with the dead).
  wash(tx, body_id, *, full, at, cause_event_id, turn_index) -> Event | None   (action.effects
    wash) full: grime, blood and gore to 0, wet + 1 (max 3), washed_at = at, source 'washed'; not
    full (a wipe): grime - 1, blood - 2, gore - 2 (never below 0), wet + 1, washed_at unchanged,
    source 'wiped'. One BODY_CONDITION {body_id, grime, blood, gore, wet, source} (as soil) — also
    when nothing but wet changed; None only for no such body.
LOOK-08 Condition over time (P10; progress step 2): for a living body of kind 'human' whose looks
  are recorded (bodies.looks not NULL: a body the world has never dressed makes no claim about what
  time does to it), at each progress step [t, end]:
    unwashed  g = min(C.grime_unwashed_max, (end - washed_at) // (C.grime_every_h hours)); grime < g
              -> soil(grime = g - grime, source 'unwashed', at = end, cause None). (Days of no wash
              make anyone grimy; filthy takes dirt, not days.)
    weather   n = end // W - t // W (W = C.weather_step_min minutes in ms: the whole steps of the
              clock crossed); n >= 1: out in it — world.decay.wet(tx) and world.decay.exposed(the
              body's place) -> soil(wet = +n, blood = -n, gore = -n, source 'rain'): the rain soaks
              you and takes the blood and the gore off you (INF-14's camouflage washes away in the
              open); else wet > 0 -> soil(wet = -n, source 'dried').
  create gives every body washed_at = at (a new body starts clean).
LOOK-09 Cold (P10; progress step 2, after LOOK-08; the same bodies): warmth is
  physical.objects.warmth(body) (what they wear). cold_need(store, body_id, at) -> int = what the
  body's place and weather ask: base = C.cold_need[band], band 'cold' when world_params
  climate_heat <= 3, 'hot' when >= 8, else 'mild' (climate_heat 5 without world_params); in an
  exposed place (world.decay.exposed) base + 1 at night (kernel.clock.world_time(at).part_of_day
  'night' or 'late night'); indoors max(0, base - C.shelter); then + 1 when bodies.wet >= 2 (a
  soaked body loses its heat anywhere). A body LOOK-08 does not apply to -> 0.
  At each progress step: n = end // K - t // K (K = C.cold_step_min minutes in ms); n >= 1: d =
  cold_need(end) - warmth; chill' = needs.chill + n x d when d > 0, else max(0, needs.chill - n x
  C.warm_per_step); stage' = min(N.death_stage, chill' // C.chill_per_stage); chill' != chill ->
  NEED_STAGE {body_id, need: 'cold', stage: stage', chill: chill'} updating needs.chill and
  cold_stage. The cold stage counts toward impairment (HARM-07) and stage 6 is death by cold (the
  death test): naked outdoors on a mild night that is about twelve hours; in a cold country with
  the clothes soaked, a few.

P12 (D-79, D-102) — the reality exception (CHEAT-13; docs/as/sources/WILLIS.md: "reality does not
meaningfully resist him"). Per body, like god mode, never by who controls it:
excepted(store, body_id) -> bool: body_id is in meta 'reality_exception' (a JSON list; absent,
  empty or unreadable -> nobody).
grant_exception(tx, body_id, at, turn_index, *, origin, cause_event_id=None) -> Event | None
  Already listed -> None. Else SETTINGS_CHANGE {source: 'reality_exception', body_id} (writer
  'kernel.meta', event origin = ``origin``: 'cheat' in a life the code opened or a /spawn,
  'worldgen' for the Wild Card) upserting meta 'reality_exception' = the sorted list with it added.
For a body in the exception: apply_harm writes nothing and returns [] (a blow, a bite, a bullet
  may land; none of them has any say over it); progress moves only progressed_at (no bleeding, no
  need stage, no infection stage, no condition or cold step, no healing check, no death test);
  expose returns None and commits nothing; soil returns None (impossibly clean); cold_need is 0;
  die returns None; capacity counts no grip (restrained is ignored: contact happens, it restrains
  nothing). Everything else about the body — where it is, what it looks like, what it holds, who
  sees it — is ordinary, and every other body keeps every rule.
  Unwinnable (the owner: "every fight with Willis is unwinnable. Even if you win, it's because he
  thought it was more fun to let you think you did ... he may produce corpses, and respawn somewhere
  else"): a blow on him that would kill anyone else — severity 'catastrophic', or 'severe' to the
  head or neck — is, when rng.chance(tx, 'mind', f"decoy:{body}:{cause_event_id}", DECOY_CHANCE),
  his whim to seem to die: a new body (create: kind, sex, age, height, mass, special, looks and
  content_ref as his, origin = his) at his exact position, wearing fresh copies of what he wears
  (physical.objects.create, origin = his, holder slot 'worn'), dies of it (kill(tx, it, 'harm', at,
  T, rng, cause_event_id)); he is taken out of the place (physical.space.remove_body) and set down
  at the first anchor (none: the centre) of a top-level place drawn with rng.choice(tx, 'resolve',
  f"respawn:{body}:{cause_event_id}", every top-level place but his own, by place_id) — nobody sees
  where. apply_harm still returns []: the blow had no say over him.

P12 (D-103, CHEAT-19) — what the plain-words console can make a body do, and blasts:
force_act(tx, body_id, act, until_ms, at, turn_index, cause_event_id, *, origin='cheat') -> Event
  meta 'forced_acts' (a JSON object {body_id: {act, until}}) gains or replaces the body's entry:
  SETTINGS_CHANGE {source: 'forced_act', body_id, act, until} (writer 'kernel.meta', event origin
  ``origin``: 'cheat' for the console, 'sim' for the Doom's scream, DOOM-04).
forced(store, body_id, at) -> str | None: the body's act while at < until, else None.
  What obeys it: turn.cognition (a person under a forced act does exactly that this wave: a reflex
  of the core 'forced_act' def whose label is the act, seen as f"{Ref} {act}."), and
  world.infected.step (one of the dead under a forced act takes no step toward anything and bites no
  one: its step commits that act as its visible ACTION_START and comes back after R.step_min_s).
blast(tx, rng, at_id, size, at, turn_index, cause_event_id) -> list[Event]
  The point: a body id -> its position; a portal id -> its place_a side (anchor_a's point, else the
  centre of place_a); a place id -> its first anchor (by anchor_id), else its centre. R =
  BLAST_RADIUS_M[size] (small 3, large 8, huge 20). Every living body in that place (by body_id) at
  distance d from the point (its anchor's point, else its x/y): d <= R / 4 'catastrophic', <= R / 2
  'severe', <= R 'significant', else 'minor' for 'huge' only — one 'burn' wound through apply_harm
  (anatomy by rng.weighted(tx, 'cheats', f"blast:{body}:{at}", action.effects.CENTRE_MASS); god mode
  and the reality exception still hold). Every portal of the place whose anchor on this side lies
  within R (none: the portal counts as within R): physical.space.portal_change_event {damage 3,
  is_open 1, is_locked 0, barricade 0} (a wall or fence: damage 3 only). One NOISE (writer
  'action.propagate', origin 'cheat', place_id) {source_db 180, kind 'blast', text 'an explosion',
  place_id, x_m, y_m} at the point, then action.propagate.propagate(tx, [it], at, turn_index) (the
  district hears it and the dead come). Returns every event committed, in order.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..contracts.common import Anatomy, WoundSeverity, WoundType
from ..contracts.events import Event

if TYPE_CHECKING:
    from ..contracts.dossier import Looks
    from ..kernel.rng import Rng
    from ..kernel.store import Store, Tx


@dataclass(frozen=True)
class WoundSpec:
    anatomy: Anatomy
    type: WoundType
    severity: WoundSeverity
    contamination: int = 0


@dataclass(frozen=True)
class Capacity:
    mobile: bool
    hands_free: int
    can_speak: bool
    conscious: bool
    impairment: int
    can_run: bool = True   # H1: see capacity



import json as _json
import math as _math

from ..contracts.common import ANATOMY_GROUP, ANATOMY_SIDE, LIMB_GROUPS

STEP_MS = 60_000
MIN = 60_000


def _rules(s):
    return s.rules if getattr(s, "rules", None) is not None else s.store.rules


def _canon(s):
    return s.canon if getattr(s, "canon", None) is not None else s.store.canon


def _b(s, body_id):
    return dict(s.query_one("SELECT * FROM bodies WHERE body_id=?", (body_id,)))


def _wounds(s, body_id, unhealed=True):
    sql = "SELECT * FROM wounds WHERE body_id=?" + (" AND healed_at IS NULL" if unhealed else "") + " ORDER BY wound_id"
    out = []
    for r in s.query(sql, (body_id,)):
        d = dict(r)
        d["treatment"] = _json.loads(d["treatment"])
        out.append(d)
    return out


def _mult(H, w):
    m = {"pressure": H.pressure_mult, "packing": H.packing_mult, "tourniquet": H.tourniquet_mult,
         "bandage": H.bandage_mult, "suture": H.suture_mult}
    ms = [m[t] for t in w["treatment"] if t in m]
    return min(ms) if ms else 1.0


def _eff_bleed(H, w):
    if w["clotted"] or w["healed_at"] is not None:
        return 0.0
    return w["bleed_pct_per_min"] * _mult(H, w)


def _params(s):
    r = s.query_one("SELECT params_json FROM world_params WHERE id=1")
    if r is None:
        return {"climate_heat": 5, "recovery_slack": 5}
    d = _json.loads(r[0])
    return {"climate_heat": d["a"]["climate_heat"], "recovery_slack": d["sim"]["recovery_slack"]}


def _impairment_from(R, pain, blood, needs):
    H, N = R.harm, R.needs
    blood_steps = 0
    for th, v in sorted(H.impairment_from_blood_loss):
        if blood >= th:
            blood_steps = v
    need_steps = 0
    mx = max(needs) if needs else 0
    for k, v in sorted(N.impairment_at_stage.items()):
        if mx >= int(k):
            need_steps = v
    return max(0, min(H.impairment_max, pain // 2 + blood_steps + need_steps))


def _needs_of(s, body_id):
    r = s.query_one("SELECT thirst_stage, hunger_stage, fatigue_stage, cold_stage FROM needs WHERE body_id=?", (body_id,))
    return list(r) if r is not None else [0, 0, 0, 0]


def impairment(store: "Store | Tx", body_id: str) -> int:
    b = _b(store, body_id)
    return _impairment_from(_rules(store), b["pain"], b["blood_loss_pct"], _needs_of(store, body_id))


def is_alive(store: "Store | Tx", body_id: str) -> bool:
    return _b(store, body_id)["alive"] == 1


def _wound_values(R, spec_anatomy, spec_type, severity, contamination, at, cause, treatment=()):
    H = R.harm
    grp = ANATOMY_GROUP[str(spec_anatomy)]
    return {"anatomy": str(spec_anatomy), "type": str(spec_type), "severity": str(severity),
            "bleed_pct_per_min": H.bleed_pct_per_min[str(severity)], "pain": H.pain_per_severity[str(severity)],
            "contamination": contamination, "function_loss": H.function_loss[str(severity)] if grp in LIMB_GROUPS else 0,
            "cause_event": cause, "treatment": list(treatment), "clotted": 0, "created_at": at,
            "next_due_at": at + int(H.minor_clot_min * MIN) if str(severity) == "minor" else None, "healed_at": None}


def apply_harm(tx: "Tx", body_id: str, wound: WoundSpec, at: int, cause_event_id: str,
               turn_index: int, rng: "Rng") -> list[Event]:
    """HARM event inserting the wound (+ pain/impairment update) then the death test (rng is
    needed for a false-death draw). Returns the committed events (HARM, and possibly
    AWARENESS_CHANGE / DEATH / FALSE_DEATH). (P12, CHEAT god mode) A body listed in meta
    'god_bodies' takes no wound: nothing is written and [] is returned (L12: per body).
    actor_id (event and payload) = the cause event's actor_id when that actor is a human body,
    else null (infected bites, animals, falls).
    HARM payload (cascades filter on it): {wound_id, body_id, actor_id (null for infected/animals),
    anatomy, anatomy_group ('head'|'neck'|'torso'|'arm'|'hand'|'leg'|'foot'), type, severity,
    function_loss, bleed_pct_per_min, contamination}. (F1c LOOK-07: then the wounded body's blood,
    a BODY_CONDITION committed right after the HARM and NOT in the returned list.)"""
    from ..contracts.events import Event, EventType, WriteOp, WriteRecord
    g = tx.query_one("SELECT value FROM meta WHERE key='god_bodies'")
    if g is not None and body_id in _god_list(g[0]):
        return []
    if excepted(tx, body_id):                 # D-102: no say over him — and he may play dead
        _decoy(tx, body_id, wound, at, cause_event_id, turn_index, rng)
        return []
    R = _rules(tx)
    wid = tx.mint("wnd")
    vals = _wound_values(R, wound.anatomy, wound.type, wound.severity, wound.contamination, at, cause_event_id)
    b = _b(tx, body_id)
    pain = min(6, sum(w["pain"] for w in _wounds(tx, body_id)) + vals["pain"])
    imp = _impairment_from(R, pain, b["blood_loss_pct"], _needs_of(tx, body_id))
    cause = tx.query_one("SELECT actor_id FROM events WHERE event_id=?", (cause_event_id,)) if cause_event_id else None
    attacker = cause[0] if cause else None
    if attacker:
        k = tx.query_one("SELECT kind FROM bodies WHERE body_id=?", (attacker,))
        if k is None or k[0] != "human":
            attacker = None
    ev = tx.commit_event(Event(type=EventType.HARM, writer="physical.bodies", at=at, turn_index=turn_index,
        actor_id=attacker, target_ids=[body_id], cause_event_id=cause_event_id,
        writes=[WriteRecord(op=WriteOp.INSERT, table="wounds", values={"wound_id": wid, "body_id": body_id, **vals}),
                WriteRecord(op=WriteOp.UPDATE, table="bodies", key={"body_id": body_id}, values={"pain": pain, "impairment": imp})],
        payload={"wound_id": wid, "body_id": body_id, "actor_id": attacker, "anatomy": vals["anatomy"],
                 "anatomy_group": ANATOMY_GROUP[vals["anatomy"]], "type": vals["type"], "severity": vals["severity"],
                 "function_loss": vals["function_loss"], "bleed_pct_per_min": vals["bleed_pct_per_min"],
                 "contamination": vals["contamination"]}))
    out = [ev]
    add = R.condition.blood_from_wound.get(vals["severity"], 0)
    if add:
        soil(tx, body_id, blood=add, source="harm", at=at, cause_event_id=ev.event_id, turn_index=turn_index)
    d = death_test(tx, body_id, at, turn_index, rng, ev.event_id)
    if d is not None:
        out.append(d)
    return out


def _rise_pathway(tx, body_id, at):
    """P10: None when the body cannot rise; else the pathway it rises by."""
    b = _b(tx, body_id)
    if b["kind"] != "human":
        return None
    for w in _wounds(tx, body_id):
        if w["severity"] == "catastrophic" and ANATOMY_GROUP[w["anatomy"]] in ("head", "neck"):
            return None
    pw = _canon(tx).find("pathway", "wet")
    for inf in tx.query("SELECT * FROM infections WHERE body_id=? AND pathway='wet'", (body_id,)):
        if pw.death_at_h is not None and (at - inf["exposed_at"]) >= pw.death_at_h * 3_600_000:
            return "wet"
    return "cold_start"


def _god_list(raw):
    import json as _json
    try:
        return set(_json.loads(raw or "[]"))
    except (ValueError, TypeError):
        return set()


DECOY_CHANCE = 0.5


def _decoy(tx, body_id, wound, at, cause_event_id, turn_index, rng):
    from ..physical import objects, space
    grp = ANATOMY_GROUP[str(wound.anatomy)]
    sev = str(wound.severity)
    if not (sev == "catastrophic" or (sev == "severe" and grp in ("head", "neck"))):
        return
    if not rng.chance(tx, "mind", f"decoy:{body_id}:{cause_event_id}", DECOY_CHANCE):
        return
    b = _b(tx, body_id)
    pos = tx.query_one("SELECT place_id, anchor_id, x_m, y_m FROM positions WHERE body_id=?", (body_id,))
    if pos is None:
        return
    import json as _json
    special = b["special"] if isinstance(b["special"], dict) else _json.loads(b["special"] or "{}")
    corpse = create(tx, kind=b["kind"], sex=b["sex"], age_years=b["age_years"], height_cm=b["height_cm"], mass_kg=b["mass_kg"],
                    special=special, at=at, turn_index=turn_index, origin=b["origin"], cause_event_id=cause_event_id,
                    content_ref=b["content_ref"], looks=looks_of(tx, body_id))
    space.place_body(tx, corpse, pos[0], pos[1], pos[2], pos[3], at, cause_event_id, turn_index)
    item_origin = b["origin"] if b["origin"] in objects.ORIGINS else "cheat"
    for (ref,) in [tuple(r) for r in tx.query("SELECT def_ref FROM items WHERE holder_body=? AND holder_slot='worn' ORDER BY item_id",
                                              (body_id,))]:
        objects.create(tx, ref, 1, objects.Holder("body", corpse, "worn"), item_origin, {}, at, cause_event_id, turn_index)
    kill(tx, corpse, "harm", at, turn_index, rng, cause_event_id=cause_event_id)
    places = [r[0] for r in tx.query("SELECT place_id FROM places WHERE parent_id IS NULL AND place_id != ? ORDER BY place_id",
                                     (pos[0],))]
    if not places:
        return
    to = rng.choice(tx, "resolve", f"respawn:{body_id}:{cause_event_id}", places)
    space.remove_body(tx, body_id, at, cause_event_id, turn_index)
    a = tx.query_one("SELECT anchor_id, x_m, y_m FROM anchors WHERE place_id=? ORDER BY anchor_id LIMIT 1", (to,))
    if a is not None:
        space.place_body(tx, body_id, to, a[0], a[1], a[2], at, cause_event_id, turn_index)
    else:
        p = tx.query_one("SELECT width_m, depth_m FROM places WHERE place_id=?", (to,))
        space.place_body(tx, body_id, to, None, p[0] / 2, p[1] / 2, at, cause_event_id, turn_index)


BLAST_RADIUS_M: dict[str, float] = {"small": 3.0, "large": 8.0, "huge": 20.0}


def force_act(tx: "Tx", body_id: str, act: str, until_ms: int, at: int, turn_index: int,
              cause_event_id: str | None, *, origin: str = "cheat") -> "Event":
    import json as _json

    from ..contracts.events import Event, EventType, WriteOp, WriteRecord
    r = tx.query_one("SELECT value FROM meta WHERE key='forced_acts'")
    try:
        cur = _json.loads(r[0]) if r is not None and r[0] else {}
    except (TypeError, ValueError):
        cur = {}
    cur[body_id] = {"act": act, "until": until_ms}
    return tx.commit_event(Event(type=EventType.SETTINGS_CHANGE, writer="kernel.meta", origin=origin, at=at,
                                 turn_index=turn_index, cause_event_id=cause_event_id,
                                 payload={"source": "forced_act", "body_id": body_id, "act": act, "until": until_ms},
                                 writes=[WriteRecord(op=WriteOp.UPSERT, table="meta", key={"key": "forced_acts"},
                                                     values={"key": "forced_acts", "value": _json.dumps(cur, sort_keys=True)})]))


def forced(store: "Store | Tx", body_id: str, at: int) -> "str | None":
    import json as _json
    r = store.query_one("SELECT value FROM meta WHERE key='forced_acts'")
    if r is None or not r[0]:
        return None
    try:
        e = _json.loads(r[0]).get(body_id)
    except (TypeError, ValueError, AttributeError):
        return None
    return e["act"] if e and at < e["until"] else None


def blast(tx: "Tx", rng: "Rng", at_id: str, size: str, at: int, turn_index: int, cause_event_id: str | None) -> list:
    from ..action.effects import CENTRE_MASS
    from ..action.propagate import propagate
    from ..contracts.events import Event, EventType
    from ..physical import space
    R = BLAST_RADIUS_M[size]
    if at_id.startswith("act_"):
        p = tx.query_one("SELECT place_id, x_m, y_m FROM positions WHERE body_id=?", (at_id,))
        place, x, y = p[0], p[1], p[2]
    elif tx.query_one("SELECT 1 FROM portals WHERE portal_id=?", (at_id,)) is not None:
        pr = tx.query_one("SELECT place_a, anchor_a FROM portals WHERE portal_id=?", (at_id,))
        place = pr[0]
        a = tx.query_one("SELECT x_m, y_m FROM anchors WHERE anchor_id=?", (pr[1],)) if pr[1] else None
        if a is None:
            a = [v / 2 for v in tx.query_one("SELECT width_m, depth_m FROM places WHERE place_id=?", (place,))]
        x, y = a[0], a[1]
    else:
        place = at_id
        a = tx.query_one("SELECT x_m, y_m FROM anchors WHERE place_id=? ORDER BY anchor_id LIMIT 1", (place,))
        if a is None:
            a = [v / 2 for v in tx.query_one("SELECT width_m, depth_m FROM places WHERE place_id=?", (place,))]
        x, y = a[0], a[1]
    out = []
    for (b, bx, by) in [tuple(r) for r in tx.query("SELECT b.body_id, q.x_m, q.y_m FROM bodies b JOIN positions q ON q.body_id=b.body_id "
                                                   "WHERE q.place_id=? AND b.alive=1 ORDER BY b.body_id", (place,))]:
        d = ((bx - x) ** 2 + (by - y) ** 2) ** 0.5
        sev = ("catastrophic" if d <= R / 4 else "severe" if d <= R / 2 else "significant" if d <= R
               else "minor" if size == "huge" else None)
        if sev is None:
            continue
        anat = rng.weighted(tx, "cheats", f"blast:{b}:{at}", list(CENTRE_MASS))
        out += apply_harm(tx, b, WoundSpec(anat, "burn", sev, 0), at, cause_event_id, turn_index, rng)
    for (pid, kind, pa, aa, ab) in [tuple(r) for r in tx.query("SELECT portal_id, kind, place_a, anchor_a, anchor_b FROM portals "
                                                               "WHERE place_a=? OR place_b=? ORDER BY portal_id", (place, place))]:
        anc = aa if pa == place else ab
        pt = tx.query_one("SELECT x_m, y_m FROM anchors WHERE anchor_id=?", (anc,)) if anc else None
        if pt is not None and ((pt[0] - x) ** 2 + (pt[1] - y) ** 2) ** 0.5 > R:
            continue
        ch = {"damage": 3} if kind in ("wall", "fence") else {"damage": 3, "is_open": 1, "is_locked": 0, "barricade": 0}
        out.append(space.portal_change_event(tx, pid, ch, at, None, cause_event_id, turn_index))
    noise = tx.commit_event(Event(type=EventType.NOISE, writer="action.propagate", origin="cheat", at=at, turn_index=turn_index,
                                  place_id=place, cause_event_id=cause_event_id,
                                  payload={"source_db": 180, "kind": "blast", "text": "an explosion", "place_id": place,
                                           "x_m": x, "y_m": y}))
    out.append(noise)
    out += propagate(tx, [noise], at, turn_index)
    return out


def excepted(store: "Store | Tx", body_id: str) -> bool:
    r = store.query_one("SELECT value FROM meta WHERE key='reality_exception'")
    return r is not None and body_id in _god_list(r[0])


def grant_exception(tx: "Tx", body_id: str, at: int, turn_index: int, *, origin: str,
                    cause_event_id: str | None = None) -> "Event | None":
    import json as _json

    from ..contracts.events import Event, EventType, WriteOp, WriteRecord
    r = tx.query_one("SELECT value FROM meta WHERE key='reality_exception'")
    listed = _god_list(r[0]) if r is not None else set()
    if body_id in listed:
        return None
    return tx.commit_event(Event(type=EventType.SETTINGS_CHANGE, writer="kernel.meta", origin=origin, at=at,
                                 turn_index=turn_index, cause_event_id=cause_event_id,
                                 payload={"source": "reality_exception", "body_id": body_id},
                                 writes=[WriteRecord(op=WriteOp.UPSERT, table="meta", key={"key": "reality_exception"},
                                                     values={"key": "reality_exception",
                                                             "value": _json.dumps(sorted(listed | {body_id}))})]))


def _clock_only(tx, body_id, b, to_ms, turn_index):
    from ..contracts.events import Event, EventType, WriteOp, WriteRecord
    if to_ms > b["progressed_at"]:
        tx.commit_event(Event(type=EventType.WOUND_PROGRESS, writer="physical.bodies", at=to_ms, turn_index=turn_index,
                              target_ids=[body_id], payload={"body_id": body_id, "change": "clock"},
                              writes=[WriteRecord(op=WriteOp.UPDATE, table="bodies", key={"body_id": body_id},
                                                  values={"progressed_at": to_ms})]))
    return []


def kill(tx: "Tx", body_id: str, cause: str, at: int, turn_index: int, rng: "Rng", *,
         cause_event_id: str | None = None, extra: dict | None = None) -> Event:
    """P12 (the cheat /kill, /cure of a risen body; any code that must end a life outright): the
    DEATH the death test commits — alive 0, dead_at, death_event, awareness 'dead', posture 'lying'
    (plus ``extra`` columns, e.g. core_intact 0 for a true death), payload {body_id, cause,
    cause_event_id} and the rise that follows for an infected body (DEATH-01..05)."""
    return _death_ev(tx, body_id, at, turn_index, cause, cause_event_id, extra=extra, rng=rng)


def _death_ev(tx, body_id, at, turn_index, cause, cause_event_id, extra=None, rng=None):
    from ..contracts.events import Event, EventType, WriteOp, WriteRecord
    pathway = _rise_pathway(tx, body_id, at) if rng is not None else None
    vals = {"alive": 0, "dead_at": at, "death_event": cause_event_id, "awareness": "dead", "posture": "lying"}
    if extra:
        vals.update(extra)
    payload = {"body_id": body_id, "cause": cause, "cause_event_id": cause_event_id}
    if pathway is not None:
        payload["rise_pending"] = True
    links = []
    if cause == "blood_loss":
        from ..contracts.events import EventLink
        seen = set()
        for w in tx.query("SELECT cause_event FROM wounds WHERE body_id=? AND healed_at IS NULL AND bleed_pct_per_min > 0 "
                          "ORDER BY created_at, wound_id", (body_id,)):
            ce = w[0]
            if ce in seen or ce == cause_event_id or tx.query_one("SELECT 1 FROM events WHERE event_id=?", (ce,)) is None:
                continue
            seen.add(ce)
            links.append(EventLink(event_id=ce, role="contributed"))
    ev = tx.commit_event(Event(type=EventType.DEATH, writer="physical.bodies", at=at, turn_index=turn_index,
        target_ids=[body_id], cause_event_id=cause_event_id, links=links,
        writes=[WriteRecord(op=WriteOp.UPDATE, table="bodies", key={"body_id": body_id}, values=vals)], payload=payload))
    if pathway is not None:
        from ..kernel import clock
        pw = _canon(tx).find("pathway", pathway)
        lo, hi = round(pw.rise_after_death_h[0] * 60), round(pw.rise_after_death_h[1] * 60)
        mins = rng.range_int(tx, "infected", f"rise:{body_id}", lo, hi)
        clock.schedule(tx, at + mins * MIN, "REANIMATION", body_id, {"body_id": body_id, "pathway": pathway}, ev.event_id)
    return ev


def death_test(tx: "Tx", body_id: str, at: int, turn_index: int, rng: "Rng",
               cause_event_id: str | None) -> Event | None:
    from ..contracts.events import Event, EventType, WriteOp, WriteRecord
    R = _rules(tx)
    H, N = R.harm, R.needs
    b = _b(tx, body_id)
    if not b["alive"]:
        return None
    ws = _wounds(tx, body_id)
    cat = [w for w in ws if w["severity"] == "catastrophic"]
    headneck = [w for w in cat if ANATOMY_GROUP[w["anatomy"]] in ("head", "neck")]
    if b["kind"] == "infected":
        core = [w for w in headneck if w["type"] in ("gunshot", "stab", "crush", "blunt")]
        if core:
            return _death_ev(tx, body_id, at, turn_index, "head_wound" if ANATOMY_GROUP[core[0]["anatomy"]] == "head" else "neck_wound",
                             cause_event_id, {"core_intact": 0})
        live_cat = [w for w in cat if not w["clotted"]]
        if (live_cat or b["blood_loss_pct"] >= H.infected_false_death_at_blood_loss_pct) and b["false_dead_until"] is None:
            st = tx.query_one("SELECT type_id FROM infected_state WHERE body_id=?", (body_id,))
            t = _canon(tx).find("infected", st[0])
            if t.reanimation_window_h is None:
                return _death_ev(tx, body_id, at, turn_index, "blood_loss", cause_event_id, {"core_intact": 0})
            lo, hi = round(t.reanimation_window_h[0] * 60), round(t.reanimation_window_h[1] * 60)
            mins = rng.range_int(tx, "infected", f"false_death:{body_id}", lo, hi)
            until = at + mins * MIN
            return tx.commit_event(Event(type=EventType.FALSE_DEATH, writer="physical.bodies", at=at, turn_index=turn_index,
                target_ids=[body_id], cause_event_id=cause_event_id,
                writes=[WriteRecord(op=WriteOp.UPDATE, table="bodies", key={"body_id": body_id},
                                    values={"false_dead_until": until, "awareness": "unconscious", "posture": "lying"})],
                payload={"body_id": body_id, "false_dead_until": until}))
        return None
    # alive kinds
    person = b["kind"] in ("human", "lurker") and _doomable(tx, body_id)
    cause = None
    if b["blood_loss_pct"] >= H.death_at_blood_loss_pct:
        cause = "blood_loss"
    elif headneck:
        cause = "head_wound" if ANATOMY_GROUP[headneck[0]["anatomy"]] == "head" else "neck_wound"
    else:
        n = tx.query_one("SELECT * FROM needs WHERE body_id=?", (body_id,))
        if n is not None:
            for need in ("thirst", "hunger", "cold", "heat"):
                if n[f"{need}_stage"] >= N.death_stage:
                    cause = need
                    break
        if cause is None:
            for inf in tx.query("SELECT * FROM infections WHERE body_id=? AND pathway='wet'", (body_id,)):
                pw = _canon(tx).find("pathway", "wet")
                if pw.death_at_h is not None and (at - inf["exposed_at"]) >= pw.death_at_h * 3_600_000:
                    cause = "infection"
    if cause:
        if person and doomed(tx, body_id) is None:
            _doom(tx, b, "instant", at, at, at, turn_index, cause_event_id, cause_event_id)
        return _death_ev(tx, body_id, at, turn_index, cause, cause_event_id, rng=rng)
    if person:
        d = doomed(tx, body_id)
        if d is None:
            _doom_check(tx, b, at, turn_index, cause_event_id)
        elif at >= d["death_by"] + H.doom_overdue_min * MIN:
            from ..audit.log import repair
            repair(tx, "degraded", None, "DOOM-05", {"body_id": body_id, "death_by": d["death_by"]}, turn_index, at)
            return _death_ev(tx, body_id, at, turn_index, "infection" if d["kind"] == "infection" else "blood_loss",
                             cause_event_id, rng=rng)
    if b["blood_loss_pct"] >= H.unconscious_at_blood_loss_pct and b["awareness"] != "unconscious":
        return tx.commit_event(Event(type=EventType.AWARENESS_CHANGE, writer="physical.bodies", at=at, turn_index=turn_index,
            target_ids=[body_id], cause_event_id=cause_event_id,
            writes=[WriteRecord(op=WriteOp.UPDATE, table="bodies", key={"body_id": body_id}, values={"awareness": "unconscious", "posture": "lying"})],
            payload={"body_id": body_id, "awareness": "unconscious", "from": b["awareness"]}))
    return None


def doomed(store: "Store | Tx", body_id: str) -> "dict | None":
    r = store.query_one("SELECT * FROM dooms WHERE body_id=?", (body_id,))
    return dict(r) if r is not None else None


def _doomable(tx, body_id):
    if excepted(tx, body_id):
        return False
    g = tx.query_one("SELECT value FROM meta WHERE key='god_bodies'")
    return not (g is not None and body_id in _god_list(g[0]))


def _doom_check(tx, b, at, turn_index, cause_event_id):
    """DOOM-01 / DOOM-02: a doom when this person's death has become certain."""
    H = _rules(tx).harm
    body_id = b["body_id"]
    horizon = H.doom_horizon_min
    rate_now = rate_best = minor_now = minor_best = 0.0
    worst, worst_e = None, 0.0
    for w in _wounds(tx, body_id):
        e = _eff_bleed(H, w)
        if e <= 0:
            continue
        best_m = min(_mult(H, w), H.tourniquet_mult if ANATOMY_GROUP[w["anatomy"]] in LIMB_GROUPS else H.packing_mult)
        if w["severity"] == "minor":
            left = min(horizon, max(0.0, (w["created_at"] + H.minor_clot_min * MIN - at) / MIN))
            minor_now += e * left
            minor_best += w["bleed_pct_per_min"] * best_m * left
            continue
        rate_now += e
        rate_best += w["bleed_pct_per_min"] * best_m
        if worst is None or e > worst_e:
            worst, worst_e = w, e
    to_lose = H.death_at_blood_loss_pct - b["blood_loss_pct"]
    if rate_best > 0:
        t_best = max(0.0, (to_lose - minor_best) / rate_best)
        if t_best <= horizon:
            t_now = max(0.0, (to_lose - minor_now) / rate_now) if rate_now > 0 else t_best
            death_by = at + _math.ceil(t_best * 60) * 1000
            expected = min(death_by, at + _math.ceil(t_now * 60) * 1000)
            return _doom(tx, b, "bleeding", at, expected, death_by, turn_index, cause_event_id, worst["cause_event"])
    lead = H.doom_infection_lead_min * MIN
    for inf in tx.query("SELECT * FROM infections WHERE body_id=? AND pathway='wet'", (body_id,)):
        pw = _canon(tx).find("pathway", "wet")
        if pw.death_at_h is None:
            continue
        dt = inf["exposed_at"] + int(pw.death_at_h * 3_600_000)
        if at <= dt <= at + lead:
            return _doom(tx, b, "infection", at, dt, dt, turn_index, cause_event_id, inf["cause_event"])
    return None


def _doom(tx, b, kind, at, expected, death_by, turn_index, cause_event_id, cause_event):
    """DOOM-03 / DOOM-04: the DOOM, and for a doom that leaves time, the scream."""
    from ..contracts.events import Event, EventType, WriteOp, WriteRecord
    body_id = b["body_id"]
    ev = tx.commit_event(Event(type=EventType.DOOM, writer="physical.bodies", at=at, turn_index=turn_index, actor_id=body_id,
        target_ids=[body_id], cause_event_id=cause_event_id,
        writes=[WriteRecord(op=WriteOp.INSERT, table="dooms", values={
            "body_id": body_id, "doomed_at": at, "expected_at": expected, "death_by": death_by, "kind": kind,
            "cause_event": cause_event, "turn_index": turn_index})],
        payload={"body_id": body_id, "kind": kind, "expected_at": expected, "death_by": death_by, "cause_event_id": cause_event}))
    if kind == "instant":
        return ev
    from ..mind import perception
    R = _rules(tx)
    pos = tx.query_one("SELECT place_id, x_m, y_m FROM positions WHERE body_id=?", (body_id,))
    now = tx.query_one("SELECT now_ms FROM world_clock WHERE id=1")[0]
    if pos is not None and at >= now:   # a doom found in catch-up, at a moment already past, screams unheard
        tx.commit_event(Event(type=EventType.NOISE, writer="action.propagate", at=at, turn_index=turn_index,
            actor_id=body_id, cause_event_id=ev.event_id, place_id=pos[0],
            payload={"source_db": R.infected.scream_db, "kind": "screaming", "text": "someone screaming", "place_id": pos[0],
                     "x_m": pos[1], "y_m": pos[2]}))
    perception.grant(tx, body_id, event_id=ev.event_id, channel="auditory", fidelity="exact", text="You are screaming.",
                     source_id=None, at=at, turn_index=turn_index)
    force_act(tx, body_id, "screams", death_by + int(R.harm.doom_overdue_min * MIN), at, turn_index, ev.event_id, origin="sim")
    return ev


def _next_boundary(tx, b, t, to_ms, periods, lastcol, canon, H):
    """The next time after t at which anything in a progress step can change, when nothing bleeds;
    None when something bleeds (step minute by minute)."""
    body_id = b["body_id"]
    for w in _wounds(tx, body_id):
        if _eff_bleed(H, w) > 0:
            return None
    cands = [to_ms]
    if b["kind"] in ("human", "lurker", "animal"):
        n = tx.query_one("SELECT * FROM needs WHERE body_id=?", (body_id,))
        if n is not None:
            for need in ("thirst", "hunger", "fatigue"):
                per = periods[need] * 3_600_000
                k = _math.floor((t - n[lastcol[need]]) / per) + 1
                cands.append(int(n[lastcol[need]] + k * per))
    for inf in tx.query("SELECT * FROM infections WHERE body_id=?", (body_id,)):
        pw = canon.find("pathway", inf["pathway"])
        for s in pw.stages:
            st = inf["exposed_at"] + int(s.starts_at_h * 3_600_000)
            if st > t:
                cands.append(st)
        if pw.death_at_h is not None:
            dt = inf["exposed_at"] + int(pw.death_at_h * 3_600_000)
            if dt > t:
                cands.append(dt)
    if b["false_dead_until"] is not None and b["false_dead_until"] > t:
        cands.append(b["false_dead_until"])
    if _care_subject(tx, b):
        C = _rules(tx).condition
        for step in (C.weather_step_min * MIN, C.cold_step_min * MIN):
            cands.append((t // step + 1) * step)
        gh = int(C.grime_every_h * 3_600_000)
        cands.append(b["washed_at"] + ((t - b["washed_at"]) // gh + 1) * gh)
    nxt = min(c for c in cands if c > t) if any(c > t for c in cands) else to_ms
    # land exactly on the step grid the minute-by-minute integration would use
    steps = max(1, (nxt - t + STEP_MS - 1) // STEP_MS)
    return min(to_ms, t + steps * STEP_MS)


def progress(tx: "Tx", body_id: str, to_ms: int, turn_index: int, rng: "Rng") -> list[Event]:
    """Advance bleeding, clotting, needs stages, infection stages and false-death timers for one
    body up to ``to_ms``; run the death test; return committed events (WOUND_PROGRESS,
    NEED_STAGE, INFECTION_STAGE, IMPAIRMENT_CHANGE, DEATH, REANIMATION...)."""
    from ..contracts.events import Event, EventType, WriteOp, WriteRecord
    R = _rules(tx)
    H, N = R.harm, R.needs
    canon = _canon(tx)
    out = []
    b = _b(tx, body_id)
    t = b["progressed_at"]
    imp0 = b["impairment"]
    if excepted(tx, body_id):                # D-102: nothing wears on it; only the clock moves
        return _clock_only(tx, body_id, b, to_ms, turn_index)
    params = _params(tx)
    heat = 1 + (params["climate_heat"] - 5) * 0.08
    periods = {"thirst": N.thirst_stage_every_h * heat, "hunger": N.hunger_stage_every_h, "fatigue": N.fatigue_stage_every_h}
    lastcol = {"thirst": "last_drink_ms", "hunger": "last_meal_ms", "fatigue": "last_sleep_ms"}
    while t < to_ms:
        end = min(t + STEP_MS, to_ms)
        b = _b(tx, body_id)
        if not b["alive"]:
            break
        if b["kind"] in ("human", "lurker") and doomed(tx, body_id) is None and _doomable(tx, body_id):
            _doom_check(tx, b, t, turn_index, None)   # DOOM-01 / DOOM-02 at the step's start, before it can kill
        jump = _next_boundary(tx, b, t, to_ms, periods, lastcol, canon, H)
        if jump is not None and jump > end:
            end = jump
        # 1 blood
        add = 0.0
        for w in _wounds(tx, body_id):
            if w["clotted"]:
                continue
            bleed_end = end
            clot_at = w["created_at"] + int(H.minor_clot_min * MIN) if w["severity"] == "minor" else None
            if clot_at is not None:
                bleed_end = min(end, clot_at)
            span = max(0, bleed_end - max(t, w["created_at"]))
            add += _eff_bleed(H, w) * span / MIN
            if clot_at is not None and clot_at <= end:
                out.append(tx.commit_event(Event(type=EventType.WOUND_PROGRESS, writer="physical.bodies", at=end, turn_index=turn_index,
                    target_ids=[body_id], writes=[WriteRecord(op=WriteOp.UPDATE, table="wounds", key={"wound_id": w["wound_id"]}, values={"clotted": 1, "next_due_at": None})],
                    payload={"body_id": body_id, "wound_id": w["wound_id"], "change": "clotted"})))
        if add > 0:
            nb = min(100.0, b["blood_loss_pct"] + add)
            tx.commit_event(Event(type=EventType.WOUND_PROGRESS, writer="physical.bodies", at=end, turn_index=turn_index,
                target_ids=[body_id], writes=[WriteRecord(op=WriteOp.UPDATE, table="bodies", key={"body_id": body_id}, values={"blood_loss_pct": nb, "progressed_at": end})],
                payload={"body_id": body_id, "change": "bleeding", "blood_loss_pct": nb}))
        # 2 needs (P10: living kinds only)
        n = tx.query_one("SELECT * FROM needs WHERE body_id=?", (body_id,)) if b["kind"] in ("human", "lurker", "animal") else None
        if n is not None:
            for need in ("thirst", "hunger", "fatigue"):
                hours = (end - n[lastcol[need]]) / 3_600_000
                st = min(6, max(0, int(_math.floor(hours / periods[need]))))
                if st != n[f"{need}_stage"]:
                    out.append(tx.commit_event(Event(type=EventType.NEED_STAGE, writer="physical.bodies", at=end, turn_index=turn_index,
                        target_ids=[body_id], writes=[WriteRecord(op=WriteOp.UPDATE, table="needs", key={"body_id": body_id}, values={f"{need}_stage": st})],
                        payload={"body_id": body_id, "need": need, "stage": st})))
                    bb = _b(tx, body_id)
                    if need == "fatigue" and st >= 6 and bb["awareness"] in ("alert", "awake", "drowsy"):
                        out.append(tx.commit_event(Event(type=EventType.AWARENESS_CHANGE, writer="physical.bodies", at=end, turn_index=turn_index,
                            target_ids=[body_id], writes=[WriteRecord(op=WriteOp.UPDATE, table="bodies", key={"body_id": body_id}, values={"awareness": "asleep", "posture": "lying"})],
                            payload={"body_id": body_id, "awareness": "asleep", "from": bb["awareness"]})))
        out += _care_step(tx, body_id, t, end, turn_index)
        # 3 infection
        for inf in tx.query("SELECT * FROM infections WHERE body_id=?", (body_id,)):
            pw = canon.find("pathway", inf["pathway"])
            hours = (end - inf["exposed_at"]) / 3_600_000
            stage = None
            for s in pw.stages:
                if s.starts_at_h <= hours:
                    stage = s.name
            if stage and stage != inf["stage"]:
                out.append(tx.commit_event(Event(type=EventType.INFECTION_STAGE, writer="physical.bodies", at=end, turn_index=turn_index,
                    target_ids=[body_id], writes=[WriteRecord(op=WriteOp.UPDATE, table="infections", key={"body_id": body_id, "pathway": inf["pathway"]}, values={"stage": stage})],
                    payload={"body_id": body_id, "pathway": inf["pathway"], "stage": stage})))
        # 4 false death
        b = _b(tx, body_id)
        if b["kind"] == "infected" and b["false_dead_until"] is not None and b["false_dead_until"] <= end and b["core_intact"]:
            ws = [WriteRecord(op=WriteOp.UPDATE, table="bodies", key={"body_id": body_id}, values={"awareness": "awake", "posture": "standing", "false_dead_until": None, "blood_loss_pct": 0.0})]
            for w in _wounds(tx, body_id):
                if not w["clotted"]:
                    ws.append(WriteRecord(op=WriteOp.UPDATE, table="wounds", key={"wound_id": w["wound_id"]}, values={"clotted": 1, "next_due_at": None}))
            out.append(tx.commit_event(Event(type=EventType.REANIMATION, writer="physical.bodies", at=end, turn_index=turn_index,
                target_ids=[body_id], writes=ws, payload={"body_id": body_id})))
        bleeders = sorted(_wounds(tx, body_id), key=lambda w: (-w["bleed_pct_per_min"], w["wound_id"]))
        blood_cause = bleeders[0]["cause_event"] if bleeders else None
        bb = _b(tx, body_id)
        d = death_test(tx, body_id, end, turn_index, rng, blood_cause if bb["blood_loss_pct"] >= min(H.death_at_blood_loss_pct, H.unconscious_at_blood_loss_pct) else None)
        if d is not None:
            out.append(d)
        t = end
    # heal check at to_ms
    b = _b(tx, body_id)
    rf = 1 + (5 - params["recovery_slack"]) * 0.1
    for w in _wounds(tx, body_id):
        if w["treatment"] and (to_ms - w["created_at"]) >= H.heal_days_per_severity[w["severity"]] * rf * 86_400_000:
            qualified = w["created_at"] + int(H.heal_days_per_severity[w["severity"]] * rf * 86_400_000)
            out.append(tx.commit_event(Event(type=EventType.WOUND_PROGRESS, writer="physical.bodies", at=to_ms, turn_index=turn_index,
                target_ids=[body_id], writes=[WriteRecord(op=WriteOp.UPDATE, table="wounds", key={"wound_id": w["wound_id"]}, values={"healed_at": qualified, "next_due_at": None})],
                payload={"body_id": body_id, "wound_id": w["wound_id"], "change": "healed"})))
    b = _b(tx, body_id)
    pain = min(6, sum(w["pain"] for w in _wounds(tx, body_id)))
    imp = _impairment_from(R, pain, b["blood_loss_pct"], _needs_of(tx, body_id))
    vals = {"progressed_at": to_ms}
    if pain != b["pain"]:
        vals["pain"] = pain
    if imp != imp0 or imp != b["impairment"]:
        vals["impairment"] = imp
    et = EventType.IMPAIRMENT_CHANGE if "impairment" in vals and imp != imp0 else EventType.WOUND_PROGRESS
    ev = tx.commit_event(Event(type=et, writer="physical.bodies", at=max(to_ms, b["progressed_at"]), turn_index=turn_index, target_ids=[body_id],
        writes=[WriteRecord(op=WriteOp.UPDATE, table="bodies", key={"body_id": body_id}, values=vals)],
        payload={"body_id": body_id, "impairment": imp} if et == EventType.IMPAIRMENT_CHANGE else {"body_id": body_id, "change": "clock"}))
    if et == EventType.IMPAIRMENT_CHANGE:
        out.append(ev)
    return out


def treat(tx: "Tx", body_id: str, wound_id: str, method: str, by_actor: str, at: int,
          cause_event_id: str, turn_index: int) -> Event:
    """TREATMENT event: method in {'pressure','packing','tourniquet','bandage','suture','clean'}."""
    from ..contracts.events import Event, EventType, WriteOp, WriteRecord
    if method not in ("pressure", "packing", "tourniquet", "bandage", "suture", "clean"):
        raise ValueError(f"unknown treatment {method}")
    w = [x for x in _wounds(tx, body_id, unhealed=False) if x["wound_id"] == wound_id][0]
    if method == "tourniquet" and ANATOMY_GROUP[w["anatomy"]] not in LIMB_GROUPS:
        raise ValueError("a tourniquet goes on a limb")
    if method == "suture" and w["severity"] not in ("minor", "significant"):
        raise ValueError("only minor or significant wounds can be sutured")
    vals = {"treatment": w["treatment"] + [method]}
    if method == "clean":
        vals["contamination"] = max(0, w["contamination"] - 1)
    return tx.commit_event(Event(type=EventType.TREATMENT, writer="physical.bodies", at=at, turn_index=turn_index, actor_id=by_actor,
        target_ids=[body_id], cause_event_id=cause_event_id,
        writes=[WriteRecord(op=WriteOp.UPDATE, table="wounds", key={"wound_id": wound_id}, values=vals)],
        payload={"body_id": body_id, "wound_id": wound_id, "method": method, "by_actor": by_actor}))


def capacity(store: "Store | Tx", body_id: str) -> Capacity:
    b = _b(store, body_id)
    ws = _wounds(store, body_id)
    conscious = bool(b["alive"]) and b["awareness"] in ("alert", "awake", "drowsy")
    legs = {ANATOMY_SIDE[w["anatomy"]] for w in ws if ANATOMY_GROUP[w["anatomy"]] in ("leg",) and w["function_loss"] >= 2}
    mobile = conscious and not (b["restrained"] and not excepted(store, body_id)) and len(legs) < 2
    free = 0
    for side, slot in (("l", "hand_l"), ("r", "hand_r")):
        disabled = any(ANATOMY_GROUP[w["anatomy"]] in ("arm", "hand") and ANATOMY_SIDE.get(w["anatomy"]) == side and w["function_loss"] >= 2 for w in ws)
        held = store.query_one("SELECT 1 FROM items WHERE holder_body=? AND holder_slot=?", (body_id, slot)) is not None
        if not disabled and not held:
            free += 1
    can_speak = conscious and not any(w["severity"] == "catastrophic" and ANATOMY_GROUP[w["anatomy"]] == "neck" for w in ws)
    hobbled = any(ANATOMY_GROUP[w["anatomy"]] in ("leg", "foot") and w["function_loss"] >= 1 for w in ws)
    return Capacity(mobile=mobile, hands_free=free, can_speak=can_speak, conscious=conscious, impairment=b["impairment"],
                    can_run=mobile and not hobbled)


def wake(tx: "Tx", body_id: str, at: int, cause_event_id: str | None, turn_index: int) -> Event | None:
    """P3 (perception calls it): an ASLEEP or DROWSY living body becomes 'awake' — commit
    AWARENESS_CHANGE {body_id, awareness: 'awake', from} (posture unchanged: waking is not
    standing up). Any other awareness -> None, nothing committed."""
    from ..contracts.events import Event, EventType, WriteOp, WriteRecord
    bb = _b(tx, body_id)
    if not bb["alive"] or bb["awareness"] not in ("asleep", "drowsy"):
        return None
    return tx.commit_event(Event(type=EventType.AWARENESS_CHANGE, writer="physical.bodies", at=at, turn_index=turn_index,
        target_ids=[body_id], cause_event_id=cause_event_id,
        writes=[WriteRecord(op=WriteOp.UPDATE, table="bodies", key={"body_id": body_id}, values={"awareness": "awake"})],
        payload={"body_id": body_id, "awareness": "awake", "from": bb["awareness"]}))


def effective_bleed(store: "Store | Tx", wound_id: str) -> float:
    """Effective bleed of one wound in % blood per minute, by the rule in the module docstring
    (0.0 for a clotted or healed wound). The packet's 'bleeding' word and progress() share it."""
    r = store.query_one("SELECT * FROM wounds WHERE wound_id=?", (wound_id,))
    if r is None:
        raise ValueError(f"no wound {wound_id}")
    w = dict(r)
    w["treatment"] = _json.loads(w["treatment"])
    return _eff_bleed(_rules(store).harm, w)


# ------------------------------------------------------------------ P5 additions
_POSTURES = ("standing", "crouched", "sitting", "lying", "prone")


def posture_event(tx: "Tx", body_id: str, posture: str, at: int, cause_event_id: str | None,
                  turn_index: int, *, awareness: str | None = None) -> Event:
    """P5 (effects). Commit POSTURE_CHANGE {body_id, posture, from, awareness} (writer
    'physical.bodies', actor_id = body_id) writing bodies.posture (a Posture value, ValueError
    otherwise) and, when ``awareness`` is given, bodies.awareness — only 'asleep' or 'awake' may be
    set this way (ValueError otherwise; a dead or unconscious body -> ValueError). payload
    awareness is null when not given. A change to the same posture is still committed (a
    deliberate act)."""
    from ..contracts.events import Event, EventType, WriteOp, WriteRecord
    if posture not in _POSTURES:
        raise ValueError(f"bad posture {posture}")
    bb = _b(tx, body_id)
    if not bb["alive"] or bb["awareness"] in ("unconscious", "dead"):
        raise ValueError("an unconscious or dead body does not change posture by itself")
    vals = {"posture": posture}
    if awareness is not None:
        if awareness not in ("asleep", "awake"):
            raise ValueError("only asleep / awake")
        vals["awareness"] = awareness
    return tx.commit_event(Event(type=EventType.POSTURE_CHANGE, writer="physical.bodies", at=at, turn_index=turn_index,
                                 actor_id=body_id, cause_event_id=cause_event_id,
                                 writes=[WriteRecord(op=WriteOp.UPDATE, table="bodies", key={"body_id": body_id}, values=vals)],
                                 payload={"body_id": body_id, "posture": posture, "from": bb["posture"], "awareness": awareness}))


def grips_on(store: "Store | Tx", target_id: str) -> list[str]:
    """P5. Holder ids gripping the target, sorted."""
    return [r[0] for r in store.query("SELECT holder_id FROM grips WHERE target_id=? ORDER BY holder_id", (target_id,))]


def grip_event(tx: "Tx", holder_id: str, target_id: str, at: int, cause_event_id: str | None,
               turn_index: int) -> Event:
    """P5. Commit CONTROL_ESTABLISH {holder_id, target_id} (writer 'physical.bodies', actor_id =
    holder) inserting a grips row and setting the target's bodies.restrained = 1. A grip that
    already exists -> ValueError."""
    from ..contracts.events import Event, EventType, WriteOp, WriteRecord
    if tx.query_one("SELECT 1 FROM grips WHERE holder_id=? AND target_id=?", (holder_id, target_id)):
        raise ValueError("already gripping")
    return tx.commit_event(Event(type=EventType.CONTROL_ESTABLISH, writer="physical.bodies", at=at, turn_index=turn_index,
                                 actor_id=holder_id, cause_event_id=cause_event_id, target_ids=[target_id],
                                 writes=[WriteRecord(op=WriteOp.INSERT, table="grips", values={
                                     "holder_id": holder_id, "target_id": target_id, "since_ms": at, "cause_event": cause_event_id or "none"}),
                                     WriteRecord(op=WriteOp.UPDATE, table="bodies", key={"body_id": target_id}, values={"restrained": 1})],
                                 payload={"holder_id": holder_id, "target_id": target_id}))


def release_event(tx: "Tx", holder_id: str, target_id: str, at: int, cause_event_id: str | None,
                  turn_index: int) -> Event:
    """P5. Commit CONTROL_RELEASE {holder_id, target_id} deleting the grips row; the target's
    restrained becomes 0 when no other grip on it remains. No such grip -> ValueError. A body
    that dies or falls unconscious keeps no grips: effects release them (the resolver checks
    grips of incapable holders at every landing)."""
    from ..contracts.events import Event, EventType, WriteOp, WriteRecord
    if not tx.query_one("SELECT 1 FROM grips WHERE holder_id=? AND target_id=?", (holder_id, target_id)):
        raise ValueError("no such grip")
    others = [h for h in grips_on(tx, target_id) if h != holder_id]
    writes = [WriteRecord(op=WriteOp.DELETE, table="grips", key={"holder_id": holder_id, "target_id": target_id})]
    if not others:
        writes.append(WriteRecord(op=WriteOp.UPDATE, table="bodies", key={"body_id": target_id}, values={"restrained": 0}))
    return tx.commit_event(Event(type=EventType.CONTROL_RELEASE, writer="physical.bodies", at=at, turn_index=turn_index,
                                 actor_id=holder_id, cause_event_id=cause_event_id, target_ids=[target_id], writes=writes,
                                 payload={"holder_id": holder_id, "target_id": target_id}))


_NEED_COL = {"thirst": ("thirst_stage", "last_drink_ms"), "hunger": ("hunger_stage", "last_meal_ms"),
             "fatigue": ("fatigue_stage", "last_sleep_ms")}


def refresh_need(tx: "Tx", body_id: str, need: str, at: int, cause_event_id: str | None,
                 turn_index: int) -> Event:
    """P5 (eat / drink effects; sleep in P10). need in {'thirst','hunger','fatigue'} (ValueError
    otherwise). Commit NEED_STAGE {body_id, need, stage: 0, refreshed: true} writing
    needs.<need>_stage = 0 and last_drink_ms / last_meal_ms / last_sleep_ms = at, and the body's
    impairment recomputed (HARM-07) in the same event."""
    from ..contracts.events import Event, EventType, WriteOp, WriteRecord
    if need not in _NEED_COL:
        raise ValueError(f"bad need {need}")
    stage_col, last_col = _NEED_COL[need]
    n = dict(tx.query_one("SELECT thirst_stage, hunger_stage, fatigue_stage FROM needs WHERE body_id=?", (body_id,)))
    n[stage_col] = 0
    bb = _b(tx, body_id)
    imp = _impairment_from(_rules(tx), bb["pain"], bb["blood_loss_pct"], [n["thirst_stage"], n["hunger_stage"], n["fatigue_stage"]])
    writes = [WriteRecord(op=WriteOp.UPDATE, table="needs", key={"body_id": body_id}, values={stage_col: 0, last_col: at})]
    if imp != bb["impairment"]:
        writes.append(WriteRecord(op=WriteOp.UPDATE, table="bodies", key={"body_id": body_id}, values={"impairment": imp}))
    return tx.commit_event(Event(type=EventType.NEED_STAGE, writer="physical.bodies", at=at, turn_index=turn_index,
                                 actor_id=body_id, cause_event_id=cause_event_id, writes=writes,
                                 payload={"body_id": body_id, "need": need, "stage": 0, "refreshed": True}))



# ------------------------------------------------------------------------------------------ P10
def create(tx: "Tx", *, kind: str, sex: str | None, age_years: int | None, height_cm: int, mass_kg: int,
           special: dict, at: int, turn_index: int, origin: str, cause_event_id: str | None = None,
           awareness: str = "awake", posture: str = "standing", content_ref: str | None = None,
           looks: "Looks | None" = None) -> str:
    from ..contracts.common import age_band_for
    from ..contracts.events import Event, EventType, WriteOp, WriteRecord
    if origin not in ("worldgen", "birth", "materialize", "cheat", "reanimation", "scenario", "wildcard"):
        raise ValueError(f"unknown body origin {origin}")
    bid = tx.mint("act")
    vals = {"body_id": bid, "kind": kind, "content_ref": content_ref, "sex": sex, "age_years": age_years,
            "age_band": age_band_for(age_years).value if age_years is not None else None, "height_cm": height_cm,
            "mass_kg": mass_kg, "alive": 1, "awareness": awareness, "posture": posture, "blood_loss_pct": 0.0,
            "pain": 0, "impairment": 0, "restrained": 0, "special": special, "progressed_at": at, "core_intact": 1,
            "origin": origin}
    if looks is not None:
        from ..kernel.jsoncanon import canonical_json
        vals["looks"] = canonical_json({**looks.model_dump(mode="json"), "outfit": []})
    if kind == "infected":
        vals.update(grime=5, blood=3, gore=5)
    vals["washed_at"] = at
    ws = [WriteRecord(op=WriteOp.INSERT, table="bodies", values=vals)]
    if kind in ("human", "lurker", "animal"):
        ws.append(WriteRecord(op=WriteOp.INSERT, table="needs", values={
            "body_id": bid, "thirst_stage": 0, "hunger_stage": 0, "fatigue_stage": 0,
            "last_drink_ms": at, "last_meal_ms": at, "last_sleep_ms": at}))
    tx.commit_event(Event(type=EventType.MATERIALIZE, writer="physical.bodies", at=at, turn_index=turn_index,
                          origin="worldgen" if origin == "worldgen" else "sim", actor_id=bid, target_ids=[bid],
                          cause_event_id=cause_event_id, writes=ws, payload={"body_id": bid, "kind": kind, "source": origin}))
    return bid


def expose(tx: "Tx", rng: "Rng", body_id: str, pathway: str, exposure: str, at: int, cause_event_id: str | None,
           turn_index: int) -> Event | None:
    from ..contracts.events import Event, EventType, WriteOp, WriteRecord
    rec = _canon(tx).find("pathway", pathway)
    if exposure not in rec.exposure:
        raise ValueError(f"pathway {pathway} has no exposure {exposure}")
    b = _b(tx, body_id)
    if not b["alive"] or b["kind"] not in ("human", "lurker") or excepted(tx, body_id):
        return None
    if tx.query_one("SELECT 1 FROM infections WHERE body_id=? AND pathway=?", (body_id, pathway)) is not None:
        return None
    infected = rng.chance(tx, "infected", f"exposure:{body_id}:{cause_event_id}", rec.exposure[exposure])
    ws = []
    if infected:
        ws.append(WriteRecord(op=WriteOp.INSERT, table="infections", values={
            "body_id": body_id, "pathway": pathway, "exposed_at": at, "stage": rec.stages[0].name,
            "cause_event": cause_event_id or "", "known_to_self": 0}))
    return tx.commit_event(Event(type=EventType.INFECTION_EXPOSURE, writer="physical.bodies", at=at, turn_index=turn_index,
                                 actor_id=body_id, target_ids=[body_id], cause_event_id=cause_event_id, writes=ws,
                                 payload={"body_id": body_id, "pathway": pathway, "exposure": exposure, "infected": infected}))


def die(tx: "Tx", rng: "Rng", body_id: str, at: int, cause_event_id: str | None, turn_index: int, *,
        cause: str = "offscreen") -> Event | None:
    b = _b(tx, body_id)
    if not b["alive"] or excepted(tx, body_id):
        return None
    return _death_ev(tx, body_id, at, turn_index, cause, cause_event_id, rng=rng)


def rise(tx: "Tx", corpse_id: str, type_id: str, at: int, cause_event_id: str | None, turn_index: int) -> str:
    c = _b(tx, corpse_id)
    t = _canon(tx).find("infected", type_id)
    return create(tx, kind="infected", sex=c["sex"], age_years=c["age_years"], height_cm=c["height_cm"],
                  mass_kg=c["mass_kg"], special={k: (v.lo + v.hi) // 2 for k, v in t.special.items()}, at=at,
                  turn_index=turn_index, origin="reanimation", cause_event_id=cause_event_id,
                  looks=looks_of(tx, corpse_id))


def contagious(store: "Store | Tx", body_id: str) -> bool:
    b = store.query_one("SELECT kind, alive FROM bodies WHERE body_id=?", (body_id,))
    if b is None:
        return False
    if b[0] == "infected":
        return True
    if not b[1] or b[0] not in ("human", "lurker"):
        return False
    return any(pw == "wet" and st.saliva_infectious for pw, st in stages(store, body_id))


def stages(store: "Store | Tx", body_id: str) -> list[tuple[str, "InfectionStage"]]:
    """P10: (pathway, the canon stage record) per infections row, by pathway."""
    out = []
    for r in store.query("SELECT pathway, stage FROM infections WHERE body_id=? ORDER BY pathway", (body_id,)):
        rec = _canon(store).find("pathway", r[0])
        st = next((s for s in rec.stages if s.name == r[1]), None)
        if st is not None:
            out.append((r[0], st))
    return out


@dataclass(frozen=True)
class BodyCondition:
    grime: int
    blood: int
    gore: int
    wet: int
    washed_at: int


def looks_of(store: "Store | Tx", body_id: str) -> "Looks | None":
    import json
    from ..contracts.dossier import Looks
    r = store.query_one("SELECT looks FROM bodies WHERE body_id=?", (body_id,))
    if r is None or r[0] is None:
        return None
    return Looks.model_validate(json.loads(r[0]))


def condition_of(store: "Store | Tx", body_id: str) -> BodyCondition:
    r = store.query_one("SELECT grime, blood, gore, wet, washed_at FROM bodies WHERE body_id=?", (body_id,))
    return BodyCondition(*r)


def soil(tx: "Tx", body_id: str, *, grime: int = 0, blood: int = 0, gore: int = 0, wet: int = 0, source: str,
         at: int, cause_event_id: str | None, turn_index: int) -> "Event | None":
    from ..contracts.events import Event, EventType, WriteOp, WriteRecord
    if excepted(tx, body_id):
        return None
    c = condition_of(tx, body_id)
    new = {"grime": max(0, min(5, c.grime + grime)), "blood": max(0, min(5, c.blood + blood)),
           "gore": max(0, min(5, c.gore + gore)), "wet": max(0, min(3, c.wet + wet))}
    if new == {"grime": c.grime, "blood": c.blood, "gore": c.gore, "wet": c.wet}:
        return None
    return tx.commit_event(Event(type=EventType.BODY_CONDITION, writer="physical.bodies", at=at, turn_index=turn_index,
                                 actor_id=body_id, target_ids=[body_id], cause_event_id=cause_event_id,
                                 writes=[WriteRecord(op=WriteOp.UPDATE, table="bodies", values=new, key={"body_id": body_id})],
                                 payload={"body_id": body_id, **new, "source": source}))


def wash(tx: "Tx", body_id: str, *, full: bool, at: int, cause_event_id: str | None,
         turn_index: int) -> "Event | None":
    from ..contracts.events import Event, EventType, WriteOp, WriteRecord
    if tx.query_one("SELECT 1 FROM bodies WHERE body_id=?", (body_id,)) is None:
        return None
    c = condition_of(tx, body_id)
    if full:
        new = {"grime": 0, "blood": 0, "gore": 0, "wet": min(3, c.wet + 1), "washed_at": at}
        source = "washed"
    else:
        new = {"grime": max(0, c.grime - 1), "blood": max(0, c.blood - 2), "gore": max(0, c.gore - 2), "wet": min(3, c.wet + 1)}
        source = "wiped"
    return tx.commit_event(Event(type=EventType.BODY_CONDITION, writer="physical.bodies", at=at, turn_index=turn_index,
                                 actor_id=body_id, cause_event_id=cause_event_id,
                                 writes=[WriteRecord(op=WriteOp.UPDATE, table="bodies", key={"body_id": body_id}, values=new)],
                                 payload={"body_id": body_id, "grime": new["grime"], "blood": new["blood"], "gore": new["gore"],
                                          "wet": new["wet"], "source": source}))


def _care_subject(s, b):
    return b["alive"] and b["kind"] == "human" and b["looks"] is not None


def cold_need(store: "Store | Tx", body_id: str, at: int) -> int:
    from ..kernel.clock import world_time
    from ..world.decay import exposed
    C = _rules(store).condition
    b = _b(store, body_id)
    if not _care_subject(store, b) or excepted(store, body_id):
        return 0
    heat = _params(store)["climate_heat"]
    band = "cold" if heat <= 3 else ("hot" if heat >= 8 else "mild")
    base = C.cold_need[band]
    pos = store.query_one("SELECT place_id FROM positions WHERE body_id=?", (body_id,))
    if pos is not None and exposed(store, pos[0]):
        if world_time(at).part_of_day in ("night", "late night"):
            base += 1
    else:
        base = max(0, base - C.shelter)
    if b["wet"] >= 2:
        base += 1
    return base


def _care_step(tx, body_id, t, end, turn_index):
    """LOOK-08 then LOOK-09 for one progress step [t, end]."""
    from ..contracts.events import Event, EventType, WriteOp, WriteRecord
    from ..physical.objects import warmth
    from ..world.decay import exposed, wet
    R = _rules(tx)
    C, N = R.condition, R.needs
    out = []
    b = _b(tx, body_id)
    if not _care_subject(tx, b):
        return out
    g = min(C.grime_unwashed_max, (end - b["washed_at"]) // int(C.grime_every_h * 3_600_000))
    if b["grime"] < g:
        ev = soil(tx, body_id, grime=g - b["grime"], source="unwashed", at=end, cause_event_id=None, turn_index=turn_index)
        if ev is not None:
            out.append(ev)
    W = C.weather_step_min * MIN
    n = end // W - t // W
    if n >= 1:
        pos = tx.query_one("SELECT place_id FROM positions WHERE body_id=?", (body_id,))
        if pos is not None and wet(tx) and exposed(tx, pos[0]):
            ev = soil(tx, body_id, wet=n, blood=-n, gore=-n, source="rain", at=end, cause_event_id=None, turn_index=turn_index)
        elif _b(tx, body_id)["wet"] > 0:
            ev = soil(tx, body_id, wet=-n, source="dried", at=end, cause_event_id=None, turn_index=turn_index)
        else:
            ev = None
        if ev is not None:
            out.append(ev)
    K = C.cold_step_min * MIN
    k = end // K - t // K
    nd = tx.query_one("SELECT * FROM needs WHERE body_id=?", (body_id,))
    if k >= 1 and nd is not None:
        d = cold_need(tx, body_id, end) - warmth(tx, body_id)
        chill = nd["chill"] + k * d if d > 0 else max(0, nd["chill"] - k * C.warm_per_step)
        stage = min(N.death_stage, chill // C.chill_per_stage)
        if chill != nd["chill"]:
            out.append(tx.commit_event(Event(type=EventType.NEED_STAGE, writer="physical.bodies", at=end, turn_index=turn_index,
                target_ids=[body_id], writes=[WriteRecord(op=WriteOp.UPDATE, table="needs", key={"body_id": body_id},
                                                          values={"chill": chill, "cold_stage": stage})],
                payload={"body_id": body_id, "need": "cold", "stage": stage, "chill": chill})))
    return out
