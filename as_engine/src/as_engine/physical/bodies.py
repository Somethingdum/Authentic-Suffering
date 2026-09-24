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
  max(thirst_stage, hunger_stage, fatigue_stage) (0 below 3). (Intoxication, concussion and
  exhaustion terms join this sum when their systems exist; until then they are 0.)
  bodies.impairment is rewritten whenever pain, blood loss or a need stage changes, by the event
  that changed it.

Capacity (``capacity``):
  conscious  = alive and awareness in (alert, awake, drowsy)
  mobile     = conscious and not restrained and NOT (both legs carry a wound with function_loss 2)
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
  tick must not cost 360 database round trips per body.
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

Treatment (``treat``): method in {'pressure','packing','tourniquet','bandage','suture','clean'};
  tourniquet only on a limb (ValueError otherwise); suture only on a minor or significant wound
  (ValueError otherwise); 'clean' lowers contamination by 1 (min 0). The method is appended to
  wounds.treatment (a JSON list; repeats allowed). Payload {body_id, wound_id, method, by_actor}.

P10 — bodies made during play, exposure, deaths nobody saw, and the dead that rise:
create(tx, *, kind, sex, age_years, height_cm, mass_kg, special, at, turn_index, origin,
       cause_event_id=None, awareness='awake', posture='standing', content_ref=None) -> str
  body_id = tx.mint('act'). One MATERIALIZE {body_id, kind, source: origin} (writer
  'physical.bodies', event origin 'worldgen' when ``origin`` (the bodies.origin value) is
  'worldgen', else 'sim'; actor_id = body_id) inserting bodies {body_id, kind, content_ref, sex, age_years, age_band =
  contracts.common.age_band_for(age_years) (NULL without an age), height_cm, mass_kg, alive 1, awareness,
  posture, blood_loss_pct 0, pain 0, impairment 0, restrained 0, special (JSON), progressed_at = at,
  core_intact 1, origin} and, for kinds human, lurker and animal, needs {body_id, all stages 0,
  last_drink_ms = last_meal_ms = last_sleep_ms = at}. origin in bodies.origin's CHECK values
  (ValueError otherwise). Returns body_id.
