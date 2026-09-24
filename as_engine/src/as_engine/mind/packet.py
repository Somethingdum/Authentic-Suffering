"""Skull Packet builder (P4). THE ONLY CONSTRUCTOR OF SkullPacket. Rules SKULL-01..10, WILL-00, WILL-C,
IDN (the card).
MUST NOT import as_engine.kernel.truth (SKULL-02, import-graph test). Reads only: the actor's
own body, wounds, needs and inventory, its actors row and fused dossier, percept_log rows for
this holder, its claim_holdings + propositions, its relationships / acquaintance / households /
open_loops / refusals / plans / tasks rows, voice_lines, episodes (via mind.retrieval from P6),
and the AffordanceSet passed in. Never another body's state: 'here' and 'near you' come from
this holder's percepts.

build_packet(tx, actor_id, lod, affordances, turn_index, at, *, reaction=False, consulted=None)
    -> SkullPacket
  lod COLD -> ValueError (COLD actors get no packet, LOD-02). An empty AffordanceSet -> ValueError
  (the affordance floor makes that impossible; failing loudly beats an empty menu).
  Budget key: 'reaction' when reaction=True, else lod.value ('hot' | 'warm').
  ``consulted`` (a mind.consult.Consulted) rebuilds the packet of a decision after its one
  consultation, from the same snapshot (the same ``at`` and AffordanceSet): its options are
  appended to the menu, its lines are the looked_up field, and nothing more may be consulted.

SKULL-10 (P10) Nothing later than the moment reaches a mind: a mind deciding at ``at`` knows only
  its percepts with at <= ``at``. A wave's landings are written when the wave resolves (and a
  timer's action with its landing, P10), so a later percept can be in the log before an earlier
  reaction decides. Every reader of "this turn's percepts" for a decision at ``at`` reads the
  percept_log rows with turn_index == turn_index AND at <= ``at``: this packet, mind.affordance
  (known bodies and items, threats, the attention point), mind.retrieval (the moment set) and
  turn.select (salience; mind.cues always did).

Handles (never an internal id in anything rendered — SKULL-06 is tested over the rendered prompt):
  S1..Sn  this holder's percept_log rows with turn_index == turn_index and at <= ``at`` (SKULL-10),
          ordered (at, percept_id),
          EXCEPT standing-view rows (event_id starting 'scene:') older than the latest standing
          view among those rows (only the rows with the greatest ``at`` among them count: a
          room described twice is shown once, as it is now); ONE numbering over perceived_now
          and utterances together.
  P1..Pn  bodies, each once, never the holder: (1) the source_id of those percepts, in percept
          order, when source_id is a body (items and portals are sources too — they are not
          entities); (2) bodies the holder has relationships rows toward, by to_id; (3) the other
          members of the holder's households, by actor_id.
  A1..An  affordances.options in AffordanceSet order, then consulted.options (so a consultation
          appends handles and never renumbers one already offered); the handle map value is the
          option's BoundAffordance.signature 'def_id:target:destination:item' ('*' for an empty
          slot).
  L1..Ln  open loops (below) in packet order.   E1..En  memories (P6).
  ``handles`` maps every handle to its internal id (percept_id, body id, signature, loop_id,
  episode_id) and is never rendered. tests/helpers.handle_for finds an option by def and referent.

Fields (second person, plain English):
  world_time_text   time as the person knows it (Actor Spec §5): the clock only for someone who has
                    a timepiece — an item held, worn or carried (inventory_tree) whose def tags
                    contain 'timepiece' — f'{format_clock(at)}, day {world_time(at).day} since the
                    Fall ({part_of_day})', e.g. '23:14, day 18 since the Fall (night)'; anyone else
                    f'Day {world_time(at).day} since the Fall ({part_of_day})'.
  identity          mind.identity.compile_identity(mind.actor.fused(tx, actor_id), minimum=reaction)
                    (IDN-01..05; Actor Spec AC02 / AC04): the whole card for a deliberation, the
                    reaction card for a reaction. What the card keeps out — writers_notes,
                    knowledge.does_not_know, who knows a secret, reflexes, counts that go stale —
                    reaches no field of the packet (IDN-02).
  recent_lines      mind.actor.recent_lines(n = PacketRules.max_recent_lines).
  body_lines        in this order, each a full sentence:
                    * per unhealed wound (created_at, wound_id): f'{SEVERITY_WORDS[severity]
                      capitalised} {type} wound to your {ANATOMY_WORDS[anatomy]}{", bleeding" when
                      physical.bodies.effective_bleed > 0}.'  ('A deep stab wound to your left
                      arm, bleeding.', 'A shallow cut wound to your left hand.');
                    * pain (bodies.pain): 1-2 'It hurts.', 3-4 'The pain is bad.', 5-6 'The pain is
                      almost more than you can take.';
                    * blood loss: 'You have lost some blood.' at >= the first
                      HarmRules.impairment_from_blood_loss threshold, 'You have lost a lot of
                      blood and feel light-headed.' at >= the second (the higher one wins);
                    * needs, thirst then hunger then fatigue: stage 2-3 'You are thirsty.' /
                      'You are hungry.' / 'You are tired.'; stage 4-6 'You are desperately
                      thirsty.' / 'You are starving.' / 'You are exhausted.';
                    * impairment: 1-2 'Everything is harder than it should be.', 3-4 'You are
                      struggling to function.', 5-6 'You can barely function.';
                    * P10: per physical.bodies.stages(actor) (pathway order), the stage's ``felt``
                      sentence when it is not empty — what the host feels, never what it has;
                    nothing to say -> ['Unhurt.'].
  resolve_cur / resolve_max   the actors row.
  position_text     f'{at_phrase(anchor name)} in {place_phrase(place name)}' ('at the counter in
                    the sales floor'), or f'in {place_phrase(place name)}' with no anchor.
  perceived_now     every non-speech percept of this turn as PerceivedItem(handle, channel,
                    fidelity, text = percept text, source_handle = the P-handle of source_id or
                    None, seconds_ago = (at - percept.at) / 1000).
  utterances        every speech percept as UtteranceView: words / volume / addressed_to_me from
                    percept_log.detail; words longer than PacketRules.max_heard_chars are cut to
                    their first max_heard_chars characters, then back to the last space among
                    them when there is one after the first character, and end ' …' (Actor Spec
                    §5: a flood of words is heard, not obeyed, and never crowds the person out of
                    their own context);
                    speaker_handle = P-handle of source_id (None when the source is unknown);
                    standing = firewall.classify_standing(tx, source_id, actor_id, words) (STRANGER
                    when source_id is None); form = firewall.effective_form(firewall.classify_form(
                    words, weapon_pointed_at_receiver = detail.armed_at_me), standing) (TONE_ONLY
                    words '' classify as STATEMENT) — standing and form read the whole words.
                    The words appear ONLY inside UtteranceView — never in a field or sentence
                    named request, order, task or ask (WILL-00).
  entities          PacketEntity per P-handle: known_name = acquaintance.known_name (or None);
                    description = known_name or with_article(perception.describe(tx, actor_id,
                    body)); relation_summary = f'your {kind with _ as spaces}' from the holder's
                    relationships row when its kind is not 'acquaintance', else None;
                    whereabouts (Actor Spec AC14: present, heard, remembered and last known are
                    different things, and being related to someone never puts them here):
                    'here' when a percept of this turn (the S rows above) with that source_id is
                    VISUAL at clear or partial; else 'heard, not seen' when one is auditory or
                    speech; else, from the holder's acquaintance row, f'last seen in
                    {place_phrase(last_seen_place name)} {age}' (age worded as for beliefs, from
                    at - last_seen) when last_seen and last_seen_place are set; else 'not seen'.
  relationships     RelationshipLine(handle, text) per entity with a relationships row from the
                    holder, in entity order. text = the non-zero axes, in the order trust, fear,
                    respect, affection, resentment, obligation, joined with '; ', first letter
                    capitalised, ending '.': trust > 0 'you trust them', < 0 'you distrust them';
                    fear > 0 'you fear them'; respect > 0 'you respect them', < 0 'you look down
                    on them'; affection 1-2 'you care about them', 3 'you love them', < 0 'you
                    dislike them'; resentment > 0 'you resent them'; obligation > 0 'you owe
                    them', < 0 'they owe you'. All zero -> 'No strong feelings.'
                    e.g. 'You trust them; you love them.'
  beliefs           BeliefLine per live believed holding (believed = 1, superseded_by NULL; the
                    text is the proposition's, or for a claims row '<predicate> <value>'), best
                    PacketRules.max_beliefs by (confidence desc, acquired_at desc, claim_id asc).
                    provenance_text: witnessed 'you saw it'; overheard 'you overheard it';
                    told_by:<id> f'{name or with_article(describe)} told you'; read:<id> 'you
                    read it'; common 'everyone says so'; childhood 'since you were small';
                    rumour / rumour:<id> 'a rumour'; inferred 'your own guess'; anything else
                    'you are not sure where from'. age_text from (at - acquired_at): < 60 s 'just
                    now'; < 1 h 'N minutes ago' ('1 minute ago'); < 1 day 'N hours ago'; else
                    'N days ago'.
  memories, lessons  [] until P6. From P6 (MEM-10) mind.retrieval.retrieve(tx, actor_id,
                    turn_index, at, max_beliefs = PacketRules.max_beliefs, max_memories =
                    .max_memories, max_loops = .max_open_loops) supplies beliefs, memories,
                    lessons, open_loops and refusals, in its order (the P4 contract tests only
                    look at membership where the orders could differ):
                    beliefs    BeliefLine per entry, worded as above;
                    memories   MemoryLine(E#, text = summary, age_text as for beliefs, from the
                               episode's at) per episode, E1..En in that order; handles E# -> episode_id;
                    lessons    f'Experience taught you: {text}' per lesson;
                    open_loops LoopLine per loop;
                    refusals   f'You refused: {summary}.' per refusal — only refusals whose
                               requester is here or named (MEM-17).
  open_loops        the holder's loops with status 'open', ordered (strength desc, created_at desc,
                    loop_id), up to PacketRules.max_open_loops: LoopLine(L#, kind, text).
  refusals          the actor's refusals with status 'standing' or 'reopened', by created_at:
                    f'You refused: {request_summary}.'
  commitments       current_task: the actor's task named by actors.current_task, else its first
                    'active' task by started_at -> f'{label} ({steps_done} of {steps_total} done)';
                    plan_step = plans.steps[0] when the plans row has steps; standing_orders =
                    f'On {trigger with _ as spaces}: {response}.' per plans.standing_orders entry
                    ('On loud noise: find the source and cover it.'); deadline = None (P6+).
  stakes            dependents: per id in the holder's household_members.guardian_of, f'{name or
                    with_article(describe)} (near you)' when a percept of this turn has that
                    source_id, else '(not with you)'; obligations: text of open loops of kind
                    promise_made or debt_owing; would_lose: [].
  resources         [] when the actor carries nothing; else ONE line f'You have: {", ".join(parts)}.'
                    with one part per item of physical.objects.inventory_tree, depth first:
                    with_article(name) when qty is 1, else f'{qty} {name}' (the tree's name is
                    already ItemDef.plural then) + ' (in your right hand)' / ' (in your left
                    hand)' for hand_r / hand_l, + ' (holstered)' when props.holstered, + f' (in
                    {thing_phrase(container name)})' for an item inside another item. Never
                    rounds, charge or other props — what is in a gun is a belief, not a fact
                    the mind can read off its own inventory.
                    e.g. 'You have: a .38 revolver (holstered), 11 .38 rounds.'
  WILL-C fill       when any utterance has addressed_to_me: current_task None -> 'You are not in
                    the middle of anything.'; empty stakes.would_lose -> ['Nothing you can name.'];
                    empty resources -> ['You carry nothing.'].
  affordances       AffordanceOption(A#, verb, label, cost_note, risk_note) per option.
  uncertainty       one line per PARTIAL or TONE_ONLY percept, in S order: f'You did not catch all
                    of {S#}.'
  families          [] when reaction or consulted; else mind.consult.families(affordances, the
                    canon affordance defs by id) — CONSULT-03.
  consult_kinds     [] when reaction or consulted; else ['recall'] + ['more_actions'] when
                    families is not empty — CONSULT-01.
  looked_up         consulted.lines, or [].

Budget (SKULL-09): tokens = estimate_tokens(system + '\n' + user) of
  prompts.render(CallClass.ACTOR_COGNITION, p=packet) (ACTOR_REACTION when reaction=True). While
  over PacketRules.token_budget[key], drop ONE item and re-render, in this order: memories (last
  first), lessons (last first), beliefs (last first), relationship lines whose entity is not a
  source of this turn's percepts (last first), refusals created more than 7 days before ``at``
  whose requester is not a source of this turn's percepts (oldest first), uncertainty lines (last
  first). Never dropped (Actor Spec AC16: what bears on this decision is pinned, never cut for
  age or length): identity (the card), recent_lines, body, position, perceived_now, utterances,
  entities, affordances, commitments, stakes, resources, open loops, what a consultation brought
  back (looked_up), and every refusal whose requester is a source of this turn's percepts
  (someone here or speaking now). Every item
  dropped is recorded, in drop order, in ``omitted`` (never rendered: an audit of what was cut):
  'memory: ' + the MemoryLine text, 'lesson: ' + the lessons entry, 'belief: ' + the BeliefLine
  text, f'relationship: {handle}: {text}', 'refusal: ' + the refusals entry, 'uncertainty: ' + the
  line — e.g. 'refusal: You refused: hand me the revolver.' When nothing droppable is left the
  packet is returned over budget (the scheduler logs it).
No instruction to forget anything is ever added (L1): what must not be used is absent.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..contracts.common import LOD
from ..contracts.mind import SkullPacket

if TYPE_CHECKING:
    from ..kernel.store import Tx
    from .affordance import AffordanceSet
    from .consult import Consulted


def build_packet(tx: "Tx", actor_id: str, lod: LOD, affordances: "AffordanceSet", turn_index: int,
                 at: int, *, reaction: bool = False, consulted: "Consulted | None" = None) -> SkullPacket:
    raise NotImplementedError("P4")


def estimate_tokens(text: str) -> int:
    """len(text) // 4 (implemented; the same estimate is used everywhere)."""
    return len(text) // 4
