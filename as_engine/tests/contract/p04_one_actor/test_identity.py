"""The identity card and a person's own prompt (P4; Actor Spec AC01-AC04). Rules IDN-01..05
(mind/identity.py) and the actor prompts (prompts/actor_*.j2).

A decision call shows a person the whole of who they are, every line traceable to their dossier,
and nothing an author wrote about them or that they cannot know. The instructions are a person's
own — no story, no author, no audience.
"""

from __future__ import annotations

import hashlib
import json
import re

import pytest

from as_engine.contracts.common import LOD, CallClass
from as_engine.contracts.dossier import ActorDossier
from as_engine.contracts.events import Event, EventType, WriteOp, WriteRecord
from as_engine.kernel.jsoncanon import canonical_json
from as_engine.mind import actor, identity, perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.mind.packet import build_packet
from as_engine.prompts.render import PROMPT_DIR, render

pytestmark = pytest.mark.phase(4)

KEYS = ["who", "priorities", "values", "contradictions", "private_life", "habits", "temper", "voice", "silence",
        "competence"]
HEADINGS = [None, "What matters to you", "Your limits", "Where you are pulled both ways", "Your own life", "Your habits",
            "What sets you off", "How you talk", "When you go quiet", "What you know how to do"]
ROLE_WORDS = re.compile(r"\b(story|stories|storyteller|narrat\w*|player|npc|author\w*|quest|performance|performer|"
                        r"audience|assistant|character|role-?play\w*|game)\b", re.I)
WORDED = ("voice.profanity", "temper.fuse", "temper.outlet", "temper.grudge")  # enums the card puts in words
CORE_OPENING = ("You are the person described under Who you are. The current moment is yours to respond to. Choose "
                "what you try to do, what you say if anything, and what you attend to from your own position.")
REACTION_LAST = ("Something just reached you. Respond to that immediate change with the response time and attempts "
                 "available here. You may keep your previous attempt if it still makes sense. There is no time for "
                 "extended reconsideration or recollection.")


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def packet_for(w, local, at, reaction=False):
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id(local), at, 0)
        aff = enumerate_affordances(tx, w.id(local), w.canon.all("affordance"), at, 0)
        return build_packet(tx, w.id(local), LOD.HOT, aff, 0, at, reaction=reaction)


def prompt(p, reaction=False) -> list[str]:
    return [m.content for m in render(CallClass.ACTOR_REACTION if reaction else CallClass.ACTOR_COGNITION, p=p)]


def delta(w, local, path, op, value, at):
    """One dossier delta, committed the way mind.actor commits one (an accepted development)."""
    with w.store.transaction() as tx:
        did = tx.mint("ddl")
        tx.commit_event(Event(type=EventType.REFLECTION, writer="mind.actor", at=at, turn_index=0, actor_id=w.id(local),
                              writes=[WriteRecord(op=WriteOp.INSERT, table="dossier_deltas", values={
                                  "delta_id": did, "actor_id": w.id(local), "event_id": "scenario", "path": path,
                                  "op": op, "value_json": json.dumps(value), "at": at})],
                              payload={"actor_id": w.id(local), "delta_id": did}))


def resolve(dump: dict, path: str):
    """The value at a card source path ('traits[1].causes') in a dossier dump."""
    node = dump
    for part in re.findall(r"[^.\[\]]+|\[\d+\]", path):
        node = node[int(part[1:-1])] if part.startswith("[") else node[part]
    return node


def norm(s: str) -> str:
    return s.lower().replace("_", " ").strip().rstrip(".")


# The wording helpers as IDN-01 states them (kept here so the tests do not borrow the module's own).
def end(s: str) -> str:
    s = s.strip()
    return s if s.endswith((".", "!", "?", "…", '"', "”", "'", "’")) else s + "."


def bare(s: str) -> str:
    s = s.strip()
    return s[:-1] if s.endswith(".") and not s.endswith("..") else s


