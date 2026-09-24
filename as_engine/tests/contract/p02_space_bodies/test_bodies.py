"""Bodies, wounds, needs, infection, death (P2). Rules HARM-01..07, DEATH-01..05 (physical/bodies.py).

No hit points: a body bleeds a percentage per minute, clots, gets treated, heals only with time and
treatment, and dies when a threshold is crossed. Numbers come from RulesConfig defaults
(significant 1.0 %/min, severe 3.0, catastrophic 12.0; unconscious at 30 %, dead at 40 %).
"""

from __future__ import annotations

import json

import pytest

from as_engine.contracts.common import Anatomy, WoundSeverity, WoundType
from as_engine.contracts.events import Event, EventType, WriteOp, WriteRecord
from as_engine.kernel.clock import MS_PER_DAY, MS_PER_H, MS_PER_MIN
from as_engine.physical import bodies
from as_engine.physical.bodies import WoundSpec
from as_engine.testing.scenario import load_scenario

pytestmark = pytest.mark.phase(2)

START = 30 * MS_PER_DAY + 12 * MS_PER_H

LAB = {
    "schema": "as.scenario.v1", "name": "harm_lab", "seed": 5, "start": {"day": 30, "time": "12:00"},
    "places": [{"id": "room", "name": "Workshop", "width_m": 10, "depth_m": 10,
                "anchors": [{"id": "bench", "name": "bench", "x": 2, "y": 2}]}],
    "bodies": [
        {"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "room", "anchor": "bench",
         "inventory": [{"item": "core:item/glock_19", "slot": "hand_r", "props": {"chambered": False}}]},
        {"id": "subj", "stub": {"name": "Dana Test", "age": 40, "sex": "female", "occupation": "welder"}, "place": "room", "x": 5, "y": 5},
        {"id": "thirsty", "stub": {"name": "Cal Dry", "age": 30, "sex": "male"}, "place": "room", "x": 6, "y": 5, "needs": {"thirst": 5}},
        {"id": "tired", "stub": {"name": "Mo Tired", "age": 30, "sex": "male"}, "place": "room", "x": 7, "y": 5, "needs": {"fatigue": 2}},
        {"id": "sleeper", "stub": {"name": "Lu Nap", "age": 30, "sex": "female"}, "place": "room", "x": 8, "y": 5, "awareness": "asleep", "posture": "lying"},
        {"id": "sham", "infected": "ZOMBIE_ARCHETYPE_SHAMBLER01", "controller": "policy", "place": "room", "x": 9, "y": 9},
        {"id": "runner", "infected": "ZOMBIE_VARIANT_ID_RUNNER01", "controller": "policy", "place": "room", "x": 9, "y": 8},
    ],
}


@pytest.fixture
def lab(fixture_packs, core_pack_dir):
    w = load_scenario(LAB, packs_root=fixture_packs, core_pack_dir=core_pack_dir)
    yield w
    w.store.close()


def body(w, local):
    return dict(w.store.query_one("SELECT * FROM bodies WHERE body_id = ?", (w.id(local),)))


def wounds(w, local):
    return [dict(r) for r in w.store.query("SELECT * FROM wounds WHERE body_id = ? ORDER BY wound_id", (w.id(local),))]


def hit(w, local, anatomy, type_, severity, *, by=None, at=START, contamination=0):
    with w.store.transaction() as tx:
        cause = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=at, turn_index=0,
                                      actor_id=w.id(by) if by else None)).event_id
        return bodies.apply_harm(tx, w.id(local), WoundSpec(Anatomy(anatomy), WoundType(type_), WoundSeverity(severity), contamination),
                                 at, cause, 0, w.rng), cause


def advance(w, local, minutes, *, from_ms=START):
    with w.store.transaction() as tx:
        return bodies.progress(tx, w.id(local), from_ms + int(minutes * MS_PER_MIN), 0, w.rng)


def treat(w, local, wound_id, method):
    with w.store.transaction() as tx:
        return bodies.treat(tx, w.id(local), wound_id, method, w.id("pc"), START, None, 0)


def types(evs):
    return [e.type for e in evs]


