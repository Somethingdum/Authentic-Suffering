"""Affordance enumeration: what THIS body could attempt at all (P4). Rules AFF-01..09, L6/L7.

CODE computes affordances -> the model chooses among them and motivates (plan §6.4).

enumerate_affordances(tx, actor_id, catalog, at, turn_index) -> AffordanceSet
  catalog = the AffordanceDefs in canon order (tx.canon.all('affordance') sorted by ref).
  Binding uses the actor's OWN knowledge (AFF-01); the truth layer is not consulted for target
  existence (the intent barrier re-checks against T0, stage 7):
    KNOWN BODIES   bodies that are the source_id of this actor's percepts this turn (visual at
                   clear/partial, or named speech) — silhouettes cannot be targeted.
    KNOWN ITEMS    its own inventory exactly (every item held in any slot, and their contents);
                   items that are the source_id of its standing-view percepts this turn; items
                   it BELIEVES are in its current place (a live, believed claim_holding whose
                   proposition has subject_type 'object', predicate 'location' and object_value =
                   an anchor of its place or the place id) — bound at the believed anchor.
    KNOWN PORTALS  portals of its current place except walls.
    KNOWN ANCHORS  anchors of its current place (it is home ground or it is standing in it).
  Candidates per ``binds``:
    none / self    one option, no referent.
    anchor         every known anchor; defs whose effect is move_to_anchor skip the anchor the
                   actor stands at (you do not walk to where you are; hiding or taking cover
                   where you stand is allowed); take_cover: anchor cover >= 1; hide: anchor
                   concealment >= 1.
    portal         every known portal; per effect: move_through_portal / climb need the far side
                   (always known); open_portal is_open 0 and barricade 0; close_portal is_open 1;
                   lock/unlock/pick_lock kinds door/gate/window, is_open 0; barricade_portal
                   is_open 0 and barricade < 3; unbarricade_portal barricade > 0; force_portal
                   is_open 0; climb_obstacle height_cm > 0; peek_portal is_open 0 (a gap);
                   watch_portal any.
    body           every known body (not the actor).
    item_held      items in hand_l / hand_r.  item_carried  its items in worn/pocket/pack slots
                   and inside containers it carries (never a firearm's loaded magazine).
                   Per effect: eat -> items whose def has a ``food`` block; drink -> a ``water``
                   block; equip -> any carried item except kind clothing and worn containers;
                   throw_distraction -> held items with bulk <= 3 that are not firearms (nobody throws
                   their gun to make a noise); reload -> held firearms.
    item_reachable known items lying in its place (seen or believed).
    container      container items (def has ``container``) lying in its place or carried.
    speech         one option addressed to 'everyone' (target None) plus one per known body.
    wound          its own unhealed wounds, and those of known bodies within touch seen at clear.
  Ranges: self; touch <= 1.5 m (space.point_distance); reach / same_place = in the actor's place
  (the effect walks there — duration base_s + per_meter_s x distance); visible = a known body /
  portal / item (it perceived it this turn); audible = a known body or 'everyone';
  adjacent_place = through a portal of its place.
  For each AffordanceDef in catalog order and each binding, run the gates IN THIS ORDER and record
  the first failing gate for the decision audit (Rejection):
    physical  capacity (mobile / hands_free / conscious), range, requires.held_item_tags (ONE held
              item whose def tags contain every listed tag), requires.carried_item_tags (one
              carried-or-held item with each tag), posture_any, actor_kinds (the actor's body
              kind), target_kinds, target_alive (PERCEIVED: a target is 'still' when its posture
              is lying/prone and it is unconscious, dead or false-dead — what anyone can see),
              admits() for move_through_portal
    skill     (requires.skill min_rank, OR requires.skill_or_belief_cue held as a belief cue; a def
              with only skill_or_belief_cue needs the cue)
    belief    (every requires.belief_cues held — e.g. 'knows_headshot_rule')
    resolve   (mind.resolve.gate)
    resource  shoot_* : rejected only when the actor BELIEVES the held firearm is empty (a live
              claim_holding on subject_type 'object', subject_id = that firearm, predicate
              'loaded' with believed 0 — the load of a gun is not visible, so an actor tries a
              trigger until it learns otherwise: INTENT-03 depends on this); reload_firearm: a
              carried magazine or ammo item whose tags carry the firearm's caliber tag; medical
              defs: the carried item's props.uses is absent or > 0
    duty      movement farther than 5 m from actors.duty_anchor adds MoralTag abandon_post and
              cost_note "It means leaving your post at the <anchor name>."; an active law
              (laws_active of the settlement whose place is the actor's place, or a group law of a
              group the actor belongs to) whose LawEffect.effect is 'forbid', applies to this
              actor (members / visitors / all) and whose affordance_tag matches EITHER the def's
              tags OR the bound option's moral tags rejects the option (so a theft law naming
              'steal' catches pick_up_item on an owned item even though 'steal' is a moral tag
              computed per binding); 'cost' laws do not reject, they set cost_note = cost_note.
    moral     option moral tags = def.moral_tags + moral_tags_if_target[every target kind] + the
              COMPUTED tags below; if they intersect the dossier motive.moral_line.wont_tags the
              option is rejected: an Actor never even sees options that cross its own line; the
              PC is gated the same way, only by the tags in its own dossier (L12).
  Computed moral tags (per binding):
    harm_dependent    an attack-verb option on a body the actor is guardian_of, or a member of its
                      household;
    attack_unarmed    an attack-verb option on a human holding no firearm or melee item in hand;
    abandon_post      see duty;
    abandon_dependent an option that takes the actor out of its place (move_through_portal,
                      leave_place, flee_threat, climb_obstacle) while a KNOWN body (above) it is
                      guardian_of stands in that place and a threat was perceived this turn — a
                      dependent it has not perceived this turn does not hold it back (it does not
                      know he is there);
    leave_wounded     the same kinds of option while a body the actor has affection >= 1 toward
                      stands in that place and was seen at clear this turn with an unhealed,
                      unclotted severe or catastrophic wound (seen at clear = the wound is visible);
    steal             via moral_tags_if_target 'owned' (see target kinds below).
  A THREAT this turn = a known body that is infected (bodies.kind 'infected': its shape and gait
  show it, though not its type), or the actor of an event this actor perceived this turn that was
  a HARM, an ACTION_START with payload verb 'attack', or a SPEECH whose percept detail has
  armed_at_me (a weapon in hand while it spoke to this actor).
  Survivors become BoundAffordance(def_id, verb, target_id, destination_id, item_id, label,
  ui_label, est_duration_s, noise_db, cost_note, risk_note, check, tags). est_duration_s =
  duration.base_s + duration.per_meter_s x the walking distance to the referent (0 for self /
  touch); tags = the def tags + the option's moral tags. Placeholders (label AND ui_label):
    {target}      a body: its known name or with_article(describe(...)); an item, container or
                  portal: thing_phrase(name) ('the office door'); a wound: f'the wound on your
                  <anatomy words>' (own) or f'the wound on <ref>'s <anatomy words>'; keep_working:
                  the task label; a speech option addressed to everyone: 'anyone who can hear'.
    {destination} an anchor: thing_phrase(anchor name); a place (move_through_portal's far side):
                  place_phrase(place name).
    {item}        label: f'your {name}' for the actor's own items, else thing_phrase(name);
                  ui_label: the bare item name (the ui_label templates carry their own 'the').
                  name = ItemDef.name, or ItemDef.plural when the item's qty > 1 ('your .38
                  rounds'). The same name is used for {target} when the target is an item.
    {distance}    f'{max(1, round(d))} m'.
    {duration}    duration_words(est_duration_s) — a bare amount, the templates say 'about'.
  (perception.with_article / thing_phrase / place_phrase: the phrase helpers are shared so every
  module words people, things and places the same way.)
Selection (AFF-07). Every surviving option gets a GROUP, by rank:
    0 continue   verb CONTINUE_TASK
    1 threat     only when a threat was perceived this turn: verb ATTACK, or a def tagged
                 'threat_response' (flee_threat, take_cover, hide, go_prone, surrender,
                 shield_dependent, break_grip, shove)
    2 speak      verb SPEAK
    3 move       verbs MOVE, FLEE
    4 act        verbs MANIPULATE, SEARCH, TREAT, SIGNAL, TAKE_COVER, HIDE, SURRENDER, ESCAPE
                 (not tagged 'posture')
    5 attack     verb ATTACK (no threat this turn)
    6 hold       everything else (OBSERVE, WAIT, GUARD, rest, sleep), and outside a threat every
                 def tagged 'posture' (crouch, go_prone, stand_up: changing how you stand is
                 waiting, not doing — it must not crowd out picking something up)
  Sort key: (group, inner, DISTANCE, catalog index, target id). inner is 0 except:
    threat group  0 an ATTACK on a threat, 1 a def tagged 'protect_dependent', 2 verbs FLEE /
                  ESCAPE, 3 verbs TAKE_COVER / HIDE, 4 SURRENDER, 5 anything else (attacks on
                  bodies that are not threats, shove) — facing a shambler with a gun in hand,
                  'shoot it' must never lose its slot to 'crouch';
    hold group    0 defs tagged 'freeze', 1 verb OBSERVE, 2 verb GUARD, 3 the rest (so 'stay
                  where you are' and 'watch' are never crowded out by 'sleep').
  DISTANCE for an option bound to an anchor or portal = metres from that point to the actor's
  ATTENTION POINT; for any other referent = metres from the actor; 0 with no referent. The
  attention point is where the actor's loudest sound this turn came from, as far as its own place
  goes: the source point when the source is in its place, else the point on its side of the portal
  the sound arrived through (percept detail 'via_portal'); with no sound this turn, the actor's
  own position. (So after a crash out back the anchors toward the storeroom door come first.)
  Walking the sorted list, each group keeps at most 3 options per def_id. The packet list is then
  filled ROUND-ROBIN: round 1 takes the first option of every non-empty group in rank order, round
  2 the second of each, and so on, until PacketRules.max_affordances options are taken or every
  group is exhausted — every kind of response gets a slot before any kind gets a second one (a
  room full of anchors must not crowd out 'keep counting' or 'freeze'). The chosen options are
  finally listed in sort-key order, which is the A1.. order. If fewer than
  PacketRules.min_affordances survive, WAIT and OBSERVE options are added.
Binding (AFF-02): `binds` is the PRIMARY referent; defs whose effect needs a second referent
enumerate it too, one option per combination (then capped by the selection rules):
  give_item            item_held x each other body within touch range (target)
  put_into_container   container in reach x each held item that fits by bulk (item)
  take_from_container  container in reach x each item inside it the actor knows about (item)
  throw_distraction    item_held with bulk <= 3, not a firearm, x each anchor visible within 15 m
                       (destination)
  reload_firearm       held firearm x a carried magazine or ammo matching its caliber tag
  shoot_*, strike_*, finish_downed   body x the held weapon (item = the weapon)
  punch, grapple, shove, disarm, break_grip, calm_person, signal, watch_target  body only
  bandage/tourniquet/suture/clean/pressure  wound (own, or of a body within touch) x the carried
                       medical item whose tags match (pressure needs no item)
  keep_working         only when the actor has an active task; {target} = the task label
  surrender            only when a threat was perceived this turn (nobody gives up to an empty room)
  flee_threat          body = each threat this turn (A THREAT above)
  shield_dependent     only when a threat was perceived this turn; body = each known body that is
                       not a threat and that the actor is guardian_of, shares a household with, or
                       has a relationships row with affection >= 1 toward
Target kinds for moral_tags_if_target: bodies -> body kind ('human','infected','lurker','animal')
and, for humans, ALSO the age band ('infant','child','preteen','teen','adult','elder'), so a child
target yields both 'human' and 'child' tags; items -> 'owned' when props.owner names a body,
household or group that is not the actor, the actor's household or a group the actor belongs to.
Duty gate details: see 'duty' and the computed moral tags above (abandon_post, abandon_dependent).
Label placeholders: {target} {destination} {item} {distance} (e.g. '4 m') {duration} (e.g.
'3 seconds', '2 minutes'). A label using any other placeholder is a content error reported under
CNT-06.

Belief cues (AFF-10): a cue is HELD by an actor when a lessons row for that holder carries the cue
id in cue_tags with confidence >= 1. Rows come from dossier knowledge.cues and held lore beliefs'
cues (worldgen WG6 / scenario load, confidence 3) and from lessons drawn at writeback (a person who
watched a "dead" infected get back up can learn knows_false_death). The gate reads lessons only —
never the truth layer, never a pack record directly.
Skill gates WHAT you try (AFF-05, Combat Incompetence carried): an untrained shooter who does not
hold 'knows_headshot_rule' is offered 'shoot centre mass' but never 'shoot the head' (holding the
belief lets anyone TRY for the head — at +2 resistance, 07_RULES.md §5.1, so the untrained mostly
miss), and nobody is offered 'finish the downed one' unless they hold 'knows_false_death'.
WILL-03: two Actors differing only in skills[] and Resolve (tests/fixtures/scenarios/two_skills.yaml)
must be offered menus that differ BECAUSE of that difference: (1) at least 3 def_ids are offered to
one and not the other; (2) every def_id offered to the trained, steady twin and not to the other
appears in the other's rejections at the skill, belief or resolve gate — the difference comes
from capability, not from which options the round-robin happened to keep. (A raw Jaccard number
is not the measure: generic options such as speak / wait / observe are rightly offered to both,
and item ids differ between two people carrying their own copies.)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..contracts.common import Verb

if TYPE_CHECKING:
    from ..contracts.content import AffordanceDef, CheckSpec
    from ..kernel.store import Tx


@dataclass(frozen=True)
class BoundAffordance:
    def_id: str
    verb: Verb
    label: str
    ui_label: str
    target_id: str | None = None
    destination_id: str | None = None
    item_id: str | None = None
    est_duration_s: float = 0.0
    noise_db: float = 0.0
    cost_note: str | None = None
    risk_note: str | None = None
    check: "CheckSpec | None" = None
    tags: tuple[str, ...] = ()

    @property
    def signature(self) -> str:
        return f"{self.def_id}:{self.target_id or '*'}:{self.destination_id or '*'}:{self.item_id or '*'}"


@dataclass
class Rejection:
    def_id: str
    target_id: str | None
    gate: str  # physical|skill|belief|resolve|resource|duty|moral
    detail: str


@dataclass
class AffordanceSet:
    actor_id: str
    options: list[BoundAffordance] = field(default_factory=list)
    rejected: list[Rejection] = field(default_factory=list)


def enumerate_affordances(tx: "Tx", actor_id: str, catalog: list["AffordanceDef"], at: int,
                          turn_index: int) -> AffordanceSet:
    raise NotImplementedError("P4")


def duration_words(seconds: float) -> str:
    """A bare amount of time (implemented; labels write 'about {duration}'): < 1.5 s 'a second';
    < 60 s f'{round(s)} seconds'; < 90 s 'a minute'; < 3600 s f'{round(s / 60)} minutes';
    < 5400 s 'an hour'; else f'{round(s / 3600)} hours'."""
    if seconds < 1.5:
        return "a second"
    if seconds < 60:
        return f"{round(seconds)} seconds"
    if seconds < 90:
        return "a minute"
    if seconds < 3600:
        return f"{round(seconds / 60)} minutes"
    if seconds < 5400:
        return "an hour"
    return f"{round(seconds / 3600)} hours"


def jaccard(a: AffordanceSet, b: AffordanceSet) -> float:
    """Jaccard similarity over BoundAffordance.signature (implemented; a tooling / eval helper)."""
    sa = {o.signature for o in a.options}
    sb = {o.signature for o in b.options}
    if not sa and not sb:
        return 1.0
    return len(sa & sb) / len(sa | sb)
