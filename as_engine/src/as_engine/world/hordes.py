"""The region's dead in numbers, and the hordes (P10; fidelity E01 finite infected, E02 hordes as
moving populations, E03 lifecycle accounting, W04 bounded exterior; the owner's Mega Horde). Owner
'world.hordes' (infected_pools, hordes). Rules HRD-01..17. docs/as/06_WORLD.md §5.

Levels of detail (fidelity §5) — the dead exist in these forms and pass between them, never made
or lost:
  LOCAL     infected BODIES (world.infected), simulated step by step where the player is.
  REGIONAL  POOLS: counts per zone and type, active or dormant — a district's dead nobody has met
            yet, spread through its streets and buildings.
  MOVING    HORDES: counted crowds walking hub to hub along the roads.
  EXTERIOR  four zones of kind 'exterior' past the region's edge (W04), each with one huge pool —
            the rest of the country's dead: large, but finite.
A body is taken from a pool or a horde (its count goes down by one); a pool grows only from real
sources — stragglers, a horde that breaks up or passes through, the district's own dead rising
(E03). Nothing refills by itself: a cleared district stays clear until dead that exist walk in.

H = RulesConfig().hordes (HordeRules); DAY = 86_400_000 ms, HOUR = 3_600_000, MIN = 60_000. TYPES =
(world.infected.SHAMBLER, CRAWLER, RUNNER), in that order; a composition is a dict type_id -> count
holding only counts > 0, always read in TYPES order. A REGION zone is a zones row whose kind is not
'exterior'. A zone's HUB is its places row of kind 'street' whose name is the zone's name (worldgen
WG1). d = at // DAY. rng stream 'hordes'. Every function that returns an Event has committed it
(writer 'world.hordes' unless said otherwise; at and turn_index as given).

HRD-01 Pools: infected_pools {zone_id, type_id, active, dormant} (primary key zone_id, type_id).
  pool(store, zone_id) -> dict[type_id, tuple[int, int]]: (active, dormant) for every type, TYPES
  order (no row -> (0, 0)). total(store, zone_id) -> int: all its active and dormant dead.
  change(tx, zone_id, type_id, active_delta, dormant_delta, reason, at, turn_index, cause) -> Event:
  POOL_CHANGE {zone_id, type_id, active_delta, dormant_delta, active, dormant, reason} (UPSERT of
  the row; active / dormant = the new counts). Both deltas 0, or a new count below 0 -> ValueError
  (nobody is taken who is not there).
HRD-02 seed_pools(tx, params, at) -> list[Event]   (worldgen WG1 step 5; origin 'worldgen', turn 0)
  v = world.worldgen.params.flat_values(params). Per zone (by zone_id): a region zone: base =
  atlas.ZONE_INFECTED[kind], scale = 0.4 + v['zombie_common'] / 10; an exterior zone: base =
  H.exterior_pool[difficulty], scale = 0.5 + v['zombie_common'] / 10. n = round(base x scale);
  runner = round(n x H.runner_share[era] x v['runner_pressure'] / 5); crawler = round(n x
  H.crawler_share); shambler = n - runner - crawler (below 0: crawler, then runner, are cut until
  it is 0). Per type with a count c > 0 (TYPES order): dormant = round(c x H.dormant_share[era]);
  change(tx, zone, type, c - dormant, dormant, 'worldgen', at, 0, None). Returns every event.
HRD-03 Hordes: hordes {horde_id (kind 'hrd'), kind 'drift' | 'drawn' | 'mega', composition,
  zone_id (the zone of its place), place_id (the hub, road or site it is in), route (JSON list: the
  places still to walk, in order), target_place, status 'moving' | 'milling' | 'gone', origin (the
  zone it formed in), since, props (JSON)}. count(store, horde_id) -> int: its composition's sum
  (a gone horde's composition is {}). HORDE_STATE {horde_id, changes} updates any of status,
  route, target_place and props when no other horde event carries the change.
  target(store, place_id) -> str: where a horde can go for that place — a room's building site
  (up its parent chain to the place with parent_id NULL), else the place itself.
  path(store, from_place, to_place) -> list[str] | None: the places a horde walks from a hub or a
  site to target(to_place), excluding from_place. From a site: its zone's hub first. Then
  breadth-first over the hubs (an edge per routes row, either direction; a hub's neighbours in
  route_id order), each crossing adding [the route's road — the street place joined by portals to
  both of its hubs — , the far hub]. Then, for a site, the site. Already there -> []; no way ->
  None.
  leg_ms(store, from_place, to_place, speed_m_s) -> int: off a road onto a hub = round(the road
  place's width_m (its length: the route's distance_m) / speed_m_s x 1000) — the walk along it;
  onto a road, and between a hub and a site = 2 x MIN.
HRD-04 form(tx, kind, zone_id, composition, to_place, at, turn_index, cause, *, props=None,
             first_leg_ms=None) -> str
  Takes the composition from zone_id's ACTIVE dead (change(..., -n, 0, 'horde') per type; too few
  -> ValueError before anything is written). route = path(the zone's hub, to_place) (None ->
  ValueError). HORDE_FORMED {horde_id, kind, composition, zone_id, place_id: the hub, route,
  target_place: target(to_place)} inserting the row: status 'moving' (route not empty) or
  'milling' (props.until = at + H.mill_h hours), origin = zone_id, since = at, props = {} merged
  with ``props``. Its first HORDE_STEP (kernel.clock.schedule(tx, due, 'HORDE_STEP', horde_id,
  {'horde_id': horde_id}, the HORDE_FORMED id)) is due at at + first_leg_ms when given, else at +
  leg_ms(hub, route[0], H.speed_m_s) (moving) or props.until (milling). Returns horde_id.
HRD-05 step(tx, rng, row, fired, turn_index) -> list[Event]   (the HORDE_STEP handler)
  h = the horde; missing or 'gone' -> []. at = row.due_at, cause = fired.event_id; area =
  turn.select.active_area(tx, meta.pc_actor_id, turn_index) ([] without a PC).
  status 'moving': nxt = route[0]; HORDE_MOVED {horde_id, from_place, to_place: nxt, zone_id} (zone
    of nxt) updating place_id, zone_id, route = route[1:]. Then, in this order:
      nxt is a hub: stragglers and rally (HRD-06);
      a mega horde at a region hub begins that zone's passage (HRD-14), at the exit zone's hub it
        is gone (HRD-14); any other horde reaching its target_place mills there: status
        'milling', props.until = at + H.mill_h hours — and presses (HRD-08): at a hub, every
        settlement whose site is in that zone (by settlement_id); at a settlement's site, that
        settlement (a crowd passing through presses no one; where it stops, it does);
      nxt in area -> promote(nxt) (HRD-07).
  status 'milling': at >= props.until -> it ends: a mega horde walks on (HRD-14); any other
    disperses: its composition goes back to its zone's pool as active dead (change, reason
    'dispersed'), HORDE_GONE {horde_id, reason: 'dispersed', zone_id} setting status 'gone'.
    Otherwise it ticks: promote at its place when in area (a mega horde: HRD-14).
  The next HORDE_STEP (unless gone), cause = the last event committed here: moving -> at +
  leg_ms(place, route[0], props.speed_m_s or H.speed_m_s); milling -> the earliest of
  props.until, props.next_press (a mega horde) and — while its place (a mega horde: any outdoor
  place of its zone) is in area — at + H.tick_min minutes. Returns every event committed, in seq
  order.
HRD-06 Straggle and rally at a hub: per type (TYPES order) k = floor(its count x H.straggle) fall
  behind into the hub zone's pool (change(..., +k, 0, 'straggled')); then a 'drift' or 'mega' horde
  gathers r = floor(the hub zone's active dead of that type x H.rally) (change(..., -r, 0,
  'rallied')). composition += r - k per type; HORDE_MOVED's payload gains stragglers and rallied
  ({type: n}, non-zero entries only). A horde left with nothing -> HORDE_GONE {reason: 'spent'}.
HRD-07 promote(tx, rng, horde_id, place_id, at, turn_index, cause) -> list[str]   (contact: counts
  become bodies where the player is)
  present = living infected bodies positioned in place_id whose infected_state.horde_id is this
  horde; n = min(H.local_cap - present, count); n <= 0 -> []. Taken in TYPES order, m = min(what is
  left of that type, what is still wanted); each body: world.infected.spawn(tx, rng, place_id,
  type, at, turn_index, cause, x_m / y_m = the point on place_id's side of its first portal (by
  portal_id; physical.space.portal_point) else the centre, origin 'materialize', horde_id =
  horde_id). HORDE_PROMOTED {horde_id, place_id, bodies: [the new ids], composition: what is left}
  updating the composition (nothing left -> status 'gone' and HORDE_GONE {reason: 'spent'}). Then
  per new body (in order): the first living, non-infected body in the place it sees
  (world.infected.sees) -> world.infected.attract(reason 'sight'); else, when the horde still has
  a route, attract(target = route[0], reason 'horde'). A body is never merged back into a count
  (fidelity §5: it keeps its wounds and what it did). Returns the new body ids.
HRD-08 press(tx, rng, horde_id, settlement_id, at, turn_index, cause) -> Event   (fidelity C01: the
  dead kill the living who are there)
  N = count; D = settlements.defences; pressure = N / (H.breach_scale x (1 + D)); p = min(0.95,
  max(0, pressure - 0.5)) — 0 for an enclave (world.factions FAC-01: sealed underground, it is
  never broken into; its gate is pressed and nothing more); breached = rng.chance(tx, 'hordes',
  f"breach:{horde}:{settlement}:{at}", p); breached -> killed (below) and one bite draw per named member there (below), in member id
  order — all drawn before anything is written. HORDE_PRESSED {horde_id, settlement_id, count: N,
  pressure: round(pressure, 2), breached, killed, bitten} (place_id = the settlement's site), then,
  each caused by it:
    not breached, N >= H.breach_scale: society.settlement.adjust 'defences' -1 and 'morale' -1
      (reason 'horde'); world.traces.create 'damage' "Claw marks and dents all along the
      barricade." at the site (source = the HORDE_PRESSED id);
    breached: 'defences' -2 and 'morale' -2 (reason 'horde'); killed = min(its unnamed people,
      ceil(N x H.breach_kill)), taken from its cohorts in reverse serving order (highest band
      rank, then highest cohort_id — those on the walls) with society.population.adjust_cohort(
      ..., reason 'horde'), and their dead rise (HRD-16, pathway 'wet'); every named member
      positioned at the site or in a room under it and outside the active area (by id):
      rng.chance(tx, 'hordes', f"bite:{horde}:{member}:{at}", H.breach_bite) ->
      physical.bodies.apply_harm(a 'significant' 'bite' on rng.choice(('arm_l', 'arm_r')),
      contamination 3) and physical.bodies.expose(tx, rng, member, 'wet', 'bite', ...); bitten =
      those ids; traces
      'damage' "Barricades torn down; the gate hangs open." and 'blood' "Blood everywhere, and drag
      marks.".
  Returns the HORDE_PRESSED event.
HRD-09 draw(tx, place_id, source_db, at, turn_index, cause) -> str | None   (E01: a loud noise draws
  a district's finite dead; action.propagate calls it for every NOISE whose source_db >=
  H.draw_db)
  z = the zone of place_id (a room: its building's); not a region zone, or a 'drawn' horde formed
  in z less than H.draw_cooldown_h hours ago -> None. Per type: n = floor(active x H.draw_share x
  (source_db - H.draw_db + 10) / 10); nothing -> None. form(tx, 'drawn', z, composition, place_id,
  at, turn_index, cause, first_leg_ms = H.draw_minutes x MIN) (they are on their way).
HRD-10 day(tx, rng, at, turn_index, cause) -> list[Event]   (world.worldmove.day step 6, after
  world.infected.day)
  1 Lifecycle (E03; a Runner becomes a Shambler, never the reverse): per pool row holding runners
    (by zone_id): n = floor(runners / H.runner_days) + (1 when rng.chance(tx, 'hordes',
    f"degrade:{zone}:{d}", the fraction left)), at most the runners, taken from the active ones
    first -> change(RUNNER, -a, -b) and change(SHAMBLER, +a, +b) (reason 'degraded').
  2 Drift (horde_pressure): per region zone (by zone_id) whose active dead >= H.drift_min:
    rng.chance(tx, 'hordes', f"drift:{zone}:{d}", H.drift_chance x horde_pressure / 5) ->
    composition = floor(active x H.drift_share) per type (nothing -> no horde); to = rng.choice(tx,
    'hordes', f"drift_to:{zone}:{d}", the hubs of the region zones a route joins to it, by
    place_id) (none -> no horde); form(tx, 'drift', zone, composition, to, ...).
  3 The Mega Horde: forming (HRD-12), then its signs (HRD-13).
HRD-11 census(store) -> dict   (the LOD view: the developer panel and the cheats read it)
  {'pools': {zone_id: {type_id: [active, dormant]}} (zones with any dead), 'hordes': [{horde_id,
  kind, count, zone_id, place_id, status, target_place}] (not gone, by horde_id), 'bodies': living
  infected bodies, 'total': the dead in pools + hordes + bodies}.
  density(store, zone_id) -> int: min(10, round(10 x the zone's active dead / H.density_full)) —
  the heat map of a district (it replaces the old encounter ratings wherever the world asks how
  thick the dead are: world.worldmove OPS-03).
HRD-12 The Mega Horde forms (the end-game event). At most one exists at a time (status not 'gone').
  days = the number of WORLD_DAY events so far (today's included); p =
  H.mega_daily_chance[difficulty] x horde_pressure / 5 x min(1, days / H.mega_ramp_days);
  rng.chance(tx, 'hordes', f"mega:{d}", p) ->
    entry = rng.weighted(tx, 'hordes', f"mega_entry:{d}", [(exterior zone, its active dead)] by
    zone_id; none with any -> no horde); size = min(its active dead, rng.range_int(tx, 'hordes',
    f"mega_size:{d}", *H.mega_size[difficulty]));
    composition: per type floor(size x its active / the entry's active), the rest Shamblers;
    target = the region zone with the most people living in its settlements (the census totals of
    the settlements whose site is in it; ties by zone_id; nobody anywhere -> the entry's gateway
    zone, the region zone its route joins); exit = the exterior zone (not entry) whose gateway zone
    is the most route hops from the target (ties by zone_id); eta = rng.range_int(tx, 'hordes',
    f"mega_eta:{d}", *H.mega_eta_days); form(tx, 'mega', entry, composition, the target's hub, at,
    turn_index, cause, props = {exit_zone, eta_at: at + eta x DAY, signs: [], speed_m_s:
    H.mega_speed_m_s, passage: {}}, first_leg_ms = eta x DAY) — it sets foot on the road into
    the region at eta_at exactly (the long walk in from the country is its first leg) and reaches
    the gateway's hub when that road has been walked. Then world.factions.sighted(tx, horde_id, at,
    turn_index, the HORDE_FORMED id) (FAC-03: a faction with a route watch knows at once).
HRD-13 The signs, every WORLD_DAY while the mega horde is still at its entry hub: left =
  ceil((eta_at - at) / DAY); each sign once, in this order, recorded in props.signs (HORDE_SIGN
  {horde_id, sign} updating props):
  left <= 7 'birds': NOISE {source_db: 70, kind: 'birds', text: 'A whole flock goes over at once,
    all of it heading the same way: away.', place_id} (writer 'action.propagate') at every outdoor
    place (indoor 0, parent_id NULL) of the gateway zone, by place_id.
  left <= 5 'talk': world.rumours.seed(tx, holder, about = the gateway zone's hub, 'horde_coming',
    at, turn_index, the HORDE_SIGN id, subject_type='place') for the leader — else the first named
    member by id — of every settlement whose site is in the gateway zone or in a zone one route
    away from it (by settlement_id).
  left <= 2 'roar': NOISE {source_db: 95, kind: 'distant_roar', text: 'A low roar, far off, that
    never stops.', place_id} at every outdoor place of the gateway zone and of the target zone.
  (The Ghosts' route watch sees it sooner: their faction content, P10.)
HRD-14 Passage. A mega horde arriving at a REGION zone's hub mills there for ceil(count /
  H.mega_throughput_per_day x 24) hours (props.until) and the zone is SATURATED: every place of the
  zone with parent_id NULL and indoor 0 -> physical.space.change_place(tx, it, {'ambient_db':
  max(its own, H.mega_ambient_db)}, 'horde', ...) with the old value kept in props.passage[zone]
  {place: old ambient_db}, and a TRACE 'tracks' "The ground is churned to mud by thousands of
  feet." there (source = the HORDE_MOVED id); it presses every settlement of the zone at once and
  again every 24 h of its stay (props.next_press); every tick it promotes (HRD-07) at every outdoor
  place of the zone that is in the active area. When the stay ends: the zone's places get their
  ambient_db back (change_place, reason 'horde gone') and it walks on (status 'moving'): route =
  the rest of its route, or — at the target — path(here, the exit zone's hub).
  At the exit zone's hub it is gone: its composition joins that zone's pool (change, reason
  'passed') and HORDE_GONE {horde_id, reason: 'left', zone_id}.
  Its FIRST region passage (props.passage empty before it) also calls world.factions.passage(tx,
  horde_id, True, at, turn_index, the HORDE_MOVED id) (FAC-03: the enclaves seal), and its
  HORDE_GONE — however it ends — calls passage(..., False, ..., the HORDE_GONE id).
HRD-15 Conservation (fidelity F04, tests check it): census(store)['total'] changes only by: the dead
  that rise (POOL_CHANGE reason 'risen'; world.infected.rise), cheat spawns (P12) and infected
  bodies destroyed. Every other move — populate, promote, draw, drift, disperse, straggle, rally,
  pass — takes from one form exactly what it gives to another.
HRD-16 The dead of the unnamed rise (E03). Whoever makes unnamed people die of something that leaves
  bodies (society.settlement privation: pathway 'cold_start'; HRD-08: 'wet') calls
  schedule_rise(tx, rng, zone_id, count, pathway, at, turn_index, cause) -> str:
  kernel.clock.schedule(tx, at + rng.range_int(tx, 'hordes', f"rise:{cause}:{zone_id}", lo x 60,
  hi x 60) x MIN (lo, hi = the canon pathway's rise_after_death_h), 'POOL_RISE', zone_id,
  {'zone_id', 'count', 'pathway'}, cause) (its queue id). rise(tx, rng, row, fired, turn_index) ->
  list[Event] (the POOL_RISE handler): the pathway's rise_as types share the count — the first
  gets count - count // 4, the second (when there is one) count // 4 -> change(zone, type, +n, 0,
  'risen') each, cause fired.
HRD-17 Nothing here reads a mind or what the player knows. People learn of a horde by hearing it,
  seeing it or being told (NOISE, bodies in sight, rumours).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..contracts.events import Event
    from ..kernel.rng import Rng
    from ..kernel.store import Store, Tx


def pool(store: "Store | Tx", zone_id: str) -> dict[str, tuple[int, int]]:
    raise NotImplementedError("P10")


def total(store: "Store | Tx", zone_id: str) -> int:
    raise NotImplementedError("P10")


def change(tx: "Tx", zone_id: str, type_id: str, active_delta: int, dormant_delta: int, reason: str, at: int,
           turn_index: int, cause: str | None) -> "Event":
    raise NotImplementedError("P10")


def seed_pools(tx: "Tx", params, at: int) -> list["Event"]:
    raise NotImplementedError("P10")


def count(store: "Store | Tx", horde_id: str) -> int:
    raise NotImplementedError("P10")


def target(store: "Store | Tx", place_id: str) -> str:
    raise NotImplementedError("P10")


def path(store: "Store | Tx", from_place: str, to_place: str) -> list[str] | None:
    raise NotImplementedError("P10")


def leg_ms(store: "Store | Tx", from_place: str, to_place: str, speed_m_s: float) -> int:
    raise NotImplementedError("P10")


def form(tx: "Tx", kind: str, zone_id: str, composition: dict[str, int], to_place: str, at: int, turn_index: int,
         cause: str | None, *, props: dict | None = None, first_leg_ms: int | None = None) -> str:
    raise NotImplementedError("P10")


def step(tx: "Tx", rng: "Rng", row: dict, fired: "Event", turn_index: int) -> list["Event"]:
    raise NotImplementedError("P10")


def promote(tx: "Tx", rng: "Rng", horde_id: str, place_id: str, at: int, turn_index: int, cause: str | None) -> list[str]:
    raise NotImplementedError("P10")


def press(tx: "Tx", rng: "Rng", horde_id: str, settlement_id: str, at: int, turn_index: int,
          cause: str | None) -> "Event":
    raise NotImplementedError("P10")


def draw(tx: "Tx", place_id: str, source_db: float, at: int, turn_index: int, cause: str | None) -> str | None:
    raise NotImplementedError("P10")


def day(tx: "Tx", rng: "Rng", at: int, turn_index: int, cause: str | None) -> list["Event"]:
    raise NotImplementedError("P10")


def census(store: "Store | Tx") -> dict:
    raise NotImplementedError("P10")


def density(store: "Store | Tx", zone_id: str) -> int:
    raise NotImplementedError("P10")


def schedule_rise(tx: "Tx", rng: "Rng", zone_id: str, count: int, pathway: str, at: int, turn_index: int,
                 cause: str | None) -> str:
    raise NotImplementedError("P10")


def rise(tx: "Tx", rng: "Rng", row: dict, fired: "Event", turn_index: int) -> list["Event"]:
    raise NotImplementedError("P10")