# --------------------------------------------------------------------------- wounds
def test_harm_writes_the_wound_and_the_payload(lab, rules):
    evs, cause = hit(lab, "subj", "leg_l", "cut", "significant", by="pc")
    assert types(evs) == [EventType.HARM]
    h = evs[0]
    (wd,) = wounds(lab, "subj")
    assert h.payload == {"wound_id": wd["wound_id"], "body_id": lab.id("subj"), "actor_id": lab.id("pc"), "anatomy": "leg_l",
                         "anatomy_group": "leg", "type": "cut", "severity": "significant", "function_loss": 1,
                         "bleed_pct_per_min": rules.harm.bleed_pct_per_min["significant"], "contamination": 0}
    assert (wd["pain"], wd["clotted"], wd["created_at"], wd["cause_event"], wd["next_due_at"], json.loads(wd["treatment"])) == (1, 0, START, cause, None, [])
    assert (body(lab, "subj")["pain"], body(lab, "subj")["impairment"]) == (1, 0)


def test_an_infected_attacker_is_not_an_actor(lab):
    evs, _ = hit(lab, "subj", "arm_l", "bite", "significant", by="sham")
    assert evs[0].payload["actor_id"] is None and evs[0].actor_id is None


@pytest.mark.parametrize("anatomy,severity,loss", [
    ("chest", "significant", 0), ("abdomen", "severe", 0), ("arm_r", "significant", 1), ("hand_l", "severe", 2),
    ("leg_r", "catastrophic", 2), ("foot_l", "minor", 0),
])
def test_function_loss_is_for_limbs(lab, anatomy, severity, loss):
    evs, _ = hit(lab, "subj", anatomy, "stab", severity)
    assert evs[0].payload["function_loss"] == loss


def test_a_minor_wound_has_a_clot_time(lab, rules):
    evs, _ = hit(lab, "subj", "arm_l", "cut", "minor")
    assert wounds(lab, "subj")[0]["next_due_at"] == START + int(rules.harm.minor_clot_min * MS_PER_MIN)


# --------------------------------------------------------------------------- bleeding
@pytest.mark.parametrize("method,mult_attr", [(None, None), ("pressure", "pressure_mult"), ("packing", "packing_mult"),
                                              ("tourniquet", "tourniquet_mult"), ("bandage", "bandage_mult"), ("suture", "suture_mult")])
def test_bleeding_and_treatment_multipliers(lab, rules, method, mult_attr):
    hit(lab, "subj", "leg_l", "cut", "significant")
    wid = wounds(lab, "subj")[0]["wound_id"]
    if method:
        treat(lab, "subj", wid, method)
    advance(lab, "subj", 10)
    mult = getattr(rules.harm, mult_attr) if mult_attr else 1.0
    assert body(lab, "subj")["blood_loss_pct"] == pytest.approx(10 * rules.harm.bleed_pct_per_min["significant"] * mult)
    assert body(lab, "subj")["progressed_at"] == START + 10 * MS_PER_MIN


def test_the_strongest_treatment_counts_not_the_product(lab, rules):
    hit(lab, "subj", "leg_l", "cut", "significant")
    wid = wounds(lab, "subj")[0]["wound_id"]
    treat(lab, "subj", wid, "pressure")
    treat(lab, "subj", wid, "packing")
    advance(lab, "subj", 10)
    assert body(lab, "subj")["blood_loss_pct"] == pytest.approx(10 * min(rules.harm.pressure_mult, rules.harm.packing_mult))


def test_effective_bleed_is_the_same_rule(lab, rules):
    """effective_bleed (used by packets for the word 'bleeding') agrees with progress()."""
    hit(lab, "subj", "leg_l", "cut", "significant")
    wid = wounds(lab, "subj")[0]["wound_id"]
    assert bodies.effective_bleed(lab.store, wid) == pytest.approx(rules.harm.bleed_pct_per_min["significant"])
    treat(lab, "subj", wid, "bandage")
    assert bodies.effective_bleed(lab.store, wid) == pytest.approx(rules.harm.bleed_pct_per_min["significant"] * rules.harm.bandage_mult)
    treat(lab, "subj", wid, "suture")
    assert bodies.effective_bleed(lab.store, wid) == 0.0, "suture multiplier 0.0"
    hit(lab, "subj", "arm_l", "cut", "minor")
    minor = wounds(lab, "subj")[1]["wound_id"]
    advance(lab, "subj", rules.harm.minor_clot_min + 1)
    assert bodies.effective_bleed(lab.store, minor) == 0.0, "clotted"


