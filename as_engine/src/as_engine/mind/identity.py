"""The identity card (P4, IMPLEMENTED; Actor Spec §4, AC02 and AC04). Rules IDN-01..05.
docs/as/05_ACTORS.md §2.1. A pure function of a dossier: it reads nothing and stores nothing.

The dossier stays whole (DOS-01); the card is the person a decision call shows — every part of the
dossier that says who someone is, in plain lines, each traceable to the fields it came from. It is
the same card in a deliberation, a reaction, a writeback and a reflection, and no budget ever trims
it (SKULL-09): a smaller prompt never costs a person their identity.

IDN-01 compile_identity(dossier, *, minimum=False) -> IdentityCard   (``dossier``: ActorDossier or
  PCDossier — pass mind.actor.fused, so accepted developments, the dossier deltas, are in it)
  name / age / one_line from identity; dossier_hash (IDN-04); the sections below, in this order,
  each line a CardLine(text, sources). A section with no lines is left out.
  Wording helpers: end(s) = s stripped, plus '.' unless it already ends in . ! ? … or a closing
  quote (" ” ' ’); bare(s) = s stripped, minus one trailing '.' when it ends in exactly one;
  cap(s) = first letter upper-cased; spaced(tag) = tag with '_' as ' '; a list joined 'in words' =
  its items bare, joined with '; '.
  'who' (heading None):
    f'You are {name}, {age}. {end(one_line)}'                    [identity.name, identity.age, identity.one_line]
    f'People also call you {", ".join(aliases)}.'                [identity.aliases]   (aliases only)
    end(f'You come from {birthplace}')                           [identity.birthplace]
    f'Before the Fall: {end(occupation_before)}'                 [identity.occupation_before]
    f'Now: {end(occupation_now)}'                                [identity.occupation_now]
  'priorities' ('What matters to you'):
    f'What you want most: {end(motive.motive)}'                  [motive.motive]
    f'How you go about it: {end(motive.method)}'                 [motive.method]
    f'What comes first, in order: {layers in words}.'            [decision_stack.layers]
    f'Except: {end(c)}' per inversion condition i                [decision_stack.inversion_conditions[i]]
    f'Once, when it mattered: {end(past_example)}'               [decision_stack.past_example]
    f'How you take risks: {end(motive.risk_text)}'               [motive.risk_text]
  'values' ('Your limits'):
    f'You will: {moral_line.will in words}.'                     [motive.moral_line.will]
    f"You won't: {moral_line.wont in words}."                    [motive.moral_line.wont]
    f'What you owe: {life.obligations in words}.'                [life.obligations]   (when any)
  'contradictions' ('Where you are pulled both ways'), per contradiction i:
    f'You believe: {end(belief_a)}'                              [contradictions[i].belief_a]
    f'You also believe: {end(belief_b)}'                         [contradictions[i].belief_b]
    f'The first wins when: {end(a_wins_when)}'                   [contradictions[i].a_wins_when]
    f'The second wins when: {end(b_wins_when)}'                  [contradictions[i].b_wins_when]
  'private_life' ('Your own life'):
    f'What eats at you: {end(motive.inner_conflict)}'            [motive.inner_conflict]
    f'What you carry from before: {end(motive.past_wound)}'      [motive.past_wound]
    f'What you hope for: {end(life.aspiration)}'                 [life.aspiration]
    f'You also hope for: {life.hopes in words}.'                 [life.hopes]   (when any)
    f'What you are working on: {end(life.current_project)}'      [life.current_project]
    f'What you fear: {life.fears in words}.'                     [life.fears]
    f'What people see: {", ".join(bare(t) for t in shown_traits)}. What you tell them:
      {end(claimed_history)} Who you say you stand with: {end(presented_affiliation)}'
                                                                 [persona.public.shown_traits,
                                                                  persona.public.claimed_history,
                                                                  persona.public.presented_affiliation]
    f'What you hide: {end(concealed_history)}'                   [persona.private.concealed_history]
    f'What you really want: {true_goals in words}.'              [persona.private.true_goals]
    f'Who you really stand with: {end(real_affiliation)}'        [persona.private.real_affiliation]
    f'A secret you keep: {end(content)} If it came out: {end(exposure_consequence)}' per secret i
                                                                 [life.secrets[i].content,
                                                                  life.secrets[i].exposure_consequence]
  'habits' ('Your habits'):
    f'{cap(spaced(tag))}: {end(manifests)} It comes out when: {end(triggers)} What it makes you do:
      {end(causes)} What it costs you: {end(costs)} Once: {end(example)}' per trait i
                                                                 [traits[i].tag, .manifests, .triggers,
                                                                  .causes, .costs, .example]
    f'A habit of yours: {end(motive.signature_behaviour)}'       [motive.signature_behaviour]
    f'Under stress: {end(appearance.movement_under_stress)}'     [appearance.movement_under_stress]
    f'A habit of your hands: {end(appearance.habit_gesture)}'    [appearance.habit_gesture]
  'temper' ('What sets you off') — H1, from the dossier's temper (None: the section is left out):
    FUSE_WORDS[temper.fuse]                                      [temper.fuse]
    OUTLET_WORDS[temper.outlet]                                  [temper.outlet]
    GRUDGE_WORDS[temper.grudge]                                  [temper.grudge]
    f'Things that get under your skin: {pet_peeves in words}.'   [temper.pet_peeves]   (when any)
    f'What settles you: {end(cools_down_by)}'                    [temper.cools_down_by]   (when set)
    FUSE_WORDS = {1: 'You have a hair trigger.', 2: 'You have a short fuse.', 3: 'You can take a fair
      amount before you blow.', 4: 'It takes a lot to make you lose it.', 5: 'You almost never lose
      it. Almost.'}; OUTLET_WORDS = {fists: 'When you blow, you swing.', words: 'When you blow, you let
      them have it, out loud.', cold: 'When you blow, you go cold and cut them off.', flight: 'When you
      blow, you walk out.', tears: 'When you blow, you break down.'}; GRUDGE_WORDS = {0: 'You are over
      it by evening.', 1: 'A slight stays with you a while.', 2: 'You hold a grudge.', 3: 'You never
      forget.'} (implemented data below).
  'voice' ('How you talk'):
    end(voice.capsule)                                           [voice.capsule]
    f'How you tend to speak: {" ".join(end(t) for t in speech_tendencies)}'
                                                                 [voice.speech_tendencies]
    f'Your voice when it is easy: "{exemplars.low_stakes}"'      [voice.exemplars.low_stakes]
    f'Under pressure: "{exemplars.under_pressure}"'              [voice.exemplars.under_pressure]
    f'At your limit: "{exemplars.at_the_limit}"'                 [voice.exemplars.at_the_limit]
    f'You would never say anything like: {"; ".join(chr(34) + l + chr(34) for l in would_never_say)}'
                                                                 [voice.would_never_say]
    PROFANITY[voice.profanity]                                   [voice.profanity]
    f'How you sound: {end(dialect_notes)}'                       [voice.dialect_notes]   (when not empty)
  'silence' ('When you go quiet'):
    f'You go quiet when: {goes_quiet_when in words}.'            [silence.goes_quiet_when]
    f'When you are silent: {end(body_when_silent)}'              [silence.body_when_silent]
    f'You will not talk about: {refuses_to_discuss in words}.'   [silence.refuses_to_discuss]   (when any)
    end(comfortable_vs_uncomfortable)                            [silence.comfortable_vs_uncomfortable]
  'competence' ('What you know how to do'):
    f'{cap(spaced(domain))}: {RANK_WORDS[rank]}. {end(evidence)}' per skill i   [capability.skills[i]]
    f'You are good at: {", ".join(spaced(t) for t in tags)}.'    [capability.tags]   (when any)
    LITERACY_WORDS[literacy]                                     [capability.literacy]
    'No established specialist training beyond this list.'       [capability.skills]
IDN-02 Kept outside the card, never in any prompt a person's call renders (Actor Spec §4, §5):
  writers_notes (editorial guidance for authors — AC02), knowledge.does_not_know (naming a hidden
  fact supplies it — AC04; the field stays for authoring checks), life.secrets[].who_knows (other
  people's knowledge), id, generation, tags, depth_reference, days_since_fall_range, disposition
  (a generation prior and a default response, not a person's choice), capability.trained_responses
  (reflexes are code's, 05_ACTORS §7), motive.resource_constraints (a count that goes stale: what
  a person carries comes from the body and its items, SKULL-01), motive.risk_threshold and
  capability.special / resolve_trait_mod (numbers the rules use, not self-knowledge), the
  appearance numbers, and the knowledge seeds (knows / knows_but_hides / cues become beliefs and
  lessons with provenance, WG6 and the scenario loader, and reach a packet as beliefs).
IDN-03 Every line's sources are paths that exist in the dossier (list items by index); a line is
  made only from its sources and the fixed words above. The card is a pure function: the same
  dossier gives the same card, and a dossier delta changes exactly the lines whose sources it
  touched.
IDN-04 dossier_hash = sha256 hex of kernel.jsoncanon.canonical_json(dossier.model_dump(mode='json',
  by_alias=True)) — the decision audit's pin of which identity a call saw.
IDN-05 minimum=True gives the reaction card (Actor Spec §4: "keep a minimum identity card in
  reactions too"): a split second leaves no room for a whole life, never for none of it. The same
  lines, only these: 'who' all; 'priorities' without 'Once, when it mattered'; 'values' all;
  'temper' all (H1: a split second is when it matters); 'voice' only the capsule, 'Under pressure', 'At your limit' and 'You would never say'; 'silence'
  only 'You go quiet when'; 'competence' all. minimum = True on the card.
"""

