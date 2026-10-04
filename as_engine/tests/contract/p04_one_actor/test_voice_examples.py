"""Character examples as history (D-116). Rules EXAMPLE-01..04 (contracts/dossier.py VoiceExample;
mind/packet.py choose_examples and the budget; prompts/actor_cognition.user.j2, say_my_way.user.j2,
willis_roast.user.j2; service/death.py willis_examples).

The owner: "Good examples, I'll provide more later, for Willis and Addison. I have plenty in other places.
We should have a subsystem that gives character examples as history, or something."
A person's own moments — what was going on, what was said to them, what they said — go in front of the
model as things they already said: how they sound, never lines to repeat, and only as many as fit.
"""

from __future__ import annotations

import copy
import json
import shutil

import pytest
from pydantic import ValidationError

from as_engine.contracts.calls import RoastFacts, SayMyWayContext, WillisRoastContext
from as_engine.contracts.common import LOD, CallClass
from as_engine.contracts.dossier import Voice, VoiceExample
from as_engine.contracts.settings import PacketRules, RulesConfig
from as_engine.mind import perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.mind.packet import build_packet, choose_examples, estimate_tokens
from as_engine.prompts.render import render
from as_engine.service import death
from as_engine.testing.scenario import load_scenario

pytestmark = pytest.mark.phase(4)

HEADING = "Moments from before, in your own words (how you sound; never lines to repeat):"

EXAMPLES = [
    {"situation": "A trader weighs her antibiotics and names a price.", "by": "the trader",
     "said_to_them": "Two cans of beans. Take it or leave it.", "they_say": "Leave it, then. Somebody's kid needs these more than you need my beans."},
    {"situation": "Someone grabs her arm in the dark.", "they_say": "Let go. Now.", "pressure": "pressure"},
    {"situation": "A man she trusted points a gun at her.", "by": "Dale", "said_to_them": "Don't make me.",
     "they_say": "You already did.", "pressure": "limit"},
]

