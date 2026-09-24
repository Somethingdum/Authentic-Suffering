"""AS worldgen tables (IMPLEMENTED DATA, P10). docs/as/06_WORLD.md §1.
Unlike tables.py (Codex Master Guide §61, canon), these are Authentic Suffering's own tables: names,
zone kinds, what stands in each kind of zone, the words the world is described with. Tuning them
changes worlds, not rules; record a change in docs/as/CHANGELOG_AS.md.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------------------- stages
STAGES: tuple[str, ...] = ("WG0", "WG1", "WG2", "WG3", "WG4", "WG5", "WG6", "WG7", "WG8", "WG9", "COMMIT")
STAGE_LABELS: dict[str, str] = {
    "WG0": "Rolling the world…", "WG1": "Carving the land…", "WG2": "Writing what happened…",
    "WG3": "Drawing the lines of power…", "WG4": "Building settlements…", "WG5": "Filling homes…",
    "WG6": "Waking the people…", "WG7": "Setting the laws…", "WG8": "Placing the trouble…",
    "WG9": "Checking it all holds together…", "COMMIT": "Ready.",
}
# share of the progress bar each stage covers (sums to 100); pct at a stage's start = sum of earlier shares
STAGE_SHARE: dict[str, int] = {
    "WG0": 2, "WG1": 5, "WG2": 22, "WG3": 3, "WG4": 5, "WG5": 3, "WG6": 40, "WG7": 2, "WG8": 13, "WG9": 5,
    "COMMIT": 0,
}

# ---------------------------------------------------------------------------------------- labels
# the words players read for settings values (docs/as/11_SETTINGS.md); worldgen messages and world.json use them
DIFFICULTY_LABELS: dict[str, str] = {
    "bitch_mode": "Bitch Mode", "easy": "Easy", "normal": "Normal", "realism": "Realism",
    "actually_hell": "Actually Hell", "fuck_you": "Fuck You",
}
ERA_LABELS: dict[str, str] = {"early": "Early", "established": "Established", "mature": "Mature"}

# --------------------------------------------------------------------------------------- climate
# 06 §1.2: heat band x moisture band -> climate_descriptor (<= 35 chars). Bands: 1-3, 4-7, 8-10.
CLIMATE_DESCRIPTORS: dict[tuple[str, str], str] = {
    ("cold", "dry"): "frozen, dry, wind-scoured", ("cold", "moderate"): "cold grey damp",
    ("cold", "wet"): "sleet and slush, always wet",
    ("mild", "dry"): "dry temperate scrub", ("mild", "moderate"): "temperate, rain some days",
    ("mild", "wet"): "mild and waterlogged",
    ("hot", "dry"): "arid heat, dust and glare", ("hot", "moderate"): "hot, humid, overgrown ruin",
    ("hot", "wet"): "subtropical ruin, heavy rain",
}

# ---------------------------------------------------------------------------------- key resource
# Part VIII gives the TYPE; the descriptor is ours. key_resource = f"{type} — {descriptor}" (<= 50 chars).
KEY_RESOURCE_DESCRIPTORS: dict[str, tuple[str, ...]] = {
    "supply node": ("a sealed grocery warehouse", "a flooded distribution depot", "a church food bank"),
    "infrastructure": ("a working water tower", "a solar array still charging", "a diesel pump station"),
    "biological": ("a clean well nobody has fouled", "a seed vault in a school basement", "a goat herd"),
    "territory": ("the only bridge still standing", "high ground above the floodline", "a walled rail yard"),
    "information source": ("a radio that still talks", "a survey office full of maps", "a ledger of debts"),
}

# ---------------------------------------------------------------------------------------- region
ZONE_KINDS: tuple[str, ...] = ("downtown", "residential", "industrial", "riverside", "rural", "highway", "wilds")
START_ZONE_WEIGHTS: tuple[tuple[str, float], ...] = (
    ("residential", 3.0), ("downtown", 2.0), ("industrial", 1.0), ("riverside", 1.0), ("rural", 1.0),
)
ZONE_WEIGHTS: tuple[tuple[str, float], ...] = (
    ("residential", 3.0), ("downtown", 2.0), ("industrial", 2.0), ("riverside", 1.0), ("rural", 2.0),
    ("highway", 1.0), ("wilds", 1.0),
)
ZONE_NAMES: dict[str, tuple[str, ...]] = {
    "downtown": ("Old Market", "Civic Square", "Main and Fifth", "The Exchange", "Courthouse Row", "Union Blocks",
                 "Bank Street", "The Arcade"),
    "residential": ("Maple Heights", "Cedar Row", "Linden Park", "Orchard Hill", "Willow Court", "Birch Flats",
                    "Sycamore Loop", "Quail Run"),
    "industrial": ("Rail Yards", "Foundry Flats", "Canal Works", "North Depot", "Tannery Lane", "The Stacks",
                   "Gravel Pits", "Mill District"),
    "riverside": ("Low Wharf", "Mill Race", "Ferry Landing", "Reed Bank", "Lock Street", "The Levee",
                  "Heron Point", "Barge Row"),
    "rural": ("Hollow Farm Road", "Sawyer's Fields", "Dry Creek", "Kettle Pond", "Quarry Road", "Long Acres",
              "Crossroads", "Silo Hill"),
    "highway": ("Route 9 Interchange", "Truck Stop Mile", "Overpass Nine", "Exit 14", "The Service Road",
                "The Toll Plaza", "Weigh Station", "Interstate Bend"),
    "wilds": ("Pine Barrens", "Blackwater Woods", "Stony Ridge", "The Marsh", "Deer Hollow", "Burnt Timber",
              "Fox Hollow", "The Cutover"),
}
# building archetype kinds (content BuildingArchetype.kind) that stand in each zone kind; none -> outdoor places
ZONE_BUILDING_KINDS: dict[str, tuple[str, ...]] = {
    "downtown": ("shop", "hall"), "residential": ("house", "apartment"), "industrial": ("utility", "shop"),
    "riverside": ("house", "utility"), "rural": ("house", "utility"), "highway": ("shop",), "wilds": (),
}
OUTDOOR_PLACE_NAMES: tuple[str, ...] = (
    "a clearing", "the old campsite", "a dry creek bed", "a fallen water tower", "a burnt-out barn",
    "a hunting blind", "a ranger's lookout", "a wrecked bus",
)
# infected / hostile density modifiers by zone kind (added to the C-block values, then clamped 0..10)
ZONE_DANGER_MOD: dict[str, dict[str, int]] = {
    "downtown": {"shambler": 2, "horde": 1}, "residential": {}, "industrial": {"hostile": 1},
    "riverside": {"crawler": 1}, "rural": {"shambler": -1, "runner": -1}, "highway": {"horde": 2, "hostile": 1},
    "wilds": {"shambler": -2, "lurker": 1},
}
ROUTE_DISTANCE_M: tuple[int, int] = (400, 2500)
CHORD_CHANCE: float = 0.25
# P10 — a district's dead before zombie_common scales them (world.hordes HRD-02; fidelity E01)
ZONE_INFECTED: dict[str, int] = {
    "downtown": 3000, "residential": 2000, "industrial": 900, "riverside": 700, "rural": 200, "highway": 400,
    "wilds": 80,
}
# P10 — the four ways out of the region (W04): each an exterior zone holding the dead beyond it
EXTERIOR_DIRECTIONS: tuple[str, ...] = ("north", "east", "south", "west")
EXTERIOR_NAMES: dict[str, str] = {
    "north": "The North Road", "east": "The Interstate East", "south": "The South Highway",
    "west": "The West Rail Line",
}
EXTERIOR_DISTANCE_M: tuple[int, int] = (3000, 6000)

# --------------------------------------------------------------------------------------- polity
GROUP_DYNAMICS: tuple[str, ...] = (
    "Tight-knit", "Fortified", "Nervous", "Pious", "Hard-bargaining", "Family-run", "Militant", "Quiet",
)
GROUP_LOCATIONS: tuple[str, ...] = (
    "church-hall commune", "rail-yard crew", "school-roof camp", "market collective", "warehouse clan",
    "farmstead household", "water-tower co-op", "clinic congregation",
)
GROUP_RULES: tuple[str, ...] = (
    "that shares everything", "that trades water for work", "that turns strangers away", "that owes no one",
    "that keeps a strict curfew", "that buries its dead properly", "that tests every newcomer",
    "that pays in ammunition",
)
HOSTILE_DYNAMICS: tuple[str, ...] = ("Raiding", "Desperate", "Predatory", "Roving")
HOSTILE_LOCATIONS: tuple[str, ...] = ("highway band", "overpass crew", "motel gang", "quarry pack")
HOSTILE_RULES: tuple[str, ...] = ("that takes what it finds", "that tolls the roads", "that hunts scavengers",
                                  "that trades in people")
GROUP_NOUNS: tuple[str, ...] = ("Crew", "Family", "Collective", "Band", "Lot", "People")
SETTLEMENT_SUFFIX: tuple[tuple[int, str], ...] = ((3, "Camp"), (6, "Hold"), (10, "Commons"))   # social_order <= key
SETTLEMENT_SITE_KINDS: tuple[str, ...] = ("hall", "utility", "shop", "apartment", "house")   # preferred first

# ------------------------------------------------------------------------------------ settlement
# site_type -> (cycle_h, required roles, output resource or None, first cycle hours after midnight)
WORKPLACE_PLANS: dict[str, tuple[float, tuple[str, ...], str | None, int]] = {
    "water_pump": (12.0, ("pump_operator", "pump_operator"), "water", 6),
    "kitchen": (8.0, ("cook", "cook"), "food", 7),
    "watch": (12.0, ("watcher", "watcher"), None, 6),
    "clinic": (24.0, ("medic",), None, 8),
    "garden": (24.0, ("gardener",), "food", 18),
}
# role -> (occupation words, skill domain, rank) for the people WG6 makes to fill it
ROLE_PEOPLE: dict[str, tuple[str, str, int]] = {
    "pump_operator": ("pump mechanic", "mechanics", 2), "cook": ("cook", "cooking", 2),
    "watcher": ("watch guard", "firearms", 1), "medic": ("medic", "medicine", 2),
    "gardener": ("gardener", "farming", 2), "quartermaster": ("quartermaster", "trade", 2),
}
# occupations for people with no post (skill domain, rank)
FREE_OCCUPATIONS: tuple[tuple[str, str, int], ...] = (
    ("scavenger", "scavenging", 2), ("hunter", "survival", 2), ("builder", "building", 2),
    ("runner", "athletics", 1), ("trader", "trade", 1), ("mechanic", "mechanics", 1),
    ("teacher", "childcare", 1), ("tracker", "tracking", 1),
)

# ---------------------------------------------------------------------------------------- history
HISTORY_KINDS_FILL: tuple[str, ...] = (
    "battle", "schism", "migration", "failed_settlement", "deposed_leader", "discovery", "epidemic", "betrayal",
    "massacre",
)
# code-built skeleton sentence per kind; {a} / {b} = subject names, {zone} = a zone name, {day} = the day
HISTORY_SKELETON: dict[str, str] = {
    "disaster": "Day {day}: the Fall reached {zone}; the roads jammed and the first dead rose.",
    "founding": "Day {day}: {a} took and held {zone}.",
    "battle": "Day {day}: {a} and {b} fought over {zone}; both lost people.",
    "schism": "Day {day}: {a} split over how to share what was left.",
    "migration": "Day {day}: people from {zone} left in a long column and few came back.",
    "failed_settlement": "Day {day}: a camp at {zone} failed and its people scattered.",
    "deposed_leader": "Day {day}: {a} threw out the one who led them.",
    "massacre": "Day {day}: people were killed at {zone} and nobody was made to answer for it.",
    "discovery": "Day {day}: someone from {a} found a cache in {zone}.",
    "epidemic": "Day {day}: sickness went through {zone}; medicine ran out.",
    "betrayal": "Day {day}: {a} was sold out to {b}.",
    "infrastructure_collapse": "Day {day}: the {resource} in {zone} gave out.",
}
SHORTAGE_RESOURCE_WORDS: dict[str, str] = {
    "food": "food stores", "water": "water supply", "ammo": "last ammunition cache", "fuel": "fuel depot",
    "meds": "medicine",
}

# ---------------------------------------------------------------------------------------- opening
# C-block parameter -> the threat WG8 builds (Part IX Rule 2: the highest C value picks it)
THREAT_KINDS: dict[str, str] = {
    "hostile_human": "hostile_humans", "zombie_common": "shamblers", "horde_pressure": "shamblers",
    "runner_pressure": "runners", "lurker_pressure": "lurker_signs", "ambient_danger": "shamblers",
}