from __future__ import annotations

import hashlib

from ..contracts.dossier import ActorDossier, PCDossier
from ..contracts.mind import CardLine, CardSection, IdentityCard
from ..kernel.jsoncanon import canonical_json

RANK_WORDS: dict[int, str] = {1: "trained", 2: "skilled", 3: "expert"}
LITERACY_WORDS: dict[int, str] = {
    0: "You cannot read or write.",
    1: "You can read and write a little, slowly.",
    2: "You read and write well enough.",
    3: "You read and write easily.",
}
PROFANITY: dict[str, str] = {
    "none": "You do not swear.",
    "rare": "You rarely swear.",
    "frequent": "You swear often.",
    "constant": "You swear all the time.",
}
HEADINGS: dict[str, str | None] = {
    "who": None,
    "priorities": "What matters to you",
    "values": "Your limits",
    "contradictions": "Where you are pulled both ways",
    "private_life": "Your own life",
    "habits": "Your habits",
    "temper": "What sets you off",
    "voice": "How you talk",
    "silence": "When you go quiet",
    "competence": "What you know how to do",
}
FUSE_WORDS: dict[int, str] = {
    1: "You have a hair trigger.", 2: "You have a short fuse.", 3: "You can take a fair amount before you blow.",
    4: "It takes a lot to make you lose it.", 5: "You almost never lose it. Almost.",
}
OUTLET_WORDS: dict[str, str] = {
    "fists": "When you blow, you swing.", "words": "When you blow, you let them have it, out loud.",
    "cold": "When you blow, you go cold and cut them off.", "flight": "When you blow, you walk out.",
    "tears": "When you blow, you break down.",
}
GRUDGE_WORDS: dict[int, str] = {
    0: "You are over it by evening.", 1: "A slight stays with you a while.", 2: "You hold a grudge.",
    3: "You never forget.",
}
_CLOSERS = (".", "!", "?", "…", '"', "”", "'", "’")