ROOM = {
    "schema": "as.scenario.v1", "name": "counter", "seed": 4, "start": {"day": 200, "time": "11:00"},
    "places": [{"id": "shop", "name": "Pharmacy", "light": 3, "width_m": 8, "depth_m": 6}],
    "bodies": [
        {"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "shop", "x": 6, "y": 3},
        {"id": "june", "dossier": "core:actor/june_okafor", "place": "shop", "x": 2, "y": 3},
        {"id": "mara", "dossier": "core:actor/mara_voss", "place": "shop", "x": 3, "y": 4},
    ],
}


def ex(situation="Something happens here.", they_say="Fine.", pressure="easy", **kw):
    return VoiceExample(situation=situation, they_say=they_say, pressure=pressure, **kw)


def cost(e):
    return estimate_tokens(e.situation + e.by + e.said_to_them + e.they_say) + 8


def give_examples(w, who, examples):
    """Writes examples into a person's baseline dossier, as a pack record with them would."""
    actor = w.id(who)
    (did, base) = w.store.query_one("SELECT d.dossier_id, d.baseline_json FROM actors a JOIN dossiers d "
                                    "ON d.dossier_id = a.dossier_id WHERE a.actor_id = ?", (actor,))
    d = json.loads(base)
    d["voice"]["examples"] = examples
    w.store.conn.execute("UPDATE dossiers SET baseline_json = ? WHERE dossier_id = ?", (json.dumps(d), did))
    return actor


def world(fixture_packs, core_pack_dir, rules=None):
    return load_scenario(copy.deepcopy(ROOM), packs_root=fixture_packs, core_pack_dir=core_pack_dir, rules=rules)


def packet(w, actor, *, reaction=False, lod=LOD.HOT):
    t = w.store.query_one("SELECT now_ms FROM world_clock")[0]
    with w.store.transaction() as tx:
        perception.compile_scene(tx, actor, t, 0)
        aff = enumerate_affordances(tx, actor, w.canon.all("affordance"), t, 0)
        return build_packet(tx, actor, lod, aff, 0, t, reaction=reaction)


# ------------------------------------------------------------------------- EXAMPLE-01 the record


def test_an_example_is_a_moment_in_their_own_words():
    e = VoiceExample.model_validate(EXAMPLES[2])
    assert (e.by, e.pressure) == ("Dale", "limit")
    assert VoiceExample.model_validate(EXAMPLES[1]).said_to_them == "" and VoiceExample(
        situation="Alone, at the window.", they_say="Come on, come on.").pressure == "easy"
    for bad in ({"situation": "Hm.", "they_say": "Fine."}, {"situation": "A long wait.", "they_say": ""},
                {"situation": "A long wait.", "they_say": "Fine.", "pressure": "panic"}):
        with pytest.raises(ValidationError):
            VoiceExample.model_validate(bad)
    v = Voice.model_validate({"capsule": "Short, dry and to the point, always.", "speech_tendencies": ["a", "b"],
                              "exemplars": {"low_stakes": "Fine by me.", "under_pressure": "Move it.", "at_the_limit": "No. Never."},
                              "would_never_say": ["x", "y", "z"], "profanity": "rare"})
    assert v.examples == [], "a voice without examples is still a voice"


# ------------------------------------------------------------------------- EXAMPLE-02 which ones


def test_a_deliberation_takes_them_in_order_until_the_room_is_gone():
    a = ex("One: " + "a" * 200, "Said one.")
    b = ex("Two: " + "b" * 200, "Said two.", "pressure")
    big = ex("Three: " + "c" * 390, "Said three. " + "d" * 700)
    small = ex("Four.", "Said four.")
    rules = PacketRules(voice_example_tokens=cost(a) + cost(b) + cost(small))
    assert choose_examples([a, b, big, small], reaction=False, rules=rules) == [a, b], \
        "the first that does not fit ends the list: the same person shows the same examples every call"
    assert choose_examples([a, b, small], reaction=False, rules=rules) == [a, b, small]
    assert choose_examples([a, b], reaction=False, rules=PacketRules(voice_example_tokens=cost(a) + cost(b) - 1)) == [a]
    assert choose_examples([], reaction=False, rules=rules) == [] and choose_examples(None, reaction=False, rules=rules) == []


def test_a_split_second_takes_only_the_hard_ones():
    easy, p1, lim, p2 = ex("Easy.", "Sure."), ex("Grabbed.", "Off!", "pressure"), ex("Cornered.", "No.", "limit"), \
        ex("Shoved.", "Hey!", "pressure")
    rules = PacketRules()
    assert rules.voice_examples_reaction == 2 and rules.voice_example_tokens == 600
    assert choose_examples([easy, p1, lim, p2], reaction=True, rules=rules) == [p1, lim]
    assert choose_examples([easy, p2], reaction=True, rules=PacketRules(voice_examples_reaction=3)) == [p2]
    assert choose_examples([easy], reaction=True, rules=rules) == []


# ------------------------------------------------------------------------- EXAMPLE-02/03 the packet and the prompt


def test_she_hears_how_she_sounds_right_after_who_she_is(fixture_packs, core_pack_dir):
    w = world(fixture_packs, core_pack_dir)
    try:
        june = give_examples(w, "june", EXAMPLES)
        p = packet(w, june)
        assert p.voice_examples == [VoiceExample.model_validate(e) for e in EXAMPLES]
        user = render(CallClass.ACTOR_COGNITION, p=p)[1].content
        block = (f"\n\n{HEADING}\n"
                 "- A trader weighs her antibiotics and names a price.\n"
                 '  the trader: "Two cans of beans. Take it or leave it."\n'
                 '''  You: "Leave it, then. Somebody's kid needs these more than you need my beans."\n'''
                 "- Someone grabs her arm in the dark.\n"
                 '  You: "Let go. Now."\n'
                 "- A man she trusted points a gun at her.\n"
                 '  Dale: "Don\'t make me."\n'
                 '  You: "You already did."\n')
        assert block in user, user[:3000]
        assert user.index(p.identity.as_text()) < user.index(HEADING) < user.index("What matters to you now"), \
            "stable per person, after the card: a cached prompt stays cached (PROMPT-01)"
        r = packet(w, june, reaction=True)
        assert [e.they_say for e in r.voice_examples] == ["Let go. Now.", "You already did."]
        assert HEADING in render(CallClass.ACTOR_REACTION, p=r)[1].content
        mara = packet(w, w.id("mara"))
        assert mara.voice_examples == [] and HEADING not in render(CallClass.ACTOR_COGNITION, p=mara)[1].content
    finally:
        w.store.close()


def test_how_someone_sounds_gives_way_before_what_they_remember(fixture_packs, core_pack_dir):
    w = world(fixture_packs, core_pack_dir)
    try:
        full = packet(w, give_examples(w, "june", EXAMPLES))
        msgs = render(CallClass.ACTOR_COGNITION, p=full)
        need = estimate_tokens(msgs[0].content + "\n" + msgs[1].content)
    finally:
        w.store.close()
    tight = RulesConfig(packet={"token_budget": {"hot": need - 1, "warm": 4000, "reaction": 3000}})
    w = world(fixture_packs, core_pack_dir, rules=tight)
    try:
        p = packet(w, give_examples(w, "june", EXAMPLES))
        assert [e.they_say for e in p.voice_examples] == [EXAMPLES[0]["they_say"], EXAMPLES[1]["they_say"]]
        assert p.omitted == [f"example: {EXAMPLES[2]['they_say']}"], "the last example goes first, and nothing else"
        assert p.memories == full.memories and p.beliefs == full.beliefs
    finally:
        w.store.close()


# ------------------------------------------------------------------------- the player's own words, opted in


def test_say_my_way_hears_the_character_s_own_moments(fixture_packs, core_pack_dir):
    """Only when the player opts in (pc_voice 'my_way', D-113) does anything put words in the PC's mouth;
    then it should sound like them."""
    w = world(fixture_packs, core_pack_dir)
    try:
        pc = give_examples(w, "pc", EXAMPLES[:2])
        ctx = SayMyWayContext(packet=packet(w, pc, lod=LOD.WARM), seed_text="tell her we should go")
        user = render(CallClass.SAY_MY_WAY, ctx=ctx)[1].content
        assert ("Moments from before, in their own words (how they sound; never lines to repeat):\n"
                "- A trader weighs her antibiotics and names a price.\n"
                '  the trader: "Two cans of beans. Take it or leave it."\n'
                '''  They said: "Leave it, then. Somebody's kid needs these more than you need my beans."\n'''
                "- Someone grabs her arm in the dark.\n"
                '  They said: "Let go. Now."\n') in user
        assert user.index("Moments from before") < user.index("The idea to get across: tell her we should go")
    finally:
        w.store.close()


# ------------------------------------------------------------------------- EXAMPLE-04 Willis


def test_willis_sounds_like_himself_in_the_frozen_moment(tmp_path, core_pack_dir):
    repo_packs = core_pack_dir.parent
    rules = PacketRules()
    assert death.willis_examples(None, rules) == [] and death.willis_examples(str(tmp_path / "nowhere"), rules) == []
    assert death.willis_examples(str(repo_packs), rules) == [], "the shipped Willis has no examples yet"
    shutil.copytree(repo_packs / "cheat_admin", tmp_path / "cheat_admin")
    card = tmp_path / "cheat_admin" / "pcs" / "willis.yaml"
    text = card.read_text(encoding="utf-8")
    assert text.count("\n  profanity:") == 1
    lines = ("  examples:\n"
             "    - situation: Someone asks him to save the world.\n"
             "      by: a woman with a rifle\n"
             "      said_to_them: You could stop all of this.\n"
             "      they_say: Could I? Huh. Anyway, have you tried the coffee here? Terrible. I love it.\n"
             "    - situation: The street is on fire and he is pouring a coffee.\n"
             "      they_say: Thirty seconds is a lot of seconds, actually.\n"
             "      pressure: pressure\n")
    card.write_text(text.replace("\n  profanity:", "\n" + lines + "  profanity:", 1), encoding="utf-8")
    got = death.willis_examples(str(tmp_path), rules)
    assert [e.they_say for e in got] == ["Could I? Huh. Anyway, have you tried the coffee here? Terrible. I love it.",
                                         "Thirty seconds is a lot of seconds, actually."]
    facts = RoastFacts(pc_name="Owen Marsh", lived="2 days", turns=12)
    user = render(CallClass.WILLIS_ROAST, ctx=WillisRoastContext(facts=facts, examples=got))[1].content
    assert user.startswith("How you have sounded before (never lines to repeat):\n- Someone asks him to save the world.\n"
                           '  a woman with a rifle: "You could stop all of this."\n')
    assert "The one frozen in front of you: Owen Marsh." in user
    plain = render(CallClass.WILLIS_ROAST, ctx=WillisRoastContext(facts=facts))[1].content
    assert plain.startswith("The one frozen in front of you: Owen Marsh."), "no examples, no heading"
