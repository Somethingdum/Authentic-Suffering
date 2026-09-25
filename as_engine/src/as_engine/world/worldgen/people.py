"""WG6 — the people: authored characters first, then generated ones, their homes, posts, ties and
what they know (P10). Rules WG-26..29, SOC-01, WG-34, DEMO-02, CONSERVE-04, L11. docs/as/06_WORLD.md
§1.3. Code decides who exists (rng streams 'worldgen:people' and f"names:{settlement_id}"); the
model only writes the words of some dossiers (WORLDGEN_ACTOR). Events: origin 'worldgen', turn_index
0, at = ``at``. T = tables.DETAIL_TIERS[detail]; values = params.flat_values(params); dsf =
params.days_since_fall; round = params.rnd.

The HOME settlement = history.home_settlement(plan, region.start_zone_id).

WG-26 Pack actors. The canon actor records (not PCs), by ref. Skipped, and listed in the worldgen
  report with the reason, when: days_since_fall_range excludes dsf ("needs a world <a>-<b> years
  after the Fall", WG-34); or it has faction memberships (social.memberships with a faction ref) and
  none of those factions is planned ("their faction is not in this region"). The rest are placed:
  in their faction's settlement when it has one, else in the settlements in plan order, cycling.
  Pack actors are never killed or dropped by worldgen for any other reason (protected).

WG-27 Posts and people. generated = max(T['detailed_actors'] - placed pack actors, the home posts
  below + the leaders slot 2 needs) — the home's work and every settlement's leader always have
  someone. Slots are filled in this order until ``generated`` people exist:
    1 the home settlement's posts: pump_operator 6-18, pump_operator 18-6 (water_pump), cook 6-20
      (kitchen), quartermaster (no workplace: the settlement's trader, SOC-03), watcher 6-18,
      watcher 18-6 (watch), medic 8-20 (clinic, when there is one), gardener 6-18 (garden, when there
      is one);
    2 a leader for each settlement's group, home first then plan order (role 'leader') — except a
      faction whose record's first leader names a pack actor placed in that settlement: that actor
      leads and no one is generated for it; P10: then, for that settlement, one person per OTHER
      leader of the record that has a ``seat`` and names no placed pack actor (record order):
      occupation = the leader's title, skill ('leadership', 2), age = rng.range_int(*leader.age,
      purpose f"seat_age:{n}") when the leader gives one, group_members role = the seat (the
      Top-Hat Council and the Front Man; Ghosts_6 leaves their names to each world);
    3 residents: the home settlement, then the others in plan order, cycling, one at a time.
  A post or leader is an adult (band 'adult'); a resident's band = rng.weighted over the
  settlement's cohort counts by band (purpose f"band:{n}"), and its sex likewise over that band's
  cohorts. Every generated person is MATERIALISED from its settlement's cohort of that band and sex
  (society.population.materialise, which decrements it — never below zero: a band with no one left
  is skipped for the next best by count; a settlement with no one left takes no more residents).
  Redraws and fallbacks use the same stream; a band draw is made only for residents.
  PersonSeed per generated person (in slot order, n from 0): name = rng.choice of the names record's
  given names for the sex and family names (purposes f"given:{n}", f"family:{n}", stream
  f"names:{settlement_id}"), redrawn up to 8 times while a living body already has that display
  name or a person seeded earlier in this stage does; age = rng.range_int in the band's range (the contracts.common.AgeBand ranges:
  infant 0-2, child 3-11, preteen 12-14, teen 15-19, adult 20-59, elder 60-80); cohort from the age at the Fall (as polity.write_cohorts); occupation,
  skill (domain, rank): atlas.ROLE_PEOPLE[role] for a post, ('leader', 'leadership', 2) for a
  leader, rng.choice(atlas.FREE_OCCUPATIONS) for an adult or elder resident, ('child', none) for
  younger ones; special = 3 + rng.range_int(0, 4) per letter in 'SPECIAL' order; variant =
  rng.range_int(0, 999). Dossier = skeleton_dossier(seed) (implemented below).
  The FIRST T['llm_dossiers'] generated people (slot order) get a WORLDGEN_ACTOR call each, all
  started together (asyncio.gather) and applied in slot order (P10: await progress(done, total) as each
  answer arrives, whatever its outcome): context WorldgenContext(stage='WG6',
  brief = plain English about the person, their settlement, group and history, fields={'skeleton':
  the skeleton dict, 'settlement': name, 'group': name, 'role': occupation, 'history': [the belief
  texts of the history events whose subjects include their group]}), json_schema = the
  ActorDossier schema, client.call with no output model; the answer (lanes.parse.extract_json of
  the text) must validate as an ActorDossier after the LOCKED fields are copied over it from the
  skeleton: schema, id, generation ('generated'), identity, capability.special,
  capability.skills, days_since_fall_range (None), tags, and (F1a-2, LOOK-10) appearance.looks —
  how a person looks and what they wear is not the model's to rewrite; a failed call, or an answer
  that does not validate, keeps the skeleton (no repair call).
WG-28 Writing (per person, slot order; pack actors first in placement order): the body, needs, a
  position at the settlement site's anchor, the dossier (source 'pack' with its content ref, or
  'generated') and the actor (resolve_max from mind.actor.resolve_max; resolve_cur = resolve_max;
  controller 'model') — society.population.materialise for generated people (which also takes them
  from the cohort), physical.bodies.create + physical.space.place_body + mind.actor.create for pack
  actors after society.population.take_from_cohort of their band and sex (skipped when that cohort is
  empty). Then, per settlement: group_members {role 'leader' for the leader, the seat for a seat
  holder (P10), else 'member', standing
  0 — a pack actor's own membership standing for that faction when it has one —, since = at,
  status 'member'} (MATERIALIZE society.group) and groups.leader_id; households, in slot order: a
  named teen, adult or elder gets their own household (dwelling_place = the settlement site,
  settlement_id, head = them) unless they pair: an 'adult'-band person whose previous 'adult'-band
  person of the settlement (slot order) is of the other sex and still alone joins that household
  as 'partner' when rng.chance(0.5, purpose f"pair:{a}:{b}"); then every named infant, child or
  preteen joins the household of the first named adult of their settlement whose household has no
  child yet (else the first household), role 'child', and that household's head lists them in
  guardian_of (MATERIALIZE society.household per household); work_assignments for posts {workplace_id,
  actor_id, role, shift_start_hh, shift_end_hh, covering_for NULL} and each staffed workplace's
  required_roles = its posts' roles, each role ONCE in post order (one person at a time works a
  post, whichever shift is on: the day and the night pump operator make ['pump_operator'], so a
  cycle with its operator on shift is fully staffed) (MATERIALIZE society.work per workplace; a
  workplace nobody staffs keeps required_roles [] and runs on its unnamed people).
WG-29 Ties and knowledge (SOC-01), per settlement: every named person gets acquaintance of every
  other named person there (known_name = display name, description = mind.perception.
  describe_dossier) and known_places for every place of their zone and every road touching it
  (visited 1 for their site) — one PERCEIVE (writer 'mind.perception', seed: true) per holder;
  relationships per unordered pair (a < b by id): same household -> both ways {kind 'family', trust
  2, affection 2}; else rng.weighted((('positive', 0.2), ('stranger', 0.6), ('rival', 0.2)), purpose
  f"rel:{a}:{b}"): positive -> both ways {kind 'friend', trust 1, affection 1}; rival -> both ways
  {kind 'rival', trust -1, resentment 1}; stranger -> no row (RELATION_CHANGE per row, seed: true,
  no 'delta' key, like the scenario loader). (H1, D-84) Every settlement has somebody who cannot
  stand somebody: its first rival draw between two GENERATED people (the lowest (a, b) in the
  loop above) is a feud instead — both ways {kind 'rival', trust -2, resentment 2} — the pair
  society.settlement STL-15 sets rowing. Generated
  people's tempers come from their variant (skeleton_dossier), so a settlement breaks in
  different ways. History as belief: every named person holds, for every
  history event whose subjects include their group, settlement or zone, a proposition {subject_type
  'event', subject_id = hist_id, predicate 'history', text = belief_text} (believed 1, confidence 2,
  provenance 'common', fidelity 'exact') — the propositions in their PERCEIVE, the holdings in a
  second PERCEIVE citing it (acquired_via), as the scenario loader does.

async write_people(client, rng, tx, plan, region, params, canon, detail, at, progress=None) -> People
  People(pack_placed: [actor ids], generated: [actor ids], skipped: [(ref, reason)], home_settlement_id,
  leaders: {group_id: actor_id}, roles: {actor_id: post role, 'leader' or the seat} for the
  generated posts, leaders and seat holders).

LOOK-10 (the owner's F1a-2: everyone has a visual identity, and people dress for where they live)
  generated_looks(seed) -> dict: a contracts.dossier.Looks as a dict, a pure function of the
  PersonSeed (implemented below): hair (colour by age — grey from 50, white or grey from 70, none
  when shaved or bald; length and, for collar length or longer, a style), facial hair (men of 16
  and over), eyes, a complexion that names the skin, up to two visible marks (never a tattoo on a
  child), and an outfit of core clothing, one piece per slot and layer, chosen by the climate band
  of seed.climate_heat (1-3 cold: a warm top, a heavy outer coat, long legs, boots; 4-7 mild; 8-10
  hot: light top, short or light legs, no coat), by age (under 13: a child's outfit) and by post
  (a medic's scrubs, with clogs where it is not cold, a cook's apron where no coat is needed, a watcher's or raider's
  boots and vest, a gardener's or pump hand's rubber boots). skeleton_dossier's appearance.looks is
  it, and its prose hair, eyes and skin say the same thing. Every generated person is created
  with those looks and dressed in that outfit (society.population.materialise).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...contracts.worldgen import WorldParams
    from ...kernel.rng import Rng
    from ...kernel.store import Tx
    from .history import PolityPlan
    from .region import Region


@dataclass(frozen=True)
class PersonSeed:
    name: str
    age: int
    sex: str
    cohort: str
    occupation: str
    skills: dict[str, int]
    special: dict[str, int]
    variant: int
    settlement_name: str
    group_name: str
    climate_heat: int = 5       # LOOK-10: the region's climate_heat (1-10); what they dress for


@dataclass
class People:
    pack_placed: list[str] = field(default_factory=list)
    generated: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)
    home_settlement_id: str | None = None
    leaders: dict[str, str] = field(default_factory=dict)
    roles: dict[str, str] = field(default_factory=dict)


async def write_people(client, rng: "Rng", tx: "Tx", plan: "PolityPlan", region: "Region",
                       params: "WorldParams", canon, detail: str, at: int, progress=None) -> People:
    raise NotImplementedError("P10")


_BUILD = ("slight", "ordinary", "wiry", "broad", "heavyset")

# LOOK-10 (F1a-2): what anyone can see of a generated person, and what they wear for the climate.
_HAIR_COLOURS = ("black", "dark brown", "brown", "light brown", "auburn", "red", "dark blonde", "blonde", "sandy")
_HAIR_GREYING = ("grey", "greying brown", "iron-grey", "salt-and-pepper")
_HAIR_OLD = ("white", "grey")
_HAIR_LENGTHS = ("cropped", "short", "short", "collar", "shoulder", "long", "shaved", "short")
_HAIR_STYLES = ("", "tied back", "in a rough braid", "matted at the back", "hacked short with a knife", "combed flat", "")
_FACIAL_HAIR = ("none", "stubble", "stubble", "beard", "mustache", "full_beard", "none")
_EYES = ("brown", "dark brown", "hazel", "green", "blue", "grey", "brown")
_SKIN = ("pale skin", "fair skin freckled across the nose", "olive skin", "light brown skin", "brown skin",
         "deep brown skin", "tanned, weathered skin", "ruddy, windburnt skin", "sallow skin")
_MARKS = (("through the left eyebrow", "a pale crescent scar", "near"),
          ("across the back of the right hand", "a ridged burn scar", "near"),
          ("on the side of the neck", "a faded tattoo of a swallow", "near"),
          ("along the jaw", "a thin white scar", "close"),
          ("on the left forearm", "a row of tally marks inked in blue", "near"),
          ("on the bridge of the nose", "a badly set break", "near"),
          ("across the knuckles of both hands", "old split scars", "close"),
          ("on the right cheek", "a pitted pockmark scar", "close"))
_CHILD_MARKS = (("on the chin", "a small white scar", "close"), ("on the back of the left hand", "a healing scrape", "close"))
_OUTER_COLOURS = ("black", "navy", "olive", "grey", "brown", "dark green", "faded red")
_CLOTHES = {   # climate band -> slot -> choices (None = nothing there)
    "cold": {"top": ("thermal_top", "turtleneck", "thermal_top"), "outer": ("parka", "car_coat", "fleece_jacket", "parka"),
             "legs": ("work_pants", "cargo_pants", "jeans"), "feet": ("combat_boots", "rubber_boots")},
    "mild": {"top": ("t_shirt", "button_down_shirt", "hooded_sweatshirt", "polo_shirt", "t_shirt"),
             "outer": ("denim_jacket", "fleece_jacket", "running_jacket", "cardigan", None, None),
             "legs": ("jeans", "cargo_pants", "work_pants", "long_skirt", "leggings"),
             "feet": ("sneakers", "combat_boots", "rubber_boots", "sneakers")},
    "hot": {"top": ("tank_top", "t_shirt", "athletic_top", "button_down_shirt"), "outer": (None,),
            "legs": ("cargo_shorts", "skort", "long_skirt", "jeans"), "feet": ("sneakers", "clogs", "sneakers")},
}
_CHILD_CLOTHES = {
    "cold": {"top": ("thermal_top", "hooded_sweatshirt"), "outer": ("parka", "car_coat"), "legs": ("jeans", "leggings"),
             "feet": ("rubber_boots", "sneakers")},
    "mild": {"top": ("t_shirt", "hooded_sweatshirt"), "outer": (None, "denim_jacket"), "legs": ("jeans", "leggings"),
             "feet": ("sneakers",)},
    "hot": {"top": ("t_shirt", "tank_top"), "outer": (None,), "legs": ("cargo_shorts", "skort"), "feet": ("sneakers",)},
}
_TRADE_FEET = {"watcher": "combat_boots", "raider": "combat_boots", "hunter": "combat_boots", "tracker": "combat_boots",
               "scavenger": "combat_boots", "gardener": "rubber_boots", "pump_operator": "rubber_boots"}
_TRADE_LEGS = {"watcher": "cargo_pants", "raider": "cargo_pants", "hunter": "cargo_pants", "gardener": "work_pants",
               "builder": "work_pants", "mechanic": "work_pants", "pump_operator": "work_pants"}


def _climate_band(heat: int) -> str:
    return "cold" if heat <= 3 else "hot" if heat >= 8 else "mild"


def generated_looks(seed: "PersonSeed") -> dict:
    """LOOK-10 (implemented; deterministic): a Looks dict — hair, eyes, skin, marks and a climate-fit
    outfit — from the seed alone."""
    v, age, child = seed.variant, seed.age, seed.age < 13
    length = _HAIR_LENGTHS[(v // 3) % len(_HAIR_LENGTHS)]
    if seed.sex == "male" and age >= 60 and v % 5 == 0:
        length = "bald"
    if length in ("shaved", "bald"):
        colour = ""
    elif age >= 70:
        colour = _HAIR_OLD[v % len(_HAIR_OLD)]
    elif age >= 50:
        colour = _HAIR_GREYING[v % len(_HAIR_GREYING)]
    else:
        colour = _HAIR_COLOURS[v % len(_HAIR_COLOURS)]
    style = _HAIR_STYLES[(v // 7) % len(_HAIR_STYLES)] if length in ("collar", "shoulder", "long") else ""
    facial = _FACIAL_HAIR[(v // 5) % len(_FACIAL_HAIR)] if seed.sex == "male" and age >= 16 else "none"
    if child:
        marks = [_CHILD_MARKS[v % len(_CHILD_MARKS)]] if v % 3 == 1 else []
    else:
        n = v % 3
        first = (v // 17) % len(_MARKS)
        marks = [_MARKS[(first + 3 * i) % len(_MARKS)] for i in range(n)]
    band = _climate_band(seed.climate_heat)
    table = (_CHILD_CLOTHES if child else _CLOTHES)[band]
    top = table["top"][v % len(table["top"])]
    outer = table["outer"][(v // 2) % len(table["outer"])]
    legs = table["legs"][(v // 3) % len(table["legs"])]
    feet = table["feet"][(v // 4) % len(table["feet"])]
    occ = "" if child else seed.occupation
    body = None
    if occ == "medic":
        body, top, legs, feet = "scrubs", None, None, ("combat_boots" if band == "cold" else "clogs")
        if band == "mild":
            outer = "cardigan"
        elif band == "cold":
            outer = "parka"          # scrubs are thin: the heaviest coat over them
    feet = _TRADE_FEET.get(occ, feet)
    legs = _TRADE_LEGS.get(occ, legs) if legs is not None else None
    if occ == "cook" and band != "cold":
        outer = "apron"
    if occ in ("watcher", "raider") and band != "cold":
        outer = "tactical_vest"
    state = "soiled" if v % 5 == 0 else "torn" if v % 7 == 3 else "worn"
    outfit = []
    for i, item in enumerate((body, top, outer, legs, feet)):
        if item is None:
            continue
        piece = {"item": f"core:item/{item}", "state": state if not outfit else "worn"}
        if item == outer and i == 2 and item not in ("apron", "tactical_vest"):
            piece["colour"] = _OUTER_COLOURS[(v // 11) % len(_OUTER_COLOURS)]
        outfit.append(piece)
    if band == "hot" and not child and v % 4 == 0:
        outfit.append({"item": "core:item/bandana", "state": "worn"})
    if age >= 60 and v % 3 == 0:
        outfit.append({"item": "core:item/reading_glasses", "state": "worn"})
    elif not child and v % 11 == 0:
        outfit.append({"item": "core:item/glasses", "state": "worn"})
    return {"hair_colour": colour, "hair_length": length, "hair_style": style, "facial_hair": facial, "facial_hair_words": "",
            "eye_colour": _EYES[(v // 2) % len(_EYES)], "complexion": _SKIN[(v // 13) % len(_SKIN)],
            "marks": [{"where": w, "what": what, "shows": shows} for w, what, shows in marks], "outfit": outfit}


def _hair_words(looks: dict) -> str:
    if looks["hair_length"] in ("shaved", "bald"):
        return "shaved head" if looks["hair_length"] == "shaved" else "bald"
    style = f", {looks['hair_style']}" if looks["hair_style"] else ""
    return f"{looks['hair_length']} {looks['hair_colour']} hair{style}"
_TRAITS = (
    ("careful", "checks every door twice", "a noise at night", "is slow to move", "loses time",
     "made everyone wait at the gate while the street was checked"),
    ("blunt", "says the hard thing first", "a bad plan", "people stop asking", "few friends",
     "told the council the water would not last the month"),
    ("generous", "shares food before being asked", "a hungry child", "goes without", "is often hungry",
     "gave away a week of rations in the first winter"),
    ("suspicious", "watches strangers' hands", "a new face", "keeps people at arm's length", "is left out",
     "refused to let a sick traveller through until morning"),
    ("restless", "cannot sit through a meeting", "being told to wait", "volunteers for runs", "takes risks",
     "went out alone for a part nobody else would fetch"),
    ("dutiful", "turns up for every shift early", "a job needing doing", "takes on extra work", "is always tired",
     "covered two shifts in the storm week"),
)
_VOICES = (
    ("short sentences", "talks about the work"),
    ("asks questions instead of answering", "uses people's names"),
    ("dry jokes", "understates everything"),
    ("long explanations", "repeats the important part"),
)
_EXEMPLARS = (
    ("Pump's running. Could be worse.", "Get inside. Now.", "I can't. I just can't do it again."),
    ("You eaten today? Sit down a minute.", "Everybody quiet. Listen.", "Don't make me choose. Please."),
    ("Nice day for the end of the world.", "Move. Talk later.", "That's it. I'm done carrying this."),
    ("Here's how it works, and here's why.", "Stop. Think. Which way did it come?", "I told you. I told all of you."),
)


# H1 (D-84): generated people break in different ways — a settlement is not a room of saints.
_FUSES: tuple[int, ...] = (3, 2, 4, 3, 1, 3, 5, 2, 4, 3)
_OUTLETS: tuple[str, ...] = ("words", "fists", "cold", "words", "tears", "fists", "flight", "words", "cold", "fists")
_PEEVES: tuple[str, ...] = (
    "people taking more than their share", "being talked down to", "waste", "lazy watch shifts",
    "anyone touching their things", "being told what to do by someone who does no work", "whining",
    "people who lie about little things",
)
_SETTLERS: tuple[str, ...] = (
    "a long walk on the wall", "hard work until the arms ache", "an hour alone", "a smoke",
    "talking it out the next day", "a drink, when there is one",
)


def skeleton_dossier(seed: PersonSeed) -> dict:
    """A VALID generated ActorDossier dict from a PersonSeed (implemented; deterministic).
    Plain but specific enough to pass CNT-10; ``variant`` picks among the small tables above, so two
    people with different variants sound and behave differently. WORLDGEN_ACTOR may replace every
    unlocked field of it."""
    v = seed.variant
    first = seed.name.split()[0]
    adult = seed.age >= 16
    t1, t2 = _TRAITS[v % len(_TRAITS)], _TRAITS[(v // len(_TRAITS) + 1 + v) % len(_TRAITS)]
    if t2 == t1:
        t2 = _TRAITS[(v + 1) % len(_TRAITS)]
    tend = _VOICES[v % len(_VOICES)]
    ex = _EXEMPLARS[(v // 7) % len(_EXEMPLARS)]
    skills = [{"domain": d, "rank": r, "evidence": f"{first} learned it the hard way at {seed.settlement_name}."}
              for d, r in sorted(seed.skills.items())]
    looks = generated_looks(seed)
    work = seed.occupation if adult else "child"
    return {
        "schema": "as.actor.v1", "id": "gen_" + "".join(c if c.isalnum() else "_" for c in seed.name.lower()),
        "generation": "generated",
        "identity": {"name": seed.name, "age": seed.age, "sex": seed.sex, "cohort": seed.cohort,
                     "birthplace": "somewhere in the region", "occupation_before": work if adult else "school",
                     "occupation_now": work,
                     "one_line": f"{seed.name}, {'a ' + work if adult else 'a child'} at {seed.settlement_name}."},
        "appearance": {"height_cm": (160 + (v % 30)) if adult else (90 + seed.age * 5),
                       "mass_kg": (55 + (v % 40)) if adult else (12 + seed.age * 3),
                       "build": _BUILD[v % len(_BUILD)], "hair": _hair_words(looks), "eyes": looks["eye_colour"],
                       "skin": looks["complexion"],
                       "distinguishing_marks": [f"{m['what']} {m['where']}" for m in looks["marks"]] or ["nothing anyone remembers"],
                       "clothing_usual": "patched work clothes" if adult else "hand-me-downs two sizes big",
                       "movement_under_stress": "moves quickly and keeps to the walls",
                       "habit_gesture": ("rubs the back of the neck", "taps two fingers on anything near",
                                         "cracks the knuckles")[v % 3],
                       "relation_to_appearance": "does not think about it", "looks": looks},
        "capability": {"special": dict(seed.special), "skills": skills, "literacy": 2 if adult else 1,
                       "tech_literacy": 1},
        "motive": {"motive": f"keep {seed.group_name} fed and safe", "method": "does the work assigned, and some more",
                   "moral_line": {"will": ["work a double shift"], "wont": ["steal from the common store"],
                                  "wont_tags": ["steal"]},
                   "inner_conflict": "wants to leave and cannot abandon the others",
                   "past_wound": "lost family in the first week of the Fall",
                   "signature_behaviour": ("counts the water jugs every evening", "sleeps in boots",
                                           "keeps a list of the dead in a notebook")[v % 3],
                   "risk_threshold": 3 + v % 4, "risk_text": "takes risks only for people they know",
                   "resource_constraints": "owns what fits in one bag"},
        "persona": {"public": {"shown_traits": [t1[0]], "claimed_history": f"came to {seed.settlement_name} early",
                               "presented_affiliation": seed.group_name},
                    "private": {"true_goals": ["keep the people they love alive"], "concealed_history": "none worth telling",
                                "real_affiliation": "their own people"}},
        "traits": [dict(zip(("tag", "manifests", "triggers", "causes", "costs", "example"), t1)),
                   dict(zip(("tag", "manifests", "triggers", "causes", "costs", "example"), t2))],
        "contradictions": [{"belief_a": f"{seed.group_name} comes first", "belief_b": "family comes first",
                            "a_wins_when": "the stores are full", "b_wins_when": "the stores are low"}],
        "decision_stack": {"layers": ["family", "own safety", seed.group_name, "strangers"],
                           "inversion_conditions": ["a raid on the settlement"],
                           "past_example": "stayed on the wall during a raid instead of running home"},
        "silence": {"goes_quiet_when": ["the dead are mentioned", "leaders argue"],
                    "body_when_silent": "arms folded, looking at the floor",
                    "comfortable_vs_uncomfortable": "comfortable at work, uncomfortable in meetings"},
        "knowledge": {"knows": [f"the ways in and out of {seed.settlement_name}"]},
        "voice": {"capsule": f"{first} speaks plainly; {tend[0]}, and {tend[1]}.",
                  "speech_tendencies": list(tend),
                  "exemplars": {"low_stakes": ex[0], "under_pressure": ex[1], "at_the_limit": ex[2]},
                  "would_never_say": ["Let them starve.", "Not my problem.", "Whatever you say, boss."],
                  "profanity": ("rare", "none", "rare", "frequent")[v % 4]},
        "social": {"household_role": "", "relations": [], "dependents": [], "guardians": [], "memberships": []},
        "life": {"aspiration": "a quiet year", "current_project": f"keeping up with the work at {seed.settlement_name}",
                 "fears": [("the pump failing", "a fever in the camp", "the night watch sleeping")[v % 3]]},
        "disposition": {"archetype_prior": "civilized", "toward_strangers": ("wary", "neutral", "warm")[v % 3],
                        "encounter_default": "calls for the watch and keeps distance"},
        "temper": {"fuse": _FUSES[(v // 5) % len(_FUSES)], "outlet": _OUTLETS[(v // 11) % len(_OUTLETS)],
                   "grudge": (v // 7) % 4, "pet_peeves": [_PEEVES[(v // 3) % len(_PEEVES)]],
                   "cools_down_by": _SETTLERS[(v // 13) % len(_SETTLERS)]},
        "tags": ["generated"],
    }
from ._impl_wg import write_people  # noqa
