"""WG6 — the people: authored characters first, then generated ones, their homes, posts, ties and
what they know (P10). Rules WG-26..29, SOC-01, WG-34, DEMO-02, CONSERVE-04, L11. docs/as/06_WORLD.md
§1.3. Code decides who exists (rng streams 'worldgen:people' and f"names:{settlement_id}"); the
model only writes the words of some dossiers (WORLDGEN_ACTOR). Events: origin 'worldgen', turn_index
0, at = ``at``. T = tables.DETAIL_TIERS[detail]; values = params.flat_values(params); dsf =
params.days_since_fall; round = params.rnd.

The HOME settlement = history.home_settlement(plan, region.start_zone_id).

WG-26 Pack actors. The canon actor records (not PCs), by ref — never one from a 'cheat_' pack
  (CHEAT-10: a life as a cheat_ pack's character has that pack in its canon, and its other people
  stay in it until /spawn; D-102). Skipped, and listed in the worldgen
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
  brief = plain English about the person, their settlement, group and history — (D-131) one line
  each: name, age, sex, settlement, group and work; 'It is day N since the Fall, Y years on.'; what
  their cohort remembers (post_fall_born 'Born after the Fall: they have never known any other
  world.', fall_child 'A child when the Fall came: they remember a little of the world before.',
  pre_fall_adult 'Grown when the Fall came: they remember the world before, and losing it.'); 'A
  sketch of them to build on: keep its spirit, make it specific and their own.' then the skeleton's
  voice capsule, motive, past wound, inner conflict, aspiration, fears and signature behaviour as
  '- <what>: <text>' lines; 'What happened here, as people tell it:' then the history belief texts
  (at most 8); 'What people around them say, and they believe too (...)' then every core-lore
  belief held by 'common', their cohort or their group's faction (content_ref) — the Writer wrote
  people from a name, an age and a job, blind to the world they live in — and last 'Write their
  dossier: how they look, move, speak and decide.'; fields={'skeleton':
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
    voices_taken: tuple[str, ...] = ()   # D-199: the first lines of the voices already given out where they live


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
    ("proud", "will not ask for help", "being pitied", "does it alone", "hurts in silence",
     "carried a broken ankle home for a mile rather than be carried"),
    ("anxious", "plans for every way it can go wrong", "plans changing", "freezes for a heartbeat", "sleeps badly",
     "kept a packed bag by the door every night for a year"),
    ("cheerful", "jokes to keep spirits up", "a long face", "keeps people going", "is not taken seriously",
     "kept a whole bunkhouse laughing through a night under siege"),
    ("stubborn", "will not be moved once decided", "being overruled", "holds the line", "loses arguments badly",
     "refused to abandon the greenhouse when the fence fell"),
    ("tender", "notices who is hurting", "someone crying", "stays with them", "falls behind on work",
     "sat up three nights with a dying stranger"),
    ("cold", "keeps feelings out of it", "a sob story", "decides fast", "is not liked",
     "voted to turn away a family at the gate, and slept fine"),
    ("greedy", "always knows what things are worth", "a fair split", "trades hard", "is not trusted with stores",
     "came back from a run with more than they reported"),
    ("brave", "goes first", "someone in danger", "takes the risk", "has scars to show for it",
     "pulled a man off the wall with three of them on the ladder"),
    ("bitter", "remembers every slight", "being blamed", "keeps score", "drives people off",
     "still will not speak to the woman who took their bunk"),
    ("devout", "prays before eating and before a run", "blasphemy", "trusts it will be all right", "frustrates the practical",
     "kept a service going every Sunday through the hungry months"),
)
_KID_TRAITS = (
    ("curious", "pokes into everything", "something new", "wanders off", "gets into trouble",
     "found the way into the old shop through the vent"),
    ("shy", "hides behind grown-ups", "strangers", "goes silent", "gets overlooked",
     "did not say a word for a week after they came"),
    ("bold", "dares the other children", "being called scared", "goes too far", "gets hurt",
     "climbed the water tower on a dare"),
    ("clingy", "never lets go of a hand", "being left", "follows everywhere", "gets underfoot",
     "slept at the foot of the watch tower so as not to be left"),
    ("helpful", "fetches and carries without being asked", "a grown-up struggling", "tries to help", "gets in the way",
     "carried water all morning until their hands blistered"),
    ("watchful", "notices everything", "grown-ups whispering", "listens in", "knows too much",
     "was the first to see the dead at the fence and said nothing until asked"),
)

_VOICES = (
    ("short sentences", "talks about the work"),
    ("asks questions instead of answering", "uses people's names"),
    ("dry jokes", "understates everything"),
    ("long explanations", "repeats the important part"),
    ("swears when nervous", "laughs at the wrong moments"),
    ("quotes scripture, half-remembered", "calls everyone 'friend'"),
    ("talks to fill a silence", "tells stories about before"),
    ("barely talks", "answers with a nod or a shrug"),
    ("counts things out loud", "speaks in lists"),
    ("polite to a fault", "says sorry too much"),
    ("talks fast and drops the ends of words", "old city slang"),
    ("speaks slowly", "weighs every word"),
    ("bitter jokes about the dead", "never says 'infected', only 'them'"),
    ("gives orders like favours", "says 'we' when they mean 'you'"),
    ("hums while working", "trails off mid-thought"),
    ("corrects people", "uses old words nobody uses now"),
    ("blunt as a hammer", "ends arguments with 'that's that'"),
    ("warm and teasing", "calls people 'love' or 'pet'"),
    ("whispers out of habit", "goes quiet when anyone shouts"),
    ("talks to the dead out loud", "mixes up names when tired"),
    ("prices everything in trade", "haggles even with friends"),
    ("talks like a soldier, by the numbers", "clipped radio habits"),
    ("asks how everyone is feeling", "counsellor's habits from before"),
    ("superstitious", "touches wood and counts to three"),
    ("angry at God and says so", "loud"),
    ("soft-spoken and exact", "never raises their voice, even now"),
    ("cheerful in a way that unsettles people", "whistles"),
    ("picks fights with words when drinking", "maudlin when sober"),
    ("a mechanic's talk: everything is a machine", "fixes things while talking"),
    ("formal, from somewhere official once", "talks in procedures"),
    ("gentle with animals, short with people", "talks to dogs more than to anyone"),
    ("mocks everything", "never gives a straight answer"),
    ("stammers until there is a crisis", "apologises before speaking"),
    ("lives by survival rules", "quotes their own rules by number"),
    ("flirts out of habit", "deflects with charm"),
    ("talks about food constantly", "measures time in meals"),
    ("cold and transactional", "asks what's in it for them"),
    ("hums bits of songs", "answers with half a tune"),
    ("drops into Spanish when scared", "translates themself"),
    ("grim and literal", "states the odds"),
)
_KID_VOICES = (
    ("asks 'why' about everything", "repeats what grown-ups said"),
    ("talks to a toy", "uses grown-up words wrong"),
    ("whispers", "hides behind someone to talk"),
    ("brags", "tells made-up stories"),
    ("very serious for their age", "says grown-up words carefully"),
    ("chatters", "forgets to be quiet"),
    ("collects things", "shows everyone their treasures"),
    ("plays at being a guard", "salutes"),
    ("afraid of the dark and says so", "holds on to sleeves"),
    ("says what everyone is thinking", "blunt the way small children are"),
)
_TEEN_VOICES = (
    ("sarcastic", "rolls their eyes into every word"),
    ("tries to sound older", "swears to sound hard"),
    ("mumbles", "says 'whatever'"),
    ("argues every rule", "knows everyone's business"),
    ("talks big about runs", "goes quiet around the dead"),
    ("polite to adults, savage to other kids", "keeps secrets badly"),
    ("acts like nothing scares them", "dares people"),
    ("quiet, draws on everything", "talks to one person only"),
    ("never knew anything else", "thinks grown-ups are soft"),
    ("desperate to be useful", "volunteers for everything"),
)

# D-143: each line set belongs to the voice at the same index — a person's lines sound like the person.
_EXEMPLARS = (
    ("Work's done. Could be worse.", "Get inside. Now.", "I can't. I just can't do it again."),
    ("You eaten today? Sit down a minute.", "Who's missing? Who's not here?", "Don't make me choose. Please."),
    ("Nice day for the end of the world.", "Move. Talk later.", "That's it. I'm done carrying this."),
    ("Here's how it works, and here's why.", "Stop. Think. Which way did it come?", "I told you. I told all of you."),
    ("Ha. Sorry. Shit. It's not funny. It's a bit funny.", "Shit, shit, shit. Move!", "Why am I laughing? He's dead. Why am I laughing?"),
    ("If the Lord wanted us dead, friend, He's taking His time.", "Pray later. Run now.", "There's nobody listening. There never was."),
    ("Did I ever tell you about the drive-in? Before? You'd have loved it.", "Okay, okay, I'm moving, I'm moving.",
     "Say something. Anybody. I can't stand the quiet."),
    ("Mm-hm. Fine.", "Back. Back, I said.", "...Leave me be."),
    ("Three jugs, two cans, one knife. That's the lot.", "One: shut the door. Two: shut up.", "I counted them. I counted every one of them."),
    ("Sorry, sorry, is anyone sitting here?", "Please, please just stay behind me.", "I'm sorry. I'm so sorry. I couldn't hold on."),
    ("Y'alright? C'mon then.", "Leg it! Now, now, now!", "No. No, no, no. Not him."),
    ("Take your time. Nothing but time now.", "Easy. Slow. Nobody shoots.", "I have nothing left to weigh it against."),
    ("Fine weather for burying, my mother used to say.", "Them. Behind the cars. Don't look.", "I keep seeing her face. Every time I close my eyes."),
    ("We'll want that wall patched by dark, won't we.", "We are leaving. Now.", "We? There's no we. There's just me."),
    ("Hm-hm-hm... sorry, what was that?", "Quiet, quiet...", "I don't... I don't remember what I came in for."),
    ("It's 'fewer', not 'less'. Old habits.", "Indoors, the lot of you. Hasten.", "There's no word for this. I looked. There isn't one."),
    ("That's that, then.", "No. That's final.", "You want to fight me? Fine. Outside."),
    ("Hello, pet. You look half starved.", "Pet, behind me. Don't argue.", "Not the little one. Take me instead."),
    ("There's tea. If you want it.", "Shh. Down. Stay down.", "Don't shout. Please don't shout at me."),
    ("Morning, Dad. Same as ever up here.", "Run, Sam. Ben. Whoever you are, run!", "You'd know what to do. You always knew. Tell me."),
    ("That's worth two cans. Three, if it's clean.", "Leave the bag! It's not worth your neck!", "Name your price. Anything. Just bring him back."),
    ("Copy. Moving to the wall.", "Contact left! Down, down!", "Negative. I'm not leaving him. Negative."),
    ("How are you sitting with all this? Honestly.", "Breathe with me. In. Out. Now move.", "I can't fix this one. I can't fix anyone."),
    ("Touch the frame on your way out. For luck.", "Three, two, one, go, while it looks away!", "We broke the count. I told you we broke the count."),
    ("Look at that. Another lovely day He forgot about.", "MOVE! Are you deaf?", "Go on, then. Take me too. TAKE ME!"),
    ("Would you pass that, please. Thank you.", "Behind me. Quietly. Thank you.", "Look at me. Stay with me. Just look at me."),
    ("Morning! Nobody died in the night. Good start.", "Ooh, that's a lot of them. Let's not be here.", "Still smiling. See? Still smiling. Still..."),
    ("Who drank the last of it? Who?", "Get off me, I can walk! I can... move!", "Everyone I like ends up in the ground. So don't."),
    ("Hand me that. No, the other one. There she goes.", "It's seized! Push, push!", "Some things you can't put back together. I tried."),
    ("Rations go by the list. No exceptions.", "Everyone to the assembly point. Now.", "There's no procedure for this. There's no procedure."),
    ("Good girl. Who's hungry? Not you. Him.", "Easy, easy. Everybody still. She's scared.", "Not the dog too. Please. Not the dog too."),
    ("Oh, a plan. How exciting. Do we get hats?", "Fine, fine, running. Look at me run.", "Ha. Funny. No. No, it isn't."),
    ("I... sorry... I just thought... the roof leaks.", "Left. Go left. Now.", "I c-can't. Don't make me look."),
    ("Rule four: never sleep where you ate.", "Rule one! Quiet! Rule one!", "There's no rule for this. I made them all and there's none."),
    ("Well, aren't you a sight. Even filthy.", "Darling, I'd love to chat, but run.", "Don't be sweet to me now. I can't take sweet."),
    ("Two meals till the run. One, if it's beans.", "Drop it! Drop the food and run!", "I'd give every meal I've got left. Every one."),
    ("And what do I get?", "Your problem. Move or don't.", "...Fine. I'll stay. Don't make it a thing."),
    ("La, la-la... sorry. Stuck in my head.", "Hup, hup, hup, go!", "I can't remember how it ends. The song. I can't."),
    ("Bueno. Good. It's good.", "¡Vámonos! Go, go!", "Dios mío. No. No, no, no."),
    ("Twelve of us. Food for nine. Do the sums.", "Thirty metres. We won't make it walking.", "The odds were never good. I knew. I still hoped."),
)
_KID_EXEMPLARS = (
    ("Why is the sky that colour?", "Mum said we have to be quiet.", "I want to go home. I want to go home."),
    ("Mr Bear says he's starving to death.", "Shh. Shh. They'll hear.", "Wake up. Wake up. Why won't you wake up?"),
    ("Can I sit by you? I'll be quiet.", "Is it them? Is it them?", "Don't leave me here. Please don't."),
    ("I can count to a hundred. Want to hear?", "I'm hiding. I'm the best at hiding.", "I didn't mean to. I didn't!"),
    ("We have to ration it. That means a little bit every day.", "Everybody stay calm. That's what you say.", "Where did everybody go?"),
    ("And the dog went under the fence and I said no and he did it anyway and", "Sorry! Sorry. I'm quiet now. I'm quiet.",
     "I don't like it here anymore."),
    ("Look, a button. A gold one. It's mine now.", "My bag! I need my bag!", "Somebody took my things. All my things."),
    ("Halt! Who goes there? ...Oh. It's you.", "Everybody in! Guard says!", "I was supposed to be watching. I was watching."),
    ("Can you leave the light? Just a bit?", "Hold my hand. Hold it!", "It's so dark. Where are you? Where are you?"),
    ("Why does that man smell?", "That lady's bleeding a lot.", "Is she dead? She's dead, isn't she."),
)
_TEEN_EXEMPLARS = (
    ("Oh good. Beans again. My favourite.", "Run! Don't wait for me!", "You don't get to tell me it's okay."),
    ("I could do that run. I'm faster than you.", "Shut up and move.", "Don't touch me. Don't you dare."),
    ("Whatever. It's fine.", "Go. Just go.", "Leave me alone. Please, just leave me alone."),
    ("Heard the watch talking about you.", "That rule's stupid and you know it. Move!", "I just want one normal day. One."),
    ("Is that a real gun? Can I hold it?", "Get down, get down!", "I hate this. I hate all of you."),
    ("Nobody asked you.", "Not a word. Not one word.", "I'm not a kid. Stop treating me like one."),
    ("Bet I could get over that fence in five seconds.", "Come on! What are you, scared?", "I'm not crying. Shut up. I'm not."),
    ("...I drew the wall. You want to see?", "Go. I'll follow. Go.", "I don't want to draw anymore."),
    ("You lot cry about everything.", "Stab it in the eye. It's easy. Watch.", "Is this all there is? Is this it?"),
    ("I'll take watch. I'll take two watches.", "Let me go first! I'm small, I'll fit!", "I wasn't fast enough. I should've been faster."),
)
# Elders draw from the adult voices and these (D-143): an old person is not only their age.
_ELDER_VOICES = (
    ("uses old words nobody uses now", "corrects people"),
    ("fusses over everyone", "calls people 'love'"),
    ("dry jokes", "talks about the old world as if it were still there"),
    ("tells stories about before", "talks to fill a silence"),
    ("blunt as a hammer", "worries out loud"),
    ("speaks slowly", "reads the weather in their bones"),
    ("keeps the names of the dead", "writes everything in a notebook"),
    ("gruff, old soldier", "thinks the young are soft"),
    ("gentle and forgetful", "asks after people long gone"),
    ("cutting and wise", "answers a question with a question"),
)
_ELDER_EXEMPLARS = (
    ("In my day we had a word for this. Several.", "Get the young ones in first.", "I've buried enough. I'll not bury you."),
    ("Sit, sit. Let me fuss.", "Don't run, love. It only makes them faster.", "Let me go. I'm slowing you down."),
    ("Kettle's on. Would be, if there were a kettle.", "Hush. Listen to the dogs.", "This was a school once. Children laughing."),
    ("Before all this I sold shoes. Imagine.", "Steady. Steady hands.", "Leave me the pistol and go."),
    ("You're too thin. Eat.", "Bar the door, quick now.", "It should have been me first. Not him."),
    ("Weather's turning. Knees never lie.", "Not that way, that's the river.", "I'm tired, love. So very tired."),
    ("I write them all down. Somebody should.", "In! Count heads as you go!", "Another page. I'm running out of pages."),
    ("At your age we carried twice that.", "Backs to the wall! Form up!", "I outlived my whole unit. And now you."),
    ("Has anyone seen my sister? She was just here.", "Is it the noise again? Should we hide?", "Oh. That's right. She's gone. I keep forgetting."),
    ("And who told you that? And did you believe them?", "Why are you still standing there?", "What's left to save? Tell me. What's left?"),
)
_PROFANITY = ("none", "rare", "frequent", "constant")


_NEVER_SAY = (
    "Let them starve.", "Not my problem.", "Whatever you say, boss.", "Leave the kid behind.", "I'm done with all of you.",
    "I don't care who you lost.", "Take my share, I don't need it.", "God is good.", "We should go back for them.",
    "I was wrong. I'm sorry.", "Let's put it to a vote.", "Rules are rules.", "I'd rather die than run.", "Trust me.",
    "It'll all go back to normal.", "Shoot him.", "Nobody's coming to save us.", "Lock them out.", "Feed him to them.",
    "I miss the old world.", "I love you.", "Keep it. It's yours.", "We don't need the council.",
    "Give them the medicine instead.", "Wait for me.", "That's not my job.", "I'm scared.", "You're right.",
    "Let's just talk about it.", "Thank you.",
)
_KID_NEVER_SAY = (
    "I'm not hungry.", "I'll go outside on my own.", "Grown-ups are always right.", "I don't need a hug.",
    "I'm too big to be scared.", "I like the dark.", "I'll stay here by myself.", "That doesn't hurt.",
)

_MOTIVES = (
    ("keep {group} fed and safe", "does the work assigned, and some more"),
    ("get their sister back from wherever the convoy took her", "asks every trader who passes"),
    ("earn a seat at the council table", "volunteers for whatever gets noticed"),
    ("never be hungry again", "puts a little of every ration aside"),
    ("find out what happened to their old street", "plans a run nobody has approved"),
    ("keep their hands clean", "takes the jobs nobody has to die for"),
    ("be useful enough that nobody ever turns them out", "learns every trade they can"),
    ("make up for something they did in the first winter", "takes the worst shifts without a word"),
    ("get the children through to spring", "trades their own share for milk and medicine"),
    ("leave {settlement} for somewhere quieter", "trades for goods in secret, against the day"),
    ("keep the {occupation} work going", "fixes what breaks before anyone asks"),
    ("see every one of the dead put down properly", "goes out with a spade when the watch allows"),
    ("pay back the people who took them in", "gives more than they are asked for"),
    ("keep the peace between the families", "listens to everyone and repeats nothing"),
    ("be left alone to do their work", "keeps their head down and their hands busy"),
    ("get back at the crew that burned their old camp", "asks after them on every run"),
    ("hold on to the last of their faith", "keeps the old prayers every night"),
    ("be the one people come to", "always has a little of what is needed"),
)
_CONTRADICTIONS = (
    ("{group} comes first", "family comes first", "the stores are full", "the stores are low"),
    ("everyone deserves a chance", "strangers get people killed", "a child is at the gate", "a grown man is"),
    ("the rules keep us alive", "the rules are for people who never went out there", "the leader is watching",
     "nobody is"),
    ("the dead were people once", "the dead are just meat now", "they knew the dead one", "they did not"),
    ("hope is how we last", "hope is how we die", "the morning is quiet", "the dead are at the fence"),
)
_WONT = (("steal from the common store", "steal"), ("leave a wounded friend behind", "leave_wounded"),
         ("hurt a child", "harm_dependent"), ("break their word", "break_promise"), ("turn on their own group", "betray_group"))
_KID_MOTIVES = (
    ("be allowed up on the wall one day", "follows the watch around"),
    ("keep the dog they found", "shares their food with it in secret"),
    ("find their mum", "asks every newcomer if they have seen her"),
    ("be as brave as the grown-ups", "pretends not to cry"),
    ("get the last of the sweets", "trades whatever they find"),
    ("not be a bother", "does as they are told, quickly"),
)
_CONFLICTS = (
    "wants to leave and cannot abandon the others", "trusts the leader and hates what the leader asks",
    "wants to be kind and has learned that kindness gets people killed", "misses the old world and is ashamed of how little",
    "wants a family and is terrified of losing one again", "believes in the rules and breaks them for the people they love",
    "wants revenge on the ones who left them and needs their help now", "is proud of surviving and sick of what it cost",
    "prays every night and no longer believes anyone hears", "wants to be needed and wants to be left alone",
    "loves someone in the settlement who should not know it", "would trade anything for a quiet life and is good at fighting",
)
_KID_CONFLICTS = (
    "wants to be brave and is scared all the time", "wants to play and knows they must be quiet",
    "misses someone and is told not to talk about them", "wants to grow up fast and wants someone to look after them",
)
_WOUNDS = {
    "pre_fall_adult": (
        "lost family in the first week of the Fall", "left a friend behind at the stadium evacuation",
        "shot their own brother when he turned", "was a nurse when the hospitals fell, and still smells it",
        "hid in a freezer for two days while the street was eaten", "sold out a neighbour for a bag of rice in the first winter",
        "walked out of the city alone, past people begging for help", "was in the first quarantine camp when the fence came down",
        "watched their child turn and could not do it themselves",
    ),
    "fall_child": (
        "was eight when the Fall came and remembers only the screaming", "grew up in the camps, moved from fence to fence",
        "lost their parents on the road and was raised by strangers", "was carried out of the city in a laundry basket",
        "was left at a gate with a note pinned to their coat",
    ),
    "post_fall_born": (
        "has never seen a city lit at night", "lost their mother to a fever last winter", "was born in a cellar during a raid",
        "watched a neighbour turn when they were very small", "has never known a full stomach for a whole week",
    ),
}
_ASPIRATIONS = ("a quiet year", "a roof that does not leak", "to see the sea again", "to grow something that lives",
                "to be trusted with the stores", "a bed of their own", "to hear music again", "to be left alone",
                "a wedding, a real one", "to find out if anyone is left at home", "to teach someone what they know",
                "to sleep through one whole night")
_KID_ASPIRATIONS = ("a dog of their own", "to see a real shop", "to learn to shoot", "to sleep in a proper bed",
                    "to be on the wall", "to have a birthday cake")
_FEARS = ("the pump failing", "a fever in the camp", "the night watch sleeping", "being turned out", "fire",
          "the dead getting in", "losing their hands", "the dark", "deep water", "being alone when it happens",
          "turning and not knowing it", "the council's vote")
_KID_FEARS = ("the dark", "the dead at the fence", "being left behind", "loud noises", "the cellar", "being told off")
_SIGNATURES = ("counts the water jugs every evening", "sleeps in boots", "keeps a list of the dead in a notebook",
               "carves little animals from scrap wood", "talks to the chickens", "never sits with their back to a door",
               "keeps a photo nobody else is allowed to see", "sharpens every blade they pass",
               "writes the date on the wall each morning", "sings the same song at every burial",
               "hoards string and wire", "walks the fence before bed")
_KID_SIGNATURES = ("carries a toy everywhere", "collects buttons", "draws on every wall", "follows the dogs",
                   "hums to themselves", "asks for a story every night")
_GESTURES = ("rubs the back of the neck", "taps two fingers on anything near", "cracks the knuckles",
             "pulls at an earlobe", "crosses the arms tight", "rubs a thumb over an old scar", "chews a thumbnail",
             "pats every pocket", "sets the jaw", "looks at the floor")
_MOVES = ("moves quickly and keeps to the walls", "goes very still and listens", "talks faster and louder",
          "goes pale and slow", "reaches for the nearest weapon", "looks for the children first",
          "backs toward a door", "hums under the breath")
_SILENCES = (
    (["the dead are mentioned", "leaders argue"], "arms folded, looking at the floor", "comfortable at work, uncomfortable in meetings"),
    (["someone cries", "the old world comes up"], "busy hands, eyes down", "comfortable with children, uncomfortable with officials"),
    (["they are praised", "anyone asks about family"], "a fixed smile", "comfortable outdoors, uncomfortable in crowds"),
    (["a decision has to be made", "a gun is drawn"], "very still, watching", "comfortable on watch, uncomfortable at meals"),
    (["they are wrong", "a child is hurt"], "turns away", "comfortable alone, uncomfortable in a room full of people"),
    (["money or trade comes up", "someone shouts"], "picks at their sleeve", "comfortable working, uncomfortable resting"),
)
_STACKS = (
    ["family", "own safety", "{group}", "strangers"], ["own safety", "family", "{group}", "strangers"],
    ["{group}", "family", "own safety", "strangers"], ["family", "{group}", "strangers", "own safety"],
    ["the children", "family", "{group}", "own safety"], ["their faith", "family", "{group}", "own safety"],
)
_TOWARD_STRANGERS = ("wary", "neutral", "warm", "hostile", "wary", "neutral")
_ENCOUNTER = ("calls for the watch and keeps distance", "asks their name and business", "offers water and watches them drink it",
              "puts themselves between the stranger and the children", "says nothing and fetches the leader",
              "keeps one hand on a weapon and talks")
_SECRETS = ("none worth telling", "none worth telling", "none worth telling",
            "took food from the common store in the hungry month", "rode with a raider crew for a winter",
            "left someone behind who might have lived", "was bitten once, and it never took", "lied about their trade to get in")
_DIALECTS = ("", "", "", "a northern accent that thickens when angry", "drops the 'g' on every -ing",
             "old army habits of speech", "a city voice gone rough", "slow country vowels")


def _draw(seed: "PersonSeed", what: str, pool, n: int = 1):
    """D-127: an independent, deterministic draw per field (sha256 of the person's name, variant and the
    field), so no two fields move together and no two people share a whole inner life."""
    import hashlib
    h = int.from_bytes(hashlib.sha256(f"{seed.name}|{seed.variant}|{what}".encode()).digest()[:8], "big")
    if n == 1:
        return pool[h % len(pool)]
    out, i = [], 0
    while len(out) < n:
        x = pool[(h + i * 7919) % len(pool)]
        if x not in out:
            out.append(x)
        i += 1
    return out


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
    Plain but specific enough to pass CNT-10. D-127 (GEN-01): every field is its own draw — sha256 of the
    person's name, variant and the field — from pools for their age (a child under 12, a teen 12-17, an
    adult, an elder 60 and over), cohort (what they can remember losing: pre_fall_adult, fall_child,
    post_fall_born) and work, so no two people in a settlement share a whole inner life and a child never
    talks like a pump mechanic. (D-143) A voice and its lines are one draw — the lines sound like the voice
    (an elder draws from the adult voices and the elders' own; nobody born after the Fall draws one that
    remembers the world before it) — and the profanity follows it: (D-199) a voice whose first line is in
    seed.voices_taken is drawn only when every voice open to them is taken — nobody in one place sounds like
    someone else there while there are voices left; someone who
    swears when nervous swears at least 'frequent'ly, someone who quotes scripture or apologises for
    everything never does. The temper still comes from ``variant`` (H1). WORLDGEN_ACTOR may replace every
    unlocked field of it."""
    v = seed.variant
    first = seed.name.split()[0]
    adult = seed.age >= 16
    kid, teen, elder = seed.age < 12, 12 <= seed.age < 18, seed.age >= 60
    traits = _draw(seed, "traits", _KID_TRAITS if kid else _TRAITS, 2)
    t1, t2 = traits
    voices, lines = ((_KID_VOICES, _KID_EXEMPLARS) if kid else (_TEEN_VOICES, _TEEN_EXEMPLARS) if teen else
                     (_VOICES + _ELDER_VOICES, _EXEMPLARS + _ELDER_EXEMPLARS) if elder else (_VOICES, _EXEMPLARS))
    pairs = tuple(zip(voices, lines))
    if seed.cohort == "post_fall_born":       # D-143: nobody born after the Fall tells stories about before it
        pairs = tuple(p for p in pairs if not any(k in " ".join(p[0] + p[1]) for k in ("before", "old world", "old words",
                                                                                      "old city", "used to say")))
    pairs = tuple(p for p in pairs if p[1][0] not in seed.voices_taken) or pairs    # D-199: not a voice already here
    tend, ex = _draw(seed, "voice", pairs)                             # D-143: the lines go with the voice
    swear = _draw(seed, "profanity", ("none", "rare", "rare", "frequent", "constant"))
    if any("swear" in x for x in tend):
        swear = max(swear, "frequent", key=_PROFANITY.index)
    elif any(k in x for x in tend for k in ("scripture", "polite to a fault", "says sorry")):
        swear = "none"
    fmt = {"group": seed.group_name, "settlement": seed.settlement_name, "occupation": seed.occupation}
    motive, method = _draw(seed, "motive", _KID_MOTIVES if kid else _MOTIVES)
    wounds = _WOUNDS.get(seed.cohort) or _WOUNDS["pre_fall_adult"]
    silence = _draw(seed, "silence", _SILENCES)
    wont = _draw(seed, "wont", _WONT)
    stack = [x.format(**fmt) for x in _draw(seed, "stack", _STACKS)]
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
                       "movement_under_stress": _draw(seed, "moves", _MOVES),
                       "habit_gesture": _draw(seed, "gesture", _GESTURES),
                       "relation_to_appearance": _draw(seed, "vanity", ("does not think about it", "keeps clean whatever it costs",
                                                                          "hides a scar", "wears something from before every day")),
                       "looks": looks},
        "capability": {"special": dict(seed.special), "skills": skills, "literacy": 2 if adult else 1,
                       "tech_literacy": 1},
        "motive": {"motive": motive.format(**fmt), "method": method,
                   "moral_line": {"will": [_draw(seed, "will", ("work a double shift", "share their last meal",
                                                                 "stand a watch for someone sick", "lie to protect a friend"))],
                                  "wont": [wont[0]], "wont_tags": [wont[1]]},
                   "inner_conflict": _draw(seed, "conflict", _KID_CONFLICTS if kid else _CONFLICTS),
                   "past_wound": _draw(seed, "wound", wounds),
                   "signature_behaviour": _draw(seed, "signature", _KID_SIGNATURES if kid else _SIGNATURES),
                   "risk_threshold": 3 + v % 4,
                   "risk_text": _draw(seed, "risk", ("takes risks only for people they know", "takes risks for anyone",
                                                     "takes no risks they do not have to", "takes risks to be noticed")),
                   "resource_constraints": "owns what fits in one bag"},
        "persona": {"public": {"shown_traits": [t1[0]], "claimed_history": f"came to {seed.settlement_name} early",
                               "presented_affiliation": seed.group_name},
                    "private": {"true_goals": [motive.format(**fmt)],
                                "concealed_history": "none worth telling" if kid or teen else _draw(seed, "secret", _SECRETS),
                                "real_affiliation": "their own people"}},
        "traits": [dict(zip(("tag", "manifests", "triggers", "causes", "costs", "example"), t1)),
                   dict(zip(("tag", "manifests", "triggers", "causes", "costs", "example"), t2))],
        "contradictions": [dict(zip(("belief_a", "belief_b", "a_wins_when", "b_wins_when"),
                                    (x.format(**fmt) for x in _draw(seed, "contradiction", _CONTRADICTIONS))))],
        "decision_stack": {"layers": stack, "inversion_conditions": ["a raid on the settlement"],
                           "past_example": "stayed on the wall during a raid instead of running home"},
        "silence": {"goes_quiet_when": list(silence[0]), "body_when_silent": silence[1],
                    "comfortable_vs_uncomfortable": silence[2]},
        "knowledge": {"knows": [f"the ways in and out of {seed.settlement_name}"]},
        "voice": {"capsule": f"{first} {tend[0]}; {tend[1]}.",
                  "speech_tendencies": list(tend),
                  "exemplars": {"low_stakes": ex[0], "under_pressure": ex[1], "at_the_limit": ex[2]},
                  "would_never_say": _draw(seed, "never", _KID_NEVER_SAY if kid else _NEVER_SAY, 3),
                  "profanity": "none" if kid else swear,
                  "dialect_notes": "" if kid else _draw(seed, "dialect", _DIALECTS)},
        "social": {"household_role": "", "relations": [], "dependents": [], "guardians": [], "memberships": []},
        "life": {"aspiration": _draw(seed, "aspiration", _KID_ASPIRATIONS if kid else _ASPIRATIONS),
                 "current_project": f"keeping up with the work at {seed.settlement_name}",
                 "fears": [_draw(seed, "fear", _KID_FEARS if kid else _FEARS)]},
        "disposition": {"archetype_prior": "civilized", "toward_strangers": _draw(seed, "strangers", _TOWARD_STRANGERS),
                        "encounter_default": _draw(seed, "encounter", _ENCOUNTER)},
        "temper": {"fuse": _FUSES[(v // 5) % len(_FUSES)], "outlet": _OUTLETS[(v // 11) % len(_OUTLETS)],
                   "grudge": (v // 7) % 4, "pet_peeves": [_PEEVES[(v // 3) % len(_PEEVES)]],
                   "cools_down_by": _SETTLERS[(v // 13) % len(_SETTLERS)]},
        "tags": ["generated"],
    }


from ._impl_wg import write_people  # noqa