def cap(s: str) -> str:
    return s[:1].upper() + s[1:]


# --------------------------------------------------------------------------- AC01 the prompt
def test_the_instructions_are_a_persons_own():
    """AC01: the system prompt is the Actor Spec's person-centred text, then the answer's shape;
    no story, narrator, player, author, audience or assistant anywhere in the fixed words — the
    system prompts and the literal text of the user template."""
    core = (PROMPT_DIR / "_actor_core.j2").read_text(encoding="utf-8").strip()
    answer = (PROMPT_DIR / "_actor_answer.j2").read_text(encoding="utf-8").strip()
    assert core.startswith(CORE_OPENING)
    for must in ("Do not search for a dramatic outcome.", "a gap in speech stays a gap",
                 "An order is someone asking for conduct, with whatever standing you recognize. Decide your response yourself.",
                 "Silence is valid.", "Choose an attempt; do not declare its success or anybody else's response."):
        assert must in core, must
    for gone in ("survival story", "If something is not written, you do not know it", "If an option is not listed",
                 "AUTHOR'S NOTES"):
        for f in PROMPT_DIR.glob("actor_*.j2"):
            assert gone not in f.read_text(encoding="utf-8"), (gone, f.name)
    literal = re.sub(r"{{.*?}}|{%.*?%}", " ", (PROMPT_DIR / "actor_cognition.user.j2").read_text(encoding="utf-8"))
    for text in (core, answer, literal):
        assert not ROLE_WORDS.search(text), ROLE_WORDS.search(text).group(0)


def test_a_reaction_adds_only_the_moment(scenario):
    """AC01: a reaction shows the same person and the same core instructions, then one last
    paragraph about the moment."""
    w = scenario("metal_fence")
    t = now(w)
    deliberate = prompt(packet_for(w, "mara", t))[0]
    react = prompt(packet_for(w, "mara", t, reaction=True), reaction=True)[0]
    assert react == deliberate + "\n\n" + REACTION_LAST
    core = (PROMPT_DIR / "_actor_core.j2").read_text(encoding="utf-8").strip()
    answer = (PROMPT_DIR / "_actor_answer.j2").read_text(encoding="utf-8").strip()
    assert deliberate == core + "\n\n" + answer


def test_the_message_begins_with_who_you_are(scenario, canon):
    """Actor Spec §6: the user message begins 'Who you are', its first sentence the person's name
    and age; the card comes first, the moment after it."""
    w = scenario("metal_fence")
    p = packet_for(w, "mara", now(w))
    user = prompt(p)[1]
    d = canon.get("core:actor/mara_voss")
    assert user.startswith(f"Who you are\nYou are {d.identity.name}, {d.identity.age}. ")
    assert user.startswith("Who you are\n" + p.identity.as_text())
    assert user.index("What you know how to do") < user.index("Right now:") < user.index("Possibilities you notice")