def test_treatment_limits(lab):
    hit(lab, "subj", "chest", "stab", "severe", contamination=2)
    wid = wounds(lab, "subj")[0]["wound_id"]
    with pytest.raises(ValueError):
        treat(lab, "subj", wid, "tourniquet")  # not a limb
    with pytest.raises(ValueError):
        treat(lab, "subj", wid, "suture")  # too big to suture
    with pytest.raises(ValueError):
        treat(lab, "subj", wid, "prayer")
    ev = treat(lab, "subj", wid, "clean")
    assert ev.type == EventType.TREATMENT and ev.payload["method"] == "clean"
    wd = wounds(lab, "subj")[0]
    assert wd["contamination"] == 1 and json.loads(wd["treatment"]) == ["clean"]


def test_minor_wounds_clot(lab, rules):
    hit(lab, "subj", "arm_l", "cut", "minor")
    evs = advance(lab, "subj", 30)
    wd = wounds(lab, "subj")[0]
    assert wd["clotted"] == 1 and wd["next_due_at"] is None
    assert body(lab, "subj")["blood_loss_pct"] == pytest.approx(rules.harm.bleed_pct_per_min["minor"] * rules.harm.minor_clot_min)
    clots = [e for e in evs if e.type == EventType.WOUND_PROGRESS and e.payload.get("change") == "clotted"]
    assert len(clots) == 1 and clots[0].at == START + int(rules.harm.minor_clot_min * MS_PER_MIN)


# --------------------------------------------------------------------------- death
def test_bleeding_out_unconscious_then_dead(lab):
    """Severe abdomen, 3 %/min: 30 % at minute 10 (unconscious), 42 % at minute 14 (>= 40: dead)."""
    _, cause = hit(lab, "subj", "abdomen", "stab", "severe", by="pc")
    evs = advance(lab, "subj", 20)
    aw = [e for e in evs if e.type == EventType.AWARENESS_CHANGE]
    death = [e for e in evs if e.type == EventType.DEATH]
    assert len(aw) == 1 and aw[0].at == START + 10 * MS_PER_MIN and aw[0].payload["awareness"] == "unconscious"
    assert len(death) == 1 and death[0].at == START + 14 * MS_PER_MIN
    # P10: a human who dies without a destroyed head or neck will rise (rise_pending, a REANIMATION row)
    assert death[0].payload == {"body_id": lab.id("subj"), "cause": "blood_loss", "cause_event_id": cause,
                                "rise_pending": True}
    b = body(lab, "subj")
    assert (b["alive"], b["dead_at"], b["awareness"], b["posture"], b["death_event"]) == (0, START + 14 * MS_PER_MIN, "dead", "lying", cause)
    assert b["blood_loss_pct"] == pytest.approx(42.0), "a dead body stops bleeding"
    assert not bodies.is_alive(lab.store, lab.id("subj"))
    later = advance(lab, "subj", 60, from_ms=START)
    assert not [e for e in later if e.type in (EventType.DEATH, EventType.AWARENESS_CHANGE)], "nobody dies twice"


@pytest.mark.parametrize("anatomy,cause", [("head", "head_wound"), ("neck", "neck_wound")])
def test_catastrophic_head_or_neck_kills_at_once(lab, anatomy, cause):
    evs, _ = hit(lab, "subj", anatomy, "gunshot", "catastrophic", by="pc")
    assert types(evs) == [EventType.HARM, EventType.DEATH] and evs[1].payload["cause"] == cause
    assert body(lab, "subj")["alive"] == 0


def test_thirst_kills_at_stage_six(lab, rules):
    """thirst 5 at load -> last drink 60 h ago; stage 6 at +12 h -> dead at that step's end."""
    evs = advance(lab, "thirsty", 12 * 60 + 5)
    stage = [e for e in evs if e.type == EventType.NEED_STAGE]
    assert stage[-1].payload == {"body_id": lab.id("thirsty"), "need": "thirst", "stage": 6}
    death = [e for e in evs if e.type == EventType.DEATH]
    assert death and death[0].at == START + int(rules.needs.thirst_stage_every_h * MS_PER_H)
    assert death[0].payload["cause"] == "thirst" and death[0].payload["cause_event_id"] is None