expose(tx, rng, body_id, pathway, exposure, at, cause_event_id, turn_index) -> Event | None
  (action.effects bite, world.infected.) The canon pathway record ``pathway`` (ValueError when it has
  no ``exposure`` key of that name). A dead body, or one that already has an infections row for that
  pathway -> None. infected = rng.chance(tx, 'infected', f"exposure:{body_id}:{cause_event_id}",
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
  cause_event_id) — the corpse stays a dead body (its history is its own); the new body is what got
  up. Returns the new body id. (world.infected moves it into the corpse's place and gives it the
  corpse's things.)
stages(store, body_id) -> list[tuple[str, InfectionStage]]   (what each infection is doing to the
  host now: mind.cues signs, the packet's and the narrator's felt lines, action.effects mouth
  contact, turn.cognition compulsion)
  Per infections row of the body, by pathway: (pathway, the canon pathway record's stage whose name
  is the row's stage — as ``progress`` last left it). No rows -> [].
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..contracts.common import Anatomy, WoundSeverity, WoundType
from ..contracts.events import Event

if TYPE_CHECKING:
    from ..contracts.content import InfectionStage
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


# P10 functions stand above the P2 ones so the kit's P10 patch merges over built code.
def create(tx: "Tx", *, kind: str, sex: str | None, age_years: int | None, height_cm: int, mass_kg: int,
           special: dict, at: int, turn_index: int, origin: str, cause_event_id: str | None = None,
           awareness: str = "awake", posture: str = "standing", content_ref: str | None = None) -> str:
    raise NotImplementedError("P10")


def expose(tx: "Tx", rng: "Rng", body_id: str, pathway: str, exposure: str, at: int, cause_event_id: str | None,
           turn_index: int) -> Event | None:
    raise NotImplementedError("P10")


def stages(store: "Store | Tx", body_id: str) -> list[tuple[str, "InfectionStage"]]:
    raise NotImplementedError("P10")


def die(tx: "Tx", rng: "Rng", body_id: str, at: int, cause_event_id: str | None, turn_index: int, *,
        cause: str = "offscreen") -> Event | None:
    raise NotImplementedError("P10")


def rise(tx: "Tx", corpse_id: str, type_id: str, at: int, cause_event_id: str | None, turn_index: int) -> str:
    raise NotImplementedError("P10")


def apply_harm(tx: "Tx", body_id: str, wound: WoundSpec, at: int, cause_event_id: str,
               turn_index: int, rng: "Rng") -> list[Event]:
    """HARM event inserting the wound (+ pain/impairment update) then the death test (rng is
    needed for a false-death draw). Returns the committed events (HARM, and possibly
    AWARENESS_CHANGE / DEATH / FALSE_DEATH).
    actor_id (event and payload) = the cause event's actor_id when that actor is a human body,
    else null (infected bites, animals, falls).
    HARM payload (cascades filter on it): {wound_id, body_id, actor_id (null for infected/animals),
    anatomy, anatomy_group ('head'|'neck'|'torso'|'arm'|'hand'|'leg'|'foot'), type, severity,
    function_loss, bleed_pct_per_min, contamination}."""
    raise NotImplementedError("P2")


def progress(tx: "Tx", body_id: str, to_ms: int, turn_index: int, rng: "Rng") -> list[Event]:
    """Advance bleeding, clotting, needs stages, infection stages and false-death timers for one
    body up to ``to_ms``; run the death test; return committed events (WOUND_PROGRESS,
    NEED_STAGE, INFECTION_STAGE, IMPAIRMENT_CHANGE, DEATH, REANIMATION...)."""
    raise NotImplementedError("P2")


def treat(tx: "Tx", body_id: str, wound_id: str, method: str, by_actor: str, at: int,
          cause_event_id: str, turn_index: int) -> Event:
    """TREATMENT event: method in {'pressure','packing','tourniquet','bandage','suture','clean'}."""
    raise NotImplementedError("P2")


def capacity(store: "Store | Tx", body_id: str) -> Capacity:
    raise NotImplementedError("P2")


def impairment(store: "Store | Tx", body_id: str) -> int:
    raise NotImplementedError("P2")


def death_test(tx: "Tx", body_id: str, at: int, turn_index: int, rng: "Rng",
               cause_event_id: str | None) -> Event | None:
    raise NotImplementedError("P2")


def is_alive(store: "Store | Tx", body_id: str) -> bool:
    raise NotImplementedError("P2")


def posture_event(tx: "Tx", body_id: str, posture: str, at: int, cause_event_id: str | None,
                  turn_index: int, *, awareness: str | None = None) -> Event:
    """P5 (effects). Commit POSTURE_CHANGE {body_id, posture, from, awareness} (writer
    'physical.bodies', actor_id = body_id) writing bodies.posture (a Posture value, ValueError
    otherwise) and, when ``awareness`` is given, bodies.awareness — only 'asleep' or 'awake' may be
    set this way (ValueError otherwise; a dead or unconscious body -> ValueError). payload
    awareness is null when not given. A change to the same posture is still committed (a
    deliberate act)."""
    raise NotImplementedError("P5")


def grip_event(tx: "Tx", holder_id: str, target_id: str, at: int, cause_event_id: str | None,
               turn_index: int) -> Event:
    """P5. Commit CONTROL_ESTABLISH {holder_id, target_id} (writer 'physical.bodies', actor_id =
    holder) inserting a grips row and setting the target's bodies.restrained = 1. A grip that
    already exists -> ValueError."""
    raise NotImplementedError("P5")


def release_event(tx: "Tx", holder_id: str, target_id: str, at: int, cause_event_id: str | None,
                  turn_index: int) -> Event:
    """P5. Commit CONTROL_RELEASE {holder_id, target_id} deleting the grips row; the target's
    restrained becomes 0 when no other grip on it remains. No such grip -> ValueError. A body
    that dies or falls unconscious keeps no grips: effects release them (the resolver checks
    grips of incapable holders at every landing)."""
    raise NotImplementedError("P5")


def grips_on(store: "Store | Tx", target_id: str) -> list[str]:
    """P5. Holder ids gripping the target, sorted."""
    raise NotImplementedError("P5")


def refresh_need(tx: "Tx", body_id: str, need: str, at: int, cause_event_id: str | None,
                 turn_index: int) -> Event:
    """P5 (eat / drink effects; sleep in P10). need in {'thirst','hunger','fatigue'} (ValueError
    otherwise). Commit NEED_STAGE {body_id, need, stage: 0, refreshed: true} writing
    needs.<need>_stage = 0 and last_drink_ms / last_meal_ms / last_sleep_ms = at, and the body's
    impairment recomputed (HARM-07) in the same event."""
    raise NotImplementedError("P5")


def effective_bleed(store: "Store | Tx", wound_id: str) -> float:
    """Effective bleed of one wound in % blood per minute, by the rule in the module docstring
    (0.0 for a clotted or healed wound). The packet's 'bleeding' word and progress() share it."""
    raise NotImplementedError("P2")


def wake(tx: "Tx", body_id: str, at: int, cause_event_id: str | None, turn_index: int) -> Event | None:
    """P3 (perception calls it): an ASLEEP or DROWSY living body becomes 'awake' — commit
    AWARENESS_CHANGE {body_id, awareness: 'awake', from} (posture unchanged: waking is not
    standing up). Any other awareness -> None, nothing committed."""
    raise NotImplementedError("P3")