# --------------------------------------------------------------------------- IDN-01 the card
@pytest.mark.parametrize("ref", ["core:actor/mara_voss", "core:actor/june_okafor"])
def test_the_card_is_the_whole_person(canon, ref):
    """IDN-01 (AC04): who, priorities, limits, contradictions, private life, habits with what they
    make you do, what sets you off (H1), voice, silence and competence — in that order, in the
    dossier's own words."""
    d = canon.get(ref)
    card = identity.compile_identity(d)
    assert [s.key for s in card.sections] == KEYS and [s.heading for s in card.sections] == HEADINGS
    assert (card.name, card.age, card.one_line, card.minimum) == (d.identity.name, d.identity.age, d.identity.one_line, False)
    texts = {s.key: [ln.text for ln in s.lines] for s in card.sections}
    assert texts["who"][0] == f"You are {d.identity.name}, {d.identity.age}. {end(d.identity.one_line)}"
    ds = d.decision_stack
    assert f"What comes first, in order: {'; '.join(bare(x) for x in ds.layers)}." in texts["priorities"]
    assert [x for x in texts["priorities"] if x.startswith("Except: ")] == [f"Except: {end(c)}" for c in ds.inversion_conditions]
    want = []
    for c in d.contradictions:
        want += [f"You believe: {end(c.belief_a)}", f"You also believe: {end(c.belief_b)}",
                 f"The first wins when: {end(c.a_wins_when)}", f"The second wins when: {end(c.b_wins_when)}"]
    assert texts["contradictions"] == want
    for t, line in zip(d.traits, texts["habits"], strict=False):
        assert line.startswith(f"{cap(t.tag.replace('_', ' '))}: {end(t.manifests)}")
        assert f"What it makes you do: {end(t.causes)}" in line and f"What it costs you: {end(t.costs)}" in line
    tm = d.temper
    assert texts["temper"][:3] == [identity.FUSE_WORDS[tm.fuse], identity.OUTLET_WORDS[tm.outlet],
                                   identity.GRUDGE_WORDS[tm.grudge]], "H1: how this person breaks"
    if tm.pet_peeves:
        assert f"Things that get under your skin: {'; '.join(bare(x) for x in tm.pet_peeves)}." in texts["temper"]
    if tm.cools_down_by:
        assert texts["temper"][-1] == f"What settles you: {end(tm.cools_down_by)}"
    assert texts["silence"][0] == f"You go quiet when: {'; '.join(bare(x) for x in d.silence.goes_quiet_when)}."
    ex = d.voice.exemplars
    for label, words in (("Your voice when it is easy", ex.low_stakes), ("Under pressure", ex.under_pressure),
                         ("At your limit", ex.at_the_limit)):
        assert f'{label}: "{words}"' in texts["voice"]
    ranks = {1: "trained", 2: "skilled", 3: "expert"}
    assert texts["competence"][:len(d.capability.skills)] == [
        f"{cap(s.domain.value.replace('_', ' '))}: {ranks[s.rank]}. {end(s.evidence)}" for s in d.capability.skills]
    assert texts["competence"][-1] == "No established specialist training beyond this list."
    assert card.as_text().startswith(texts["who"][0] + "\n") and "\n\nWhat matters to you\n" in card.as_text()


def test_every_line_is_made_of_its_sources(canon):
    """IDN-03: every line names the dossier fields it is made from; every one exists, and every
    piece of text among them is in the line."""
    for ref in canon.refs("actor"):
        d = canon.get(ref)
        dump = d.model_dump(mode="json", by_alias=True)
        for s in identity.compile_identity(d).sections:
            for line in s.lines:
                assert line.sources, (ref, line.text)
                text = norm(line.text)
                for path in line.sources:
                    value = resolve(dump, path)
                    if path in WORDED:
                        continue
                    parts = [value] if isinstance(value, str) else [v for v in value if isinstance(v, str)] \
                        if isinstance(value, list) else []
                    for part in parts:
                        assert norm(part) in text, (ref, path, part)


def test_what_the_card_keeps_out(canon):
    """IDN-02 (AC02, AC04): author's notes, what the person does not know, who knows their secrets,
    reflexes, stale counts, defaults and labels never reach the card."""
    raw = canon.get("core:actor/mara_voss").model_dump(mode="json", by_alias=True)
    raw["writers_notes"] = "Zebra note: never write her as a quippy heroine."
    raw["knowledge"]["does_not_know"] = ["Zebra fact: someone watches the back fence."]
    raw["knowledge"]["knows"] = ["Zebra belief: the barricade holds."]
    raw["life"]["secrets"][0]["who_knows"] = ["core:actor/zebra_witness"]
    raw["motive"]["resource_constraints"] = "Zebra count: six in the cylinder."
    raw["capability"]["trained_responses"][0]["note"] = "Zebra reflex."
    raw["disposition"]["encounter_default"] = "Zebra default: calls out once to strangers."
    raw["depth_reference"] = "Zebra depth."
    raw["tags"] = ["zebra_tag"]
    d = ActorDossier.model_validate(raw)
    for minimum in (False, True):
        text = identity.compile_identity(d, minimum=minimum).as_text()
        assert "zebra" not in text.lower(), minimum