def test_need_stages_raise_impairment(lab):
    """fatigue 2 at load (16 h awake) -> stage 3 at +8 h -> impairment 1 (HARM-07)."""
    evs = advance(lab, "tired", 8 * 60)
    assert [e.payload for e in evs if e.type == EventType.NEED_STAGE] == [{"body_id": lab.id("tired"), "need": "fatigue", "stage": 3}]
    imp = [e for e in evs if e.type == EventType.IMPAIRMENT_CHANGE]
    assert imp and imp[-1].payload == {"body_id": lab.id("tired"), "impairment": 1}
    assert body(lab, "tired")["impairment"] == 1 == bodies.impairment(lab.store, lab.id("tired"))


def test_exhaustion_collapses_but_never_kills(lab, rules):
    """fatigue 2 at load; stage 6 is 4 more periods away -> the body falls asleep, alive."""
    evs = advance(lab, "tired", 4 * rules.needs.fatigue_stage_every_h * 60 + 1)
    aw = [e for e in evs if e.type == EventType.AWARENESS_CHANGE]
    assert aw and aw[0].payload["awareness"] == "asleep"
    assert aw[0].at == START + int(4 * rules.needs.fatigue_stage_every_h * MS_PER_H)
    b = body(lab, "tired")
    assert (b["alive"], b["awareness"], b["posture"]) == (1, "asleep", "lying")


def _expose(w, local, pathway, hours_ago, stage):
    with w.store.transaction() as tx:
        tx.commit_event(Event(type=EventType.INFECTION_EXPOSURE, writer="physical.bodies", at=START, turn_index=0, writes=[
            WriteRecord(op=WriteOp.INSERT, table="infections", values={
                "body_id": w.id(local), "pathway": pathway, "exposed_at": START - int(hours_ago * MS_PER_H),
                "stage": stage, "cause_event": "test", "known_to_self": 0})]))


def test_infection_stages_advance_and_wet_strain_kills(lab, canon):
    wet = canon.find("pathway", "wet")
    _expose(lab, "subj", "wet", wet.stages[1].starts_at_h - 0.5, wet.stages[0].name)
    evs = advance(lab, "subj", 60)
    st = [e.payload for e in evs if e.type == EventType.INFECTION_STAGE]
    assert st == [{"body_id": lab.id("subj"), "pathway": "wet", "stage": wet.stages[1].name}]
    _expose(lab, "tired", "wet", wet.death_at_h - 0.5, wet.stages[-1].name)
    evs = advance(lab, "tired", 60)
    death = [e for e in evs if e.type == EventType.DEATH]
    assert death and death[0].payload["cause"] == "infection" and death[0].payload["rise_pending"] is True
    assert death[0].at == START + 30 * MS_PER_MIN


# --------------------------------------------------------------------------- infected (false death)
def test_infected_false_death_then_rise_then_true_kill(lab, canon):
    t = canon.find("infected", "ZOMBIE_ARCHETYPE_SHAMBLER01")
    lo, hi = (round(h * 60) for h in t.reanimation_window_h)
    evs, _ = hit(lab, "sham", "chest", "gunshot", "catastrophic", by="pc")
    assert types(evs) == [EventType.HARM, EventType.FALSE_DEATH]
    until = evs[1].payload["false_dead_until"]
    assert START + lo * MS_PER_MIN <= until <= START + hi * MS_PER_MIN
    draw = lab.store.query("SELECT * FROM prng_ledger WHERE stream = 'infected'")
    assert len(draw) == 1 and draw[0]["purpose"] == f"false_death:{lab.id('sham')}" and draw[0]["n"] == hi - lo + 1
    b = body(lab, "sham")
    assert (b["alive"], b["awareness"], b["posture"], b["false_dead_until"], b["core_intact"]) == (1, "unconscious", "lying", until, 1)
    evs = advance(lab, "sham", (until - START) / MS_PER_MIN)
    rise = [e for e in evs if e.type == EventType.REANIMATION]
    assert len(rise) == 1 and rise[0].at == until
    b = body(lab, "sham")
    assert (b["awareness"], b["false_dead_until"], b["blood_loss_pct"]) == ("awake", None, 0.0)
    assert all(w["clotted"] == 1 for w in wounds(lab, "sham")), "it rises with the hole, which no longer bleeds"
    again = advance(lab, "sham", 30, from_ms=until)
    assert not [e for e in again if e.type == EventType.FALSE_DEATH], "the wound that dropped it does not drop it twice"
    evs, _ = hit(lab, "sham", "head", "gunshot", "catastrophic", by="pc", at=until)
    assert types(evs) == [EventType.HARM, EventType.DEATH]
    b = body(lab, "sham")
    assert (b["alive"], b["core_intact"]) == (0, 0)


