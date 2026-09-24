# 07 — Rules

"D&D-like rules without the clutter" (project brief). Every number here lives in `RulesConfig`
(`contracts/settings.py`) or in content; `[SAND]` numbers are estimates that `tools/as/bench.py`
or play-tuning replaces, never silently.

## 1. The universal check (`action/checks.py`)

```
TARGET = clamp(attr_mod + skill_rank + tag_bonus + situation + scale - impairment//2 - resistance, 1, 9)
draw   = d10 (rng stream 'resolve')
MARGIN = TARGET - draw      >= +3 CLEAN | 0..+2 COST | -1..-2 FAIL | <= -3 BREAK
```

| attr (SPECIAL) | 1–2 | 3–4 | 5–6 | 7–8 | 9–10 |
|---|---|---|---|---|---|
| attr_mod | 1 | 2 | 3 | 4 | 5 |

skill rank 0 (untrained) … 3 (expert). One relevant capability tag grants +2; tags never stack.
Worked odds: an average untrained adult (attr 5, rank 0, target 3) gets COST 30 %, FAIL 20 %,
BREAK 50 %; a skilled specialist with a tag (attr 7, rank 2, tag → 8) gets CLEAN 50 %, COST 30 %,
FAIL 20 %. The world is hard on the untrained, as intended.

- **COST**: success plus one causal cost now (time +50 %, noise +10 dB, a scrape, a dropped item,
  a witness) chosen by the effect handler's cost table.
- **BREAK**: failure plus one new causal problem now; at snowball rate ≥ 6 an extra complication
  may follow (06 §1.2).
- **No free miss** (CHECK-04): a failed roll never causes harm by itself.
- **Identity is never rolled** (L7): consent, loyalty, values, moral limits.

### 1.1 Situation modifiers (sum, clamp −3..+3)

| Condition | Mod |
|---|---|
| light 0 / 1 / 2 (for sight-dependent actions; thermal senses ignore) | −3 / −2 / −1 |
| rushed (the actor chose a faster manner) / careful (double time) | −1 / +1 |
| wet, icy or rubble footing (athletics, melee, grapple) | −1 |
| the right tool (crowbar to force, lockpick to pick, splint to set) | +1 |
| using a limb with function loss 1 / 2 | −1 / impossible (physical gate) |
| helped by another body in reach doing the same task | +1 |

### 1.2 Resistance keys (`CheckSpec.resistance`)