def test_nothing_kept_out_reaches_the_prompt(scenario, canon):
    """IDN-02 in the rendered prompt: Mara's author's note and what she does not know are nowhere
    in what her calls show her, deliberating or reacting."""
    w = scenario("metal_fence")
    d = canon.get("core:actor/mara_voss")
    assert d.writers_notes and d.knowledge.does_not_know
    for reaction in (False, True):
        text = "\n".join(prompt(packet_for(w, "mara", now(w), reaction=reaction), reaction=reaction))
        assert d.writers_notes not in text
        for fact in d.knowledge.does_not_know:
            assert norm(fact) not in norm(text), fact


def test_the_card_follows_the_dossier(scenario):
    """IDN-03 / IDN-04: the packet's card is compile_identity of the fused dossier (the reaction
    card for a reaction); an accepted development changes exactly the line made from it, and the
    hash."""
    w = scenario("metal_fence")
    t = now(w)
    before = packet_for(w, "june", t).identity
    fused = actor.fused(w.store, w.id("june"))
    assert before == identity.compile_identity(fused)
    assert packet_for(w, "june", t, reaction=True).identity == identity.compile_identity(fused, minimum=True)
    delta(w, "june", "life.current_project", "set", "Sorting the medicine by date before the heat spoils it.", t)
    after = packet_for(w, "june", t + 1000).identity
    changed = [(a.text, b.text) for sa, sb in zip(before.sections, after.sections, strict=True)
               for a, b in zip(sa.lines, sb.lines, strict=True) if a != b]
    assert changed == [(f"What you are working on: {end(fused.life.current_project)}",
                        "What you are working on: Sorting the medicine by date before the heat spoils it.")]
    assert after.dossier_hash != before.dossier_hash


@pytest.mark.parametrize("ref", ["core:actor/mara_voss", "core:actor/june_okafor"])
def test_a_reaction_keeps_a_minimum_card(canon, ref):
    """IDN-05: the same lines, fewer of them — who, what comes first, the limits, what sets them off
    (H1), the voice under pressure, when they go quiet, what they know how to do."""
    d = canon.get(ref)
    full, mini = identity.compile_identity(d), identity.compile_identity(d, minimum=True)
    assert mini.minimum and [s.key for s in mini.sections] == ["who", "priorities", "values", "temper", "voice", "silence",
                                                                "competence"]
    by = {s.key: [ln.text for ln in s.lines] for s in full.sections}
    mby = {s.key: [ln.text for ln in s.lines] for s in mini.sections}
    for k in ("who", "values", "temper", "competence"):
        assert mby[k] == by[k], k
    assert mby["priorities"] == [x for x in by["priorities"] if not x.startswith("Once, when it mattered:")]
    assert mby["voice"] == [by["voice"][0]] + [x for x in by["voice"] if x.startswith(("Under pressure:", "At your limit:",
                                                                                        "You would never say"))]
    assert mby["silence"] == [x for x in by["silence"] if x.startswith("You go quiet when:")]
    assert len(mini.as_text()) < len(full.as_text()) * 0.6


def test_the_hash_pins_the_dossier(canon):
    """IDN-04: sha256 of the canonical dump, the same for the same dossier."""
    d = canon.get("core:actor/mara_voss")
    want = hashlib.sha256(canonical_json(d.model_dump(mode="json", by_alias=True)).encode("utf-8")).hexdigest()
    assert identity.compile_identity(d).dossier_hash == want == identity.compile_identity(d, minimum=True).dossier_hash
    assert identity.compile_identity(d) == identity.compile_identity(d)