def test_a_cut_to_the_head_does_not_destroy_the_core(lab):
    evs, _ = hit(lab, "runner", "head", "cut", "catastrophic")
    assert types(evs) == [EventType.HARM, EventType.FALSE_DEATH]
    assert body(lab, "runner")["core_intact"] == 1


def test_infected_false_death_at_sixty_percent(lab, rules):
    hit(lab, "sham", "abdomen", "stab", "severe")
    evs = advance(lab, "sham", 25)
    fd = [e for e in evs if e.type == EventType.FALSE_DEATH]
    minutes = rules.harm.infected_false_death_at_blood_loss_pct / rules.harm.bleed_pct_per_min["severe"]
    assert len(fd) == 1 and fd[0].at == START + int(minutes * MS_PER_MIN)
    assert not [e for e in evs if e.type == EventType.DEATH], "blood loss never truly kills the infected"


# --------------------------------------------------------------------------- capacity / impairment / healing
def test_capacity(lab):
    c = bodies.capacity(lab.store, lab.id("pc"))
    assert (c.mobile, c.hands_free, c.can_speak, c.conscious) == (True, 1, True, True)  # the Glock fills the right hand
    hit(lab, "pc", "arm_r", "stab", "severe")
    assert bodies.capacity(lab.store, lab.id("pc")).hands_free == 1, "the right hand was already full"
    hit(lab, "pc", "hand_l", "crush", "severe")
    assert bodies.capacity(lab.store, lab.id("pc")).hands_free == 0
    hit(lab, "pc", "leg_l", "blunt", "severe")
    assert bodies.capacity(lab.store, lab.id("pc")).mobile is True, "one leg still works"
    hit(lab, "pc", "leg_r", "blunt", "severe")
    assert bodies.capacity(lab.store, lab.id("pc")).mobile is False
    s = bodies.capacity(lab.store, lab.id("sleeper"))
    assert (s.conscious, s.mobile, s.can_speak) == (False, False, False)


def test_impairment_formula(lab):
    """pain 4 -> 2, blood loss 15 % -> 1 (HARM-07); capped at 6."""
    hit(lab, "subj", "leg_l", "stab", "severe")
    hit(lab, "subj", "leg_r", "stab", "severe")
    assert body(lab, "subj")["pain"] == 4 and bodies.impairment(lab.store, lab.id("subj")) == 2
    advance(lab, "subj", 3)  # 2 wounds x 3 %/min x 3 min = 18 %
    assert body(lab, "subj")["blood_loss_pct"] == pytest.approx(18.0)
    assert bodies.impairment(lab.store, lab.id("subj")) == 3 == body(lab, "subj")["impairment"]


def test_healing_needs_treatment_and_time(lab, rules):
    three_days_ago = START - int(rules.harm.heal_days_per_severity["minor"] * MS_PER_DAY)
    hit(lab, "subj", "arm_l", "cut", "minor", at=three_days_ago)
    hit(lab, "subj", "arm_r", "cut", "minor", at=three_days_ago)
    treated, untreated = (w["wound_id"] for w in wounds(lab, "subj"))
    treat(lab, "subj", treated, "bandage")
    evs = advance(lab, "subj", 1)
    healed = {w["wound_id"]: w["healed_at"] for w in wounds(lab, "subj")}
    assert healed[treated] == three_days_ago + int(rules.harm.heal_days_per_severity["minor"] * MS_PER_DAY)
    assert healed[untreated] is None, "an untreated wound never heals"
    assert [e.payload["wound_id"] for e in evs if e.payload.get("change") == "healed"] == [treated]