`portal.lock_quality` (0–4) · `portal.barricade` (0–3) · `portal.lock_and_barricade` (sum) ·
`target.attr_mod.<X>` · `range_band` (≤5 m 0, ≤15 m 1, ≤30 m 2, ≤60 m 3, beyond effective range 5)
plus target cover (0–3) plus 1 if the target moved · `obstacle.class` (low fence 1, high fence 3,
wall 5) · `container.lock_quality` · `wound.severity` (medicine: minor 0, significant 1, severe 2,
catastrophic 4) · `observer.best_perception` (stealth: best observer's attr_mod(P), +1 if alert).

### 1.3 Opposed checks
Both sides draw; higher margin wins; difference ≥ 3 clean, 1–2 winner pays a cost, 0 → established
control, then the precedence ladder, then one tie draw. Passive material never draws.

### 1.4 Stealth ladder (six degrees, carried)
By the hider's margin: ≥ 5 **ghost protocol** (no percept at all) · 3–4 **unseen passage** ·
1–2 **fleeting suspicion** (observers get "something moved" at tone level) · 0 **heightened
suspicion** (observers get a silhouette and become alert) · −1..−2 **detected** (partial
visibility) · ≤ −3 **compromised with prejudice** (clear visibility; observers' standing toward the
hider drops to hostile). The middle degrees are where the good play lives.

## 2. Time and movement

Clock: integer ms since the Fall. Durations: momentary 1–5 s, brief 6–30 s, sustained explicit.
Speech takes words ÷ 2.5 seconds (min 1 s) and never freezes anyone else.

| Movement | m/s |
|---|---|
| walk / careful / sneak | 1.4 / 1.0 / 0.7 |
| run / sprint (athletics ≥ 1) | 3.5 / 5.5 |
| crawl | 0.3 |
| leg function loss 1 | × 0.6 ; loss 2 on both legs: crawl only |
| load heavy / overloaded | × 0.8 / × 0.6 |

| Action | seconds | noise dB (at 1 m) |
|---|---|---|
| open / close door | 1.5 | 40 (slam 75) |
| lock / unlock with key | 3 | 35 |
| barricade / unbarricade (+1/−1) | 30 | 55 |
| force a door (per attempt) | 5 | 85 |
| search a container / a place | 20 / 120 | 40 |
| pick up / drop / give | 1.5 / 1 / 2 | 20 |
| reload (magazine swap) | 4 | 45 |
| pressure / bandage / tourniquet / suture | 5 / 60 / 30 / 600 | 20 |
| eat / drink | 300 / 30 | 20 |
| take cover / hide / crouch / stand / go prone | 2 / 4 / 1 / 1 / 2 | 30 |
| climb a low / high fence | 4 / 8 | 50 |
| 9 mm shot / shotgun / rifle (unsuppressed) | 0.5 | 160 / 165 / 165 |
| melee strike / scream | 1 / 2 | 60 / 95 |

## 3. Sound: the audibility compiler (`sense/acoustics.py`)

```
same place:  received = source_dB - k * log2(max(d, 1))      k = 4.5 indoor, 6.0 outdoor
other place: min-loss path over portals incl. walls:
             received = source_dB - k_src * log2(max(d_total, 1)) - Σ portal loss
             portal loss = open_loss_db when open, else seal_db * (1 - damage/4)
margin = received - max(ambient, loudest other sound - 3) - 4 (if the listener is talking/focused)
EXACT >= 12 | PARTIAL >= 5 | TONE_ONLY >= 0 | NONE
```
Ambient: place ambient, plus wind (level × 8 dB) and rain (50) / storm (65) floors outdoors, minus
(warning slack − 5) dB. Sleepers register only ≥ 55 dB received, at tone only, and wake. Default
material seals: glass 20, drywall 30, wood 25, brick 45, concrete 50, metal 40. **Privacy is a
physical outcome, never a declaration** (CROWD-02). Whispering is visible.
Partial speech keeps a deterministic ~59 % of words per listener (AUD-07), so two partial listeners
hear different fragments and form different wrong beliefs.

## 4. Sight (`sense/optics.py`)

`score = light + (attr_mod(P) − 3) − floor(distance/10) − concealment − 2·hidden + moved`;
clear ≥ 3, partial ≥ 1, silhouette ≥ −1, else none. Line of sight: same place, or one open/
transparent portal with one side within 3 m of it. Thermal observers treat light ≤ 1 as 4. A
visible act (leaning close, passing something low, whispering) produces a visual percept with an
inference hint even when nothing was heard (CROWD-05).

## 5. Harm, bleeding, death (`physical/bodies.py`)

No hit points. A wound: anatomy, type, severity, bleed rate, pain, contamination, function loss,
cause, treatment history, next due time.

| Severity | Bleed %/min untreated | Meaning |
|---|---|---|
| minor | 0.05 (clots after 10 min) | function 0 |
| significant | 1.0 | function −1; critical (30 %) in ~30 min |
| severe | 3.0 | function −2; critical in ~10 min |
| catastrophic | 12.0 | death (40 %) in ~3.3 min without effective pressure |

Treatment multipliers (the strongest one applied counts, they do not multiply together): pressure
×0.25, bandage ×0.5, packing ×0.1, tourniquet ×0.02 (limbs only), suture ×0 (minor and significant
only); cleaning lowers contamination. Function loss applies to limbs only. Unconscious at 30 % blood
loss, dead at 40 %. Impairment steps at 15 % (+1) and 25 % (+2). Nothing heals inside a scene: a
wound heals when it has been treated and its days have passed (3 / 14 / 45 / 120 by severity,
× the recovery-slack factor). Time is integrated minute by minute (`bodies.progress`), so a death
lands in the minute it happened, not at the end of a long wait.

### 5.1 Weapon wounds

| Hit type | CLEAN | COST |
|---|---|---|
| melee light (knife, pipe) | significant | minor |
| melee medium (bat, machete, crowbar) | severe | significant |
| melee heavy (axe, sledge) | severe; catastrophic if margin ≥ 6 on head/neck | significant |
| firearm light (.22) | significant | minor |
| firearm medium (9 mm, .38) | severe; catastrophic on head/neck | significant |
| firearm heavy (rifle, shotgun ≤ 10 m) | catastrophic | severe |

Default anatomy for "centre mass" / body strikes (rng `resolve`, weights): chest 30, abdomen 20,
arm_l 10, arm_r 10, leg_l 10, leg_r 10, head 10. The **head** variants (shoot the head, strike the
head) are only offered to bodies with the skill or belief cue for them, and add +2 resistance.
FAIL: a miss (the round still makes its noise). BREAK: a miss plus a complication — a malfunction
(next shot needs a clear action) or, if another body is within 1 m of the line, that body becomes
the target of a fresh resolution at −2.

### 5.2 The contact chain (common infected)
`0 CONTACT → 1 GRIP → 2 STRIKE (bite/claw on named anatomy) → 3 DOWN → 4 KILL`, advancing only by
an infected action inside a conflict group; reversed only by a physical interrupt (destroy the
brainstem/upper spine, break the grip, interpose an object or portal, another body intervening, the
infected body failing mechanically). Speech is not an interrupt. A bite through skin → wet-strain
exposure with the pathway's probability (content).

### 5.3 Death test
Runs whenever harm lands or a clock comes due, for every body (L12). Humans/animals/Lurkers: dead at
40 % blood loss, any catastrophic head or neck wound, needs stage 6 (thirst, hunger, cold, heat), or
the wet-strain death point. Infected: true death only when the brainstem/upper-spine junction is
destroyed; otherwise false death (a fresh catastrophic wound, or 60 % blood loss) with a
reanimation window drawn from the type. A risen body keeps its wounds and their function loss, but
they no longer bleed and cannot drop it a second time. Death is a state result, never a dramatic
decision.

## 6. Needs (`RulesConfig.needs`)
Stages 0–6. Thirst +1 per 12 h without water (heat multiplies by 1 + (climate_heat − 5) × 0.08),
hunger +1 per 84 h without food, fatigue +1 per 8 h awake. Impairment +1 at stage 3, +2 at 4, +3 at
5; death at 6 for thirst/hunger (fatigue at 6 does not kill: the body collapses asleep).

## 7. Space (`physical/space.py`)
Place graph; anchors are named points with cover/concealment 0–3; portals carry orthogonal facts
(open, locked, lock quality, barricade, damage, aperture, seal, transparency). Walls and fences are
never traversable (you climb a fence with the climb affordance, which moves you to the far side);
sound always crosses them (seal loss); sight crosses only a `transparent` one (a chain-link fence,
never a wall). Body clearance: shoulder width 30–65 cm from mass (Lurkers ×0.5); upright
needs aperture height ≥ 0.9 × body height; crawling needs ≥ 45 cm and takes 4× time. Rooms are
generated on first observation and are permanent afterwards (GEO-03).

## 8. Effect handlers
The complete list and each handler's contract are in `action/effects.py`. Every handler emits
ACTION_START and ACTION_COMPLETE (or BLOCKED/INTERRUPT), emits NOISE when loud, routes state changes
through the owning module, and never reads who controls the body.

## 9. Cascade expression language (`action/cascade.py`)
`<path> <op> <literal>` joined by ` and `; ops `== != >= <= > <`; paths `trigger.payload.<key>`,
`trigger.actor_id`, `trigger.type`, `actor(<path>).<column>`, `settlement_of(<path>).<column>`,
`workplace_of(<path>).<column>`. Literals: integers, floats, `true`/`false`, quoted strings.
A missing payload key makes a comparison false. Settlements also expose derived columns
`days_of_<resource>` and `has_shortage_<resource>`.

**Targets** are selectors (CAS-05) — `actor(...)`, `household_of(...)`, `settlement_of(...)`,
`workplace_of(...)`, `work_assignments_of(...)`, `cover_candidate_for(...)`, `active_task_of(...)`,
`heads_of_households_with_dependents(...)`, `head_of_worst_hit_household(...)`,
`leadership_of(...)`, `group_of(...)`, `infected_within_hearing_of(...)`, `witnesses_of(...)`,
`place_of(...)`, `who_would_hear_of(...)`; the full meaning of each is in `action/cascade.py`.
Payload strings beginning `$` resolve the same way. An empty selection is a no-op (CAS-07).
**Delayed effects** (`schedule_event`, or `delay_s > 0`) go through the `CASCADE_EFFECT` queue and
fire in a later transaction at cascade depth 0 (CAS-06) — which is how the six-hop ECON-01 chain
fits the depth-3 limit (CAS-02).

## 10. Style metrics (`narration/lint.py`) — IRONCLAD Step 2, computed at last

| Metric | Bound |
|---|---|
| passive-voice sentences | ≤ 20 % |
| adverbs (-ly, minus exceptions) | ≤ 8 % of words |
| similes (like a/an/the, as if, as though) | ≤ 1 per 200 words |
| abstract words (content list) | ≤ 3 % of words |
| vague timers (soon, later, eventually, before long …) | 0 |
| banned phrases (content list) / leak phrases | 0 / 0 |
| same two-word sentence opener | ≤ 2 per scene |
| consecutive sentences with the same first word | ≤ 2 |
| length | inside the narration-length band |

(Deviation D-05: the IRONCLAD "concrete noun + verb share ≥ 0.6" needs a part-of-speech tagger;
it is replaced by the abstract-word ratio so the engine stays dependency-free. See DECISIONS.)
