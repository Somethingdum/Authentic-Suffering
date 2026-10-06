"""Skull Packet builder (P4). THE ONLY CONSTRUCTOR OF SkullPacket. Rules SKULL-01..10, WILL-00, WILL-C,
IDN (the card), LOOK-06.
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

TEMPER-08 (H1) A person knows their own state: body_lines gains the strain line, each entity its
  PacketEntity.feeling, and a snap of outlet 'words' this wave sets SkullPacket.outburst — all as
  mind.temper TEMPER-08 words them. The prompt shows the feeling in the entity's line, after its
  relation, as '; ' + feeling, and the outburst first under what is happening now.
PORT-07 (P11, D-07) portrayal_note = audit.portrayal.note_for(tx, actor, turn_index): a note left
  by a retrospective portrayal audit, shown after the outburst (prompts/actor_cognition.user.j2).

LOOK-06 (F1a, F1b) Everyone the holder sees now comes with what the holder sees and smells of them:
  each entity 'here' carries PacketEntity.appearance (entities below — mind.perception.
  appearance_text at the best level and the distance, then smell_text), and the prompt shows it on
  its own line under the entity's line; nobody out of sight gets one.

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
          members of the holder's households, by actor_id; (4) (D-153, SKULL-11) known_elsewhere:
          the bodies the holder knows by name (acquaintance.known_name not null) not yet listed
          and whose death it has not perceived (no percept_log row of its own of a DEATH event of
          that body), most recently seen first (acquaintance.last_seen descending, then
          subject_id), at most PacketRules.max_known_elsewhere — people you know do not stop
          existing when they leave the room (the player's character has no relationships rows at
          all, C06: before this, its packet knew nobody it could not see).
  A1..An  affordances.options in AffordanceSet order, then consulted.options (so a consultation
          appends handles and never renumbers one already offered); the handle map value is the
          option's BoundAffordance.signature 'def_id:target:destination:item' ('*' for an empty
          slot).
  L1..Ln  open loops (below) in packet order.   E1..En  memories (P6).
  G1..Gn  (B4, GEST-01) gestures, in this order: per action.effects.GESTURES entry (catalog
          order) whose hands <= physical.bodies.capacity(actor).hands_free — an untargeted one
          once; a targeted one once per P-handle whose whereabouts is 'here', in P order, at most
          3 (the first three). Handle value f'{gesture_id}:{body id or "*"}'. Label = the
          gesture's label with {target} = the P-handle's description.
  F1..Fn  (B4, FOCUS-01) attention points: every P-handle whose whereabouts is 'here', in P
          order (label f'Keep your eyes on {description}'), then every portal of the actor's
          place the actor has a visual percept of this turn, by portal_id (label f'Watch {thing_phrase(
          portal name)}' — D-237: 'Watch the way to Pump house': a door you can see is the door; (D-259) the name
          is perception.portal_name(tx, portal, the actor's place): from inside, 'Watch the way out to the yard'). Handle value = the body or portal id. A reaction packet
          offers neither G nor F handles (its answer is short; Actor Spec §7).
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
  unprocessed       (B5, MEM-19) the texts of mind.memory.unprocessed(tx, actor_id), turn by turn in
                    order, flattened — what happened to them that no summary has settled yet (a
                    failed writeback never makes a person forget what they just said or saw).
                    The prompt shows them under 'Still raw from before' when there are any.
  body_lines        in this order, each a full sentence:
                    * (D-208) what has hold of you: per body that grips the actor
                      (physical.bodies.grips_on, by id) f'{perception.word_for(actor, it),
                      capitalised} has hold of you.' ('One of the dead has hold of you.'); then,
                      when physical.bodies.tied(actor), 'Your hands and feet are tied.' — held
                      after the moment it happened, a person still knows it;
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
                    * (F1c) the cold: COLD_LINES[needs.cold_stage] when the stage is >= 1; then
                      what you have on, when bodies.looks is recorded: physical.objects.coverage
                      lacks 'torso' and 'groin' -> BARE_LINES[0], lacks 'torso' only ->
                      BARE_LINES[1];
                    * impairment: 1-2 'Everything is harder than it should be.', 3-4 'You are
                      struggling to function.', 5-6 'You can barely function.';
                    * P10: per physical.bodies.stages(actor) (pathway order), the stage's ``felt``
                      sentence when it is not empty — what the host feels, never what it has;
                    * (D-107) what the talk left, by physical.bodies.mind_of(actor): MIND_LINES
                      [mind] — how it feels from inside, never what happened or why (DOOM-06);
                    nothing to say -> ['Unhurt.'].
  resolve_cur / resolve_max   the actors row.
  position_text     f'{at_phrase(anchor name)} in {place_phrase(place name)}' ('at the counter in
                    the sales floor'), or f'in {place_phrase(place name)}' with no anchor.
  perceived_now     every non-speech percept of this turn as PerceivedItem(handle, channel,
                    fidelity, text = percept text, source_handle = the P-handle of source_id or
                    None, seconds_ago = (at - percept.at) / 1000). (D-277) The prompt says whose it is
                    after the text — 'A short woman stands at the gap behind the counter. (P2)'.
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
                    appearance (LOOK-06): for an entity 'here', mind.perception.appearance_text(
                    tx, actor_id, the body, the best level of those VISUAL percepts ('clear' over
                    'partial'), space.point_distance(actor, body)) and mind.perception.smell_text(
                    tx, actor_id, the body, at), the non-empty ones joined with one space; else ''.
                    The prompt shows it on its own line under the entity's line.
  relationships     RelationshipLine(handle, text) per entity with a relationships row from the
                    holder, in entity order. text = the non-zero axes, in the order trust, fear,
                    respect, affection, resentment, obligation, joined with '; ', first letter
                    capitalised, ending '.' — (D-165) worded by how much, not only which way
                    (values -3..3; REL_WORDS in the implementation): trust 3 'you would trust them
                    with your life', 2 'you trust them', 1 'you mostly trust them', -1 'you are wary
                    of them', -2 'you distrust them', -3 'you do not trust them at all'; fear 1 'they
                    make you uneasy', 2 'you fear them', 3 'you are terrified of them'; respect 1 'you
                    think well of them', 2 'you respect them', 3 'you look up to them', -1 'you think
                    little of them', -2 'you look down on them', -3 'you despise them'; affection 1
                    'you like them', 2 'you care about them', 3 'you love them', -1 'you dislike
                    them', -2 'you can't stand them', -3 'you hate them'; resentment 1 'something they
                    did still rankles', 2 'you resent them', 3 'you will not forgive them';
                    obligation 1 'you owe them', 2 'you owe them a great deal', 3 'you owe them your
                    life', -1 'they owe you', -2 'they owe you a great deal', -3 'they owe you their
                    life'. All zero -> 'No strong feelings.'
                    e.g. 'You would trust them with your life; you love them.'
  beliefs           BeliefLine per live believed holding (believed = 1, superseded_by NULL; the
                    text is the proposition's, or for a claims row '<predicate> <value>'), best
                    PacketRules.max_beliefs by (confidence desc, acquired_at desc, claim_id asc).
                    provenance_text: witnessed 'you saw it'; overheard 'you overheard it';
                    told_by:<id> f'{name or with_article(describe)} told you'; read:<id> 'you
                    read it'; common 'everyone says so'; childhood 'since you were small'; (D-130) group 'your
                    people say so';
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
                    lore       (D-130, LORE-03) f'{text} ({provenance_text as for beliefs})' per
                               Retrieved.lore entry: what people say about what is in front of them —
                               at most PacketRules.max_lore lines, pinned: they bear on this
                               moment, so SKULL-09 counts them and never drops them;
                    open_loops LoopLine per loop;
                    refusals   f'You refused: {summary}.' per refusal — only refusals whose
                               requester is here or named (MEM-17).
  open_loops        the holder's loops with status 'open', ordered (strength desc, created_at desc,
                    loop_id), up to PacketRules.max_open_loops: LoopLine(L#, kind, text +
                    mind.promise.suffix(tx, loop_id)) — (B5d) how a promise it carries stands:
                    'I said I would: … (agreed between you)'.
  refusals          the actor's refusals with status 'standing' or 'reopened', by created_at:
                    f'You refused: {request_summary}.'
  commitments       current_task: the actor's task named by actors.current_task, else its first
                    'active' task by started_at -> f'{label} ({steps_done} of {steps_total} done)';
                    (D-118) none -> the paused task keep_working would name -> f'{label} ({steps_done}
                    of {steps_total} done, put down for now)' — interrupted work is not forgotten;
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
  gestures / attention_points   (B4) ExpressionOption(G# | F#, label, hands) per handle above
                    (hands 0 for attention); hands_free = capacity(actor).hands_free. The prompt
                    lists them after the options; the answer may name one of each (INTENT-09).
  uncertainty       one line per PARTIAL or TONE_ONLY percept, in S order: f'You did not catch all
                    of {S#}.' — (D-158) a visual one f'You could not make out all of {S#}.' (D-277: the
                    prompt says them once each way, prompts.render.doubts.)
  families          [] when reaction or consulted; else mind.consult.families(affordances, the
                    canon affordance defs by id) — CONSULT-03.
  consult_kinds     [] when reaction or consulted; else ['recall'] + ['more_actions'] when
                    families is not empty — CONSULT-01.
  looked_up         consulted.lines, or [].
  voice_examples    (D-116) choose_examples(the fused dossier's voice.examples, reaction=reaction,
                    rules=PacketRules) — EXAMPLE-02. The prompt shows them right after the card (stable
                    per person, so a cached prompt stays cached, PROMPT-01).

  thread            (D-117) thread_lines(tx, actor_id, turn_index, at, names, PacketRules) — THREAD-01, with
                    names(body) = the body's P-handle when this packet gave it one, else what the holder calls
                    them (acquaintance known_name, else with_article(describe)).

THREAD-01 thread_lines(tx, holder_id, turn_index, at, names, rules) -> list[ThreadLine]   (D-117; Actor
  Spec §11: "a short holder-specific conversation thread ... Never inject the UI's complete chat
  transcript. Remembered statements outside the room enter only through legitimate memory or later
  report.") What was said where the holder is now, before this moment, as the holder heard and said it.
  since = max(at - rules.thread_window_min minutes, the at of the holder's latest MOVE event (actor_id =
  holder) whose payload to_place differs from its from_place — when they arrived where they are).
  Heard: the holder's percept_log rows of channel 'speech' with turn_index < turn_index (this turn's are
  the utterances), since <= at' <= at (SKULL-10) and source_id distinct from the holder: speaker =
  names(source_id) ('Someone' when source_id is NULL), words = cut_heard(detail.words, max_heard_chars) —
  '' when the fidelity is tone_only — to_me = detail.addressed_to_me; (D-284) heard pieces of one utterance
  (SEG-01: the same SPEECH payload utterance_id, from the same speaker) that follow one another in the merged
  order below are one line at the first's time: words joined with one space ('…' for a piece of which only the
  tone came through; '' when none did), cut_heard again, to_me if any piece was. Said: the holder's voice_lines
  with since <= at' < at: speaker 'you', to_me False. Merged by (at, then the event order: the heard
  SPEECH's seq, or the seq of the speaker's own SPEECH that wrote the line, then id),
  the last rules.max_thread_lines kept, oldest first; ago_text = the beliefs' age words for at - at'.
  unanswered: a heard line to_me whose mind.firewall.classify_form(words) is QUESTION and after which
  (at' greater) the holder said nothing in the merged list before the cut.
THREAD-02 The prompt shows the thread under 'What was said here before this moment (oldest first)' —
  per line f'- {ago_text}, ' + ('you' | the speaker + (' to you' when to_me)) + ': ' + the words in
  quotes, or '(you could not make out the words)' — + ' (you have not answered)' when unanswered —
  between where the person is and what reaches them now. No lines: no heading.

EXAMPLE-02 choose_examples(examples, *, reaction, rules) -> list[VoiceExample]   (pure)
  A deliberation: the examples in the dossier's order (the author's: most telling first) while the
  running sum of estimate_tokens(situation + by + said_to_them + they_say) + 8 per example stays within
  rules.voice_example_tokens; the first that would pass it ends the list (no reshuffling to squeeze in
  a smaller one: the same person shows the same examples every call). A reaction (a split second):
  only those whose pressure is 'pressure' or 'limit', in order, at most rules.voice_examples_reaction,
  within the same token cap. None or an empty list -> [].
EXAMPLE-03 The prompt (prompts/actor_cognition.user.j2, shared by the reaction) shows them under
  'Moments from before, in your own words (how you sound; never lines to repeat):' as, per example,
  '- ' + situation, then (when said_to_them) f'  {by or "Someone"}: "{said_to_them}"', then
  f'  You: "{they_say}"'. A person with none shows nothing (no heading).

Budget (SKULL-09): tokens = estimate_tokens(system + '\n' + user) of
  prompts.render(CallClass.ACTOR_COGNITION, p=packet) (ACTOR_REACTION when reaction=True). While
  over PacketRules.token_budget[key], drop ONE item and re-render, in this order: (D-116) voice
  examples (last first: how someone sounds gives way before what they remember), memories (last
  first), lessons (last first), (D-117) thread lines (oldest first), beliefs (last first), relationship lines whose entity is not a
  source of this turn's percepts (last first), refusals created more than 7 days before ``at``
  whose requester is not a source of this turn's percepts (oldest first), (B5) the unprocessed
  lines of every unsettled turn but the latest (the oldest line first), uncertainty lines (last
  first). Never dropped (Actor Spec AC16: what bears on this decision is pinned, never cut for
  age or length): identity (the card), recent_lines, body, position, perceived_now, utterances, (D-130) lore,
  entities, affordances, commitments, stakes, resources, open loops, what a consultation brought
  back (looked_up), the latest unsettled turn's unprocessed lines, and every refusal whose
  requester is a source of this turn's percepts (someone here or speaking now). Every item
  dropped is recorded, in drop order, in ``omitted`` (never rendered: an audit of what was cut):
  'example: ' + the example's they_say, 'memory: ' + the MemoryLine text, 'lesson: ' + the lessons entry,
  'thread: ' + the line's words, 'belief: ' + the BeliefLine
  text, f'relationship: {handle}: {text}', 'refusal: ' + the refusals entry, 'unprocessed: ' + the
  line, 'uncertainty: ' + the line — e.g. 'refusal: You refused: hand me the revolver.' When
  nothing droppable is left the packet is returned over budget (the scheduler logs it).
No instruction to forget anything is ever added (L1): what must not be used is absent.

AMB-01 ambient_packet(tx, actor_id, turn_index, at, *, doing='', idle=False) -> AmbientPacket | None   (D-128)
  What a COLD person — someone past this moment's model budget — has to go on to say one short thing,
  or nothing (turn.cognition AMB-02). Their own records only (Skull Law), at <= ``at`` (SKULL-10).
  reached: their percept_log rows of this turn or the one before (turn_index - 1 .. turn_index) that
    are not scene percepts (event_id 'scene:...'), whose source is not themselves, at <= ``at`` and
    later than their own latest SPEECH event (what they spoke after has had its answer); the newest
    4, oldest first. A speech percept reads f'{word} said' + (' to you' when addressed_to_me) +
    f': "{words}"' (word = perception.word_for, 'Someone' without a source; the words as heard, cut
    to PacketRules.max_heard_chars by cut_heard); any other its text. Nothing reached -> None:
    nobody talks to the air on code's time — unless (D-150) ``idle``: then reached is [] (a quiet
    moment), and None only when nobody of ``people`` (below) is in their place now (nobody to talk to).
  voice: the fused dossier's — the capsule; 'How you talk: ' + the tendencies, each a sentence (a '.' added to one
    that does not end in '.', '!', '?' or '"'; D-237: its first letter upper-cased), joined ' ' (D-244: left
    out when the capsule already holds every one of them, as a generated person's does); f'Easy:
    "{low_stakes}"', f'Under pressure: "{under_pressure}"', f'At the limit: "{at_the_limit}"';
    'You would never say: ' + each never-say in quotes joined '; '; the profanity line (none 'You do
    not swear.', rare 'You rarely swear.', frequent 'You swear often.', constant 'You swear all the
    time.'); f'How you sound: {the dialect notes}' (D-244: as a sentence, as the card says it) when not
    empty.
  where: perception.place_phrase(their place's name). name: actors.display_name. doing: as given.
  when: (D-159) world_time_text exactly as the SkullPacket words it for them (the clock only with a
    timepiece) — the prompt no longer says "years after the Fall" of a world eighteen days into it.
  state: their body lines (as the SkullPacket's body) but 'Unhurt.', the first 3.
  said: their own last 3 voice_lines by (at, line_id), oldest first — never to be said again.
  knows: (D-130) the texts of mind.retrieval.lore_lines(tx, actor_id, turn_index, at, min(2,
    PacketRules.max_lore)) — what people say about what is in front of them.
  mind: (D-257) only in a quiet moment (reached is []): what might be on their mind to bring up — or not —
    from their own records, at most 2. Candidates, in this order, each when there is one: f'What you are
    working on: {end(life.current_project)}' (the fused dossier's; not one that says 'decided at worldgen');
    f'On your mind: {end(text)}' of their strongest 'open' loop (strength desc, created_at desc, loop_id);
    f'What you are afraid of: {end(fears[0])}'; f'Something people here say: {end(text)}' of one of their live
    believed holdings with provenance 'common' and predicate 'history' (by claim_id, the one at turn_index mod
    their count); f'Something you grew up hearing: {end(text)}' of one of their lore_held lines (by lore_ref,
    belief; the one at turn_index mod their count; its canon text). The two taken are the candidate at
    turn_index mod their count and the one after it (wrapping): a room's small talk is about their lives and
    what their world says, a different thing from turn to turn — never the same few words of the weather.
  people: the living human bodies, not themselves, that are the source of a percept of theirs this
    turn at <= ``at``, in order of first percept, at most 6: handle P1.., word = word_for, feeling =
    the TEMPER-08 words and then their relationship line (as the SkullPacket's), lower-cased and
    joined '; ' ('' with neither). handles: P# -> body id.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..contracts.common import LOD
from ..contracts.mind import SkullPacket

if TYPE_CHECKING:
    from ..contracts.mind import AmbientPacket
    from ..kernel.store import Tx
    from .affordance import AffordanceSet
    from .consult import Consulted


# D-107: how a doomed mind feels from inside (mind.packet body_lines). Nothing about what it heard.
MIND_LINES: dict[str, str] = {
    "shattered": "Something in you has come apart. Thoughts won't hold together, and words come out in pieces.",
    "broken": "Something in you is broken. You can't hold a thought for long, and you can't face much of anything.",
    "held": "Something happened to you that you cannot put into words. You are holding on. Barely.",
}

COLD_LINES: dict[int, str] = {     # F1c (physical.bodies LOOK-09): needs.cold_stage -> what the body says
    1: "You are cold.", 2: "You are cold.", 3: "You are shivering hard.", 4: "You are shivering hard.",
    5: "You are freezing to death.", 6: "You are freezing to death.",
}
BARE_LINES: tuple[str, str] = ("You have nothing on.", "You are bare to the waist.")   # F1c


def build_packet(tx: "Tx", actor_id: str, lod: LOD, affordances: "AffordanceSet", turn_index: int,
                 at: int, *, reaction: bool = False, consulted: "Consulted | None" = None) -> SkullPacket:
    raise NotImplementedError("P4")


def thread_lines(tx: "Tx", holder_id: str, turn_index: int, at: int, names, rules) -> list:
    raise NotImplementedError("D-117")


def ambient_packet(tx: "Tx", actor_id: str, turn_index: int, at: int, *, doing: str = "",
                   idle: bool = False) -> "AmbientPacket | None":
    raise NotImplementedError("D-128")


def choose_examples(examples, *, reaction: bool, rules) -> list:
    raise NotImplementedError("D-116")


def estimate_tokens(text: str) -> int:
    """len(text) // 4 (implemented; the same estimate is used everywhere)."""
    return len(text) // 4
from ._impl_packet import ambient_packet, build_packet, choose_examples, thread_lines  # noqa