def end(s: str) -> str:
    s = s.strip()
    return s if s.endswith(_CLOSERS) else s + "."


def bare(s: str) -> str:
    s = s.strip()
    return s[:-1] if s.endswith(".") and not s.endswith("..") else s


def cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def spaced(tag: str) -> str:
    return tag.replace("_", " ")


def in_words(items: list[str]) -> str:
    return "; ".join(bare(i) for i in items)


def dossier_hash(dossier: ActorDossier | PCDossier) -> str:
    return hashlib.sha256(canonical_json(dossier.model_dump(mode="json", by_alias=True)).encode("utf-8")).hexdigest()


MINIMUM_PREFIXES: dict[str, tuple[str, ...] | None] = {
    "who": None, "values": None, "competence": None, "temper": None,
    "priorities": ("What you want most:", "How you go about it:", "What comes first", "Except:", "How you take risks:"),
    "voice": ("", "Under pressure:", "At your limit:", "You would never say"),
    "silence": ("You go quiet when:",),
}


def compile_identity(dossier: ActorDossier | PCDossier, *, minimum: bool = False) -> IdentityCard:
    d = dossier
    idn, mo, life, pe = d.identity, d.motive, d.life, d.persona
    out: dict[str, list[CardLine]] = {k: [] for k in HEADINGS}

    def add(key: str, text: str, *sources: str) -> None:
        out[key].append(CardLine(text=text, sources=list(sources)))

    add("who", f"You are {idn.name}, {idn.age}. {end(idn.one_line)}", "identity.name", "identity.age",
        "identity.one_line")
    if idn.aliases:
        add("who", f"People also call you {', '.join(idn.aliases)}.", "identity.aliases")
    add("who", end(f"You come from {idn.birthplace}"), "identity.birthplace")
    add("who", f"Before the Fall: {end(idn.occupation_before)}", "identity.occupation_before")
    add("who", f"Now: {end(idn.occupation_now)}", "identity.occupation_now")

    ds = d.decision_stack
    add("priorities", f"What you want most: {end(mo.motive)}", "motive.motive")
    add("priorities", f"How you go about it: {end(mo.method)}", "motive.method")
    add("priorities", f"What comes first, in order: {in_words(ds.layers)}.", "decision_stack.layers")
    for i, c in enumerate(ds.inversion_conditions):
        add("priorities", f"Except: {end(c)}", f"decision_stack.inversion_conditions[{i}]")
    add("priorities", f"Once, when it mattered: {end(ds.past_example)}", "decision_stack.past_example")
    add("priorities", f"How you take risks: {end(mo.risk_text)}", "motive.risk_text")

    ml = mo.moral_line
    add("values", f"You will: {in_words(ml.will)}.", "motive.moral_line.will")
    add("values", f"You won't: {in_words(ml.wont)}.", "motive.moral_line.wont")
    if life.obligations:
        add("values", f"What you owe: {in_words(life.obligations)}.", "life.obligations")

    for i, c in enumerate(d.contradictions):
        p = f"contradictions[{i}]"
        add("contradictions", f"You believe: {end(c.belief_a)}", f"{p}.belief_a")
        add("contradictions", f"You also believe: {end(c.belief_b)}", f"{p}.belief_b")
        add("contradictions", f"The first wins when: {end(c.a_wins_when)}", f"{p}.a_wins_when")
        add("contradictions", f"The second wins when: {end(c.b_wins_when)}", f"{p}.b_wins_when")

    add("private_life", f"What eats at you: {end(mo.inner_conflict)}", "motive.inner_conflict")
    add("private_life", f"What you carry from before: {end(mo.past_wound)}", "motive.past_wound")
    add("private_life", f"What you hope for: {end(life.aspiration)}", "life.aspiration")
    if life.hopes:
        add("private_life", f"You also hope for: {in_words(life.hopes)}.", "life.hopes")
    add("private_life", f"What you are working on: {end(life.current_project)}", "life.current_project")
    add("private_life", f"What you fear: {in_words(life.fears)}.", "life.fears")
    pub, pri = pe.public, pe.private
    add("private_life", f"What people see: {', '.join(bare(t) for t in pub.shown_traits)}. What you tell them: "
        f"{end(pub.claimed_history)} Who you say you stand with: {end(pub.presented_affiliation)}",
        "persona.public.shown_traits", "persona.public.claimed_history", "persona.public.presented_affiliation")
    add("private_life", f"What you hide: {end(pri.concealed_history)}", "persona.private.concealed_history")
    add("private_life", f"What you really want: {in_words(pri.true_goals)}.", "persona.private.true_goals")
    add("private_life", f"Who you really stand with: {end(pri.real_affiliation)}", "persona.private.real_affiliation")
    for i, sec in enumerate(life.secrets):
        add("private_life", f"A secret you keep: {end(sec.content)} If it came out: {end(sec.exposure_consequence)}",
            f"life.secrets[{i}].content", f"life.secrets[{i}].exposure_consequence")

    for i, t in enumerate(d.traits):
        p = f"traits[{i}]"
        add("habits", f"{cap(spaced(t.tag))}: {end(t.manifests)} It comes out when: {end(t.triggers)} What it makes "
            f"you do: {end(t.causes)} What it costs you: {end(t.costs)} Once: {end(t.example)}",
            f"{p}.tag", f"{p}.manifests", f"{p}.triggers", f"{p}.causes", f"{p}.costs", f"{p}.example")
    add("habits", f"A habit of yours: {end(mo.signature_behaviour)}", "motive.signature_behaviour")
    add("habits", f"Under stress: {end(d.appearance.movement_under_stress)}", "appearance.movement_under_stress")
    add("habits", f"A habit of your hands: {end(d.appearance.habit_gesture)}", "appearance.habit_gesture")

    tm = getattr(d, "temper", None)
    if tm is not None:
        add("temper", FUSE_WORDS[tm.fuse], "temper.fuse")
        add("temper", OUTLET_WORDS[tm.outlet], "temper.outlet")
        add("temper", GRUDGE_WORDS[tm.grudge], "temper.grudge")
        if tm.pet_peeves:
            add("temper", f"Things that get under your skin: {in_words(tm.pet_peeves)}.", "temper.pet_peeves")
        if tm.cools_down_by.strip():
            add("temper", f"What settles you: {end(tm.cools_down_by)}", "temper.cools_down_by")

    v = d.voice
    add("voice", end(v.capsule), "voice.capsule")
    add("voice", f"How you tend to speak: {' '.join(end(t) for t in v.speech_tendencies)}", "voice.speech_tendencies")
    add("voice", f'Your voice when it is easy: "{v.exemplars.low_stakes}"', "voice.exemplars.low_stakes")
    add("voice", f'Under pressure: "{v.exemplars.under_pressure}"', "voice.exemplars.under_pressure")
    add("voice", f'At your limit: "{v.exemplars.at_the_limit}"', "voice.exemplars.at_the_limit")
    add("voice", "You would never say anything like: " + "; ".join(f'"{line}"' for line in v.would_never_say),
        "voice.would_never_say")
    add("voice", PROFANITY[v.profanity], "voice.profanity")
    if v.dialect_notes.strip():
        add("voice", f"How you sound: {end(v.dialect_notes)}", "voice.dialect_notes")

    si = d.silence
    add("silence", f"You go quiet when: {in_words(si.goes_quiet_when)}.", "silence.goes_quiet_when")
    add("silence", f"When you are silent: {end(si.body_when_silent)}", "silence.body_when_silent")
    if si.refuses_to_discuss:
        add("silence", f"You will not talk about: {in_words(si.refuses_to_discuss)}.", "silence.refuses_to_discuss")
    add("silence", end(si.comfortable_vs_uncomfortable), "silence.comfortable_vs_uncomfortable")

    ca = d.capability
    for i, sk in enumerate(ca.skills):
        add("competence", f"{cap(spaced(sk.domain.value))}: {RANK_WORDS[sk.rank]}. {end(sk.evidence)}",
            f"capability.skills[{i}]")
    if ca.tags:
        add("competence", f"You are good at: {', '.join(spaced(t) for t in ca.tags)}.", "capability.tags")
    add("competence", LITERACY_WORDS[ca.literacy], "capability.literacy")
    add("competence", "No established specialist training beyond this list.", "capability.skills")

    if minimum:
        kept: dict[str, list[CardLine]] = {}
        for k, lines in out.items():
            if k not in MINIMUM_PREFIXES:
                continue
            prefixes = MINIMUM_PREFIXES[k]
            if prefixes is None:
                kept[k] = lines
            elif k == "voice":
                kept[k] = [ln for ln in lines if ln.sources == ["voice.capsule"]
                           or ln.text.startswith(prefixes[1:])]
            else:
                kept[k] = [ln for ln in lines if ln.text.startswith(prefixes)]
        out = {k: kept.get(k, []) for k in out}
    sections = [CardSection(key=k, heading=HEADINGS[k], lines=lines) for k, lines in out.items() if lines]
    return IdentityCard(name=idn.name, age=idn.age, one_line=idn.one_line, dossier_hash=dossier_hash(d),
                        minimum=minimum, sections=sections)
