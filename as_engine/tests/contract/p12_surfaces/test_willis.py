"""Willis, the code box and the Wild Card (P12). Rules CHEAT-10, CHEAT-12..15, TEMPER-10, REL-06,
WORLD-07; DECISIONS D-79, D-102 (service/game_service.py on_code_enter, on_pcs_list, on_run_new;
service/runs.py create_run; cheats/commands.py start_life, /wonder, take_wonder, the persona;
physical/bodies.py the reality exception; action/effects.py the wonders and the endless container;
mind/temper.py TEMPER-10; mind/mind.py REL-06; world/worldgen/opening.py place_wild_card;
world/worldmove.py day step 4b).

The owner's own cheat entity (docs/as/sources/WILLIS.md, and the owner's words in his dossier's
depth_reference): playable only in a life the code opened; nothing can hurt him and every fight with
him is unwinnable; he can do anything, and kill anyone; friendly at best, never a friend; unbothered by
insults and bullets, enraged by worship, by being treated as a genie by someone who has seen what he
can do, and by ingratitude for a gift he gave. In a normal world the Wild Card house rule lets him
walk about as a person of his own, never where you left him.
"""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path

import pytest
from protocol_kit import actions, only, send, wait_for
from slice_kit import pick, play

from as_engine.action import effects
from as_engine.action.intent import Intent
from as_engine.cheats import commands as cheats
from as_engine.contracts.common import LOD, CallClass, Verb
from as_engine.contracts.events import Event, EventType
from as_engine.contracts.settings import EngineConfig, RunSettings
from as_engine.mind import mind as mind_mod
from as_engine.mind import perception, temper
from as_engine.mind.affordance import BoundAffordance, enumerate_affordances
from as_engine.physical import bodies, objects
from as_engine.physical.bodies import WoundSpec, apply_harm
from as_engine.service import runs
from as_engine.testing.fake_lm import FakeTransport

pytestmark = pytest.mark.phase(12)

REPO_PACKS = Path(__file__).resolve().parents[4] / "as_content" / "packs"
WILLIS = "cheat_admin:pc/willis"
SMALL = {"world_detail": "gotta_go_to_work_soon", "seed": 7, "era": "established", "difficulty": "normal"}


def cheat(s, line):
    if s.store.meta("cheat_active") != "1":
        cheats.activate(s)
    cmd = cheats.parse(line)
    assert isinstance(cmd, cheats.CheatCommand), cmd
    return asyncio.run(cheats.execute(s, cmd))


def excepted(s, who):
    """Puts ``who`` in the reality exception the way a life as Willis does (D-102)."""
    with s.store.transaction() as tx:
        return bodies.grant_exception(tx, who, 0, 0, origin="cheat")


def made(tmp_path_factory, name, pc_ref, **settings):
    root = tmp_path_factory.mktemp(name)
    c = EngineConfig(runs_dir=str(root / "runs"), content_dir=str(REPO_PACKS))
    s = asyncio.run(runs.create_run(c, pc_ref, RunSettings(**(SMALL | settings)), FakeTransport()))
    run_id = s.run_id
    s.store.close()
    return root / "runs", run_id


@pytest.fixture(scope="module")
def willis_world(tmp_path_factory):
    """A life as Willis: the smallest world, seed 7, his own pack in the run."""
    return made(tmp_path_factory, "willis_world", WILLIS, pack_ids=["core", "cheat_admin"])


@pytest.fixture(scope="module")
def wild_world(tmp_path_factory):
    """Owen Marsh in a normal world with the Wild Card house rule on."""
    return made(tmp_path_factory, "wild_world", "core:pc/owen_marsh", wild_card=True)


def opened(world, tmp_path, fake):
    src, run_id = world
    shutil.copytree(src, tmp_path / "runs")
    c = EngineConfig(runs_dir=str(tmp_path / "runs"), content_dir=str(REPO_PACKS))
    return runs.load_run(c, run_id, fake)


@pytest.fixture
def willis(willis_world, tmp_path, fake):
    s = opened(willis_world, tmp_path, fake)
    try:
        yield s
    finally:
        s.store.close()


@pytest.fixture
def wild(wild_world, tmp_path, fake):
    s = opened(wild_world, tmp_path, fake)
    try:
        yield s
    finally:
        s.store.close()


# =========================================================================== the code box
async def test_the_code_box_says_nothing_and_opens_the_list(svc, make_run):
    """CHEAT-12: "Enter a code" answers only whether the code was taken; the word lets the New Life
    list show the cheat_ packs' characters for as long as the game runs, and in an open life it is
    the word typed anywhere else."""
    before = only(await send(svc, "pcs_list"), "pcs")["cards"]
    assert before and not [c for c in before if c["ref"].startswith("cheat_")]
    for wrong in ("1234", "12508", "25080"):
        assert only(await send(svc, "code_enter", code=wrong), "code_result") == {"accepted": False}
    assert only(await send(svc, "code_enter", code=""), "error")["code"] == "bad_request"
    r = await send(svc, "code_enter", code="2508")
    assert actions(r) == ["code_result"] and only(r, "code_result") == {"accepted": True}
    after = only(await send(svc, "pcs_list"), "pcs")["cards"]
    (card,) = [c for c in after if c["ref"].startswith("cheat_")]
    assert (card["ref"], card["display_name"], card["source"]) == (WILLIS, "Willis", "pack")
    assert [c for c in after if not c["ref"].startswith("cheat_")] == before
    await send(svc, "run_load", run_id=make_run())
    r = await send(svc, "code_enter", code="2508")
    assert actions(r) == ["code_result", "cheat_activated", "story"]
    store = svc.session.store
    assert (store.meta("cheat_active"), store.meta("sandbox")) == ("1", "0"), "the word alone changes nothing"


async def test_his_life_is_asked_for_with_his_pack_and_only_after_the_code(svc, monkeypatch):
    """on_run_new: a cheat_ pack's character is a character nobody has heard of until the code was
    taken; after it, the run is asked for with that pack beside core."""
    asked = []

    async def fake_create(config, pc_ref, settings, transport, progress=None, world_id=None):
        asked.append((pc_ref, list(settings.pack_ids)))
        raise runs.RunError("not_found", f"There is no character called {pc_ref}.")
    monkeypatch.setattr(runs, "create_run", fake_create)
    await send(svc, "run_new", pc_ref=WILLIS, settings=SMALL)
    await wait_for(lambda: svc.worldgen_task is None)
    await send(svc, "code_enter", code="2508")
    await send(svc, "run_new", pc_ref=WILLIS, settings=SMALL)
    await wait_for(lambda: svc.worldgen_task is None)
    assert asked == [(WILLIS, ["core"]), (WILLIS, ["core", "cheat_admin"])]
    errors = [m["data"]["code"] for m in svc.pushed if m["action"] == "error"]
    assert errors == ["not_found", "not_found"]


# =========================================================================== a life as Willis
def test_a_life_as_willis_starts_with_the_console_open(willis):
    """CHEAT-12, CHEAT-13: his pack is in the run, but only he came out of it (CHEAT-10); the life is
    a Sandbox from the first moment, the console is open, and he is in the reality exception."""
    s = willis
    st = s.store
    assert (st.meta("cheat_active"), st.meta("sandbox")) == ("1", "1")
    assert st.query("SELECT 1 FROM events WHERE type = 'CHEAT_ACTIVATED' AND origin = 'cheat'")
    pc = s.pc_id
    b = st.query_one("SELECT origin, content_ref FROM bodies WHERE body_id = ?", (pc,))
    assert tuple(b) == ("cheat", WILLIS)
    assert st.query_one("SELECT source FROM dossiers WHERE actor_id = ?", (pc,))[0] == "cheat"
    assert st.query_one("SELECT quarantine FROM actors WHERE actor_id = ?", (pc,))[0] == 1
    assert json.loads(st.meta("reality_exception")) == [pc]
    others = st.query("SELECT body_id FROM bodies WHERE content_ref LIKE 'cheat\\_%' ESCAPE '\\' AND body_id != ?", (pc,))
    assert others == [], "Fredrick and the rest stay in the pack until /spawn (CHEAT-10)"
    (log,) = st.query("SELECT command, outcome FROM cheat_log")
    assert tuple(log) == ("start", "began a life as Willis")
    worn = sorted(r[0] for r in st.query("SELECT def_ref FROM items WHERE holder_body = ? AND holder_slot = 'worn'", (pc,)))
    assert "cheat_admin:item/top_hat" in worn and "cheat_admin:item/tuxedo_jacket" in worn
    assert st.query_one("SELECT def_ref FROM items WHERE holder_body = ? AND holder_slot = 'hand_r'", (pc,))[0] == \
        "cheat_admin:item/coffee_cup"
    assert json.loads(st.meta("fickle")) == [pc]
    knowers = st.query("SELECT holder_id FROM acquaintance WHERE subject_id = ?", (pc,))
    assert knowers, "he starts among people who know him"


# =========================================================================== the reality exception
def test_reality_does_not_argue_with_him(night):
    """CHEAT-13: no wound lands, no need grows, no strain takes hold, no dirt sticks, the cold does
    not reach him and a grip holds nothing — and the man beside him keeps every rule he had."""
    w, s = night
    mara, june = w.id("mara"), w.id("june")
    ev = excepted(s, mara)
    assert ev is not None and ev.type.value == "SETTINGS_CHANGE" and excepted(s, mara) is None
    with w.store.transaction() as tx:
        assert bodies.excepted(tx, mara) and not bodies.excepted(tx, june)
        cause = tx.query_one("SELECT event_id FROM events ORDER BY seq LIMIT 1")[0]
        assert apply_harm(tx, mara, WoundSpec("chest", "gunshot", "severe", 2), 0, cause, 0, s.rng) == []
        assert bodies.expose(tx, s.rng, mara, "wet", "bite", 0, cause, 0) is None
        assert bodies.soil(tx, mara, grime=3, blood=2, source="test", at=0, cause_event_id=None, turn_index=0) is None
        assert bodies.cold_need(tx, mara, 0) == 0
        before = tuple(tx.query_one("SELECT thirst_stage, hunger_stage, fatigue_stage FROM needs WHERE body_id = ?", (mara,)))
        later = tx.query_one("SELECT now_ms FROM world_clock")[0] + 6 * 86_400_000
        bodies.progress(tx, mara, later, 0, s.rng)
        assert tuple(tx.query_one("SELECT thirst_stage, hunger_stage, fatigue_stage FROM needs WHERE body_id = ?",
                                  (mara,))) == before
        assert tx.query_one("SELECT alive, progressed_at FROM bodies WHERE body_id = ?", (mara,))[1] == later
        bodies.grip_event(tx, june, mara, 0, None, 0)
        assert bodies.capacity(tx, mara).mobile, "the grip happened; it has no say over him"
        assert apply_harm(tx, june, WoundSpec("arm_l", "cut", "minor", 0), 0, cause, 0, s.rng), "June's rules are her own"
        bodies.progress(tx, june, later, 0, s.rng)
        assert tx.query_one("SELECT thirst_stage FROM needs WHERE body_id = ?", (june,))[0] > 0


def test_the_console_cannot_kill_him(night):
    w, s = night
    excepted(s, s.pc_id)
    r = cheat(s, "/kill me")
    assert not r.ok and r.persona_line == "Reality lost that argument a long time ago, Boss."
    assert w.store.query_one("SELECT alive FROM bodies WHERE body_id = ?", (s.pc_id,))[0] == 1


# =========================================================================== wonders
def test_a_wonder_is_seen_remembered_and_told(night, fake):
    """CHEAT-14: /wonder is his alone; it happens as the next turn opens, as his own act — the people
    who see him see it, and the story tells it; nothing else about the world changes by it."""
    w, s = night
    no = cheat(s, '/wonder "walks through the wall"')
    assert not no.ok and no.persona_line == "You're not him, Boss."
    excepted(s, s.pc_id)
    assert not cheat(s, '/wonder "I walk through the wall"').ok, "said the way they would see it"
    r = cheat(s, '/wonder "walks straight through the wall"')
    assert r.ok and s.store.meta("pending_wonder") == "walks straight through the wall"
    assert not cheat(s, '/wonder "does it again"').ok, "one at a time"
    assert not w.store.query("SELECT 1 FROM events WHERE type = 'ACTION_START' AND payload LIKE '%wonder%'")
    fake.script(CallClass.INTAKE, lambda q: {"choice": pick(w, q, "observe_area"), "none_reason": None, "manner": "",
                                            "remainder": None, "clarify": None})
    assert play(s, "do", "I look around.").ok
    (ev,) = w.store.query("SELECT actor_id, origin, payload, turn_index FROM events WHERE type = 'ACTION_START' "
                          "AND json_extract(payload, '$.def_id') = 'wonder'")
    p = json.loads(ev[2])
    assert (ev[0], ev[1], ev[3]) == (s.pc_id, "cheat", 1)
    assert (p["seen"], p["visible"]) == ("walks straight through the wall", True)
    seen = [r[0] for r in w.store.query("SELECT text FROM percept_log WHERE holder_id != ? AND turn_index = 1", (s.pc_id,))]
    assert [t for t in seen if t.endswith("walks straight through the wall.")], seen
    lines = [ln.text for ln in fake.calls(CallClass.NARRATION)[-1].context.lines]
    assert "Owen walks straight through the wall." in lines
    assert s.store.meta("pending_wonder") in (None, "")


# =========================================================================== the voice and the companion
def test_the_voice_in_his_head(night, fake):
    """D-79: Mr. Cheater Man stays the console voice; when the Boss is Willis, the voice knows Willis
    takes him for a demon in his head."""
    w, s = night
    cheat(s, "/give ammo_38 1")
    assert fake.calls(CallClass.CHEAT_PERSONA)[-1].context.willis is False
    excepted(s, s.pc_id)
    cheat(s, "/give ammo_38 1")
    req = fake.calls(CallClass.CHEAT_PERSONA)[-1]
    assert req.context.willis is True
    assert "demon" in " ".join(m.content for m in req.messages)


def test_fredrick_blends_in_when_willis_does(night):
    """D-79: spawned beside Willis, Fredrick is one of the people who know Willis — each of them knows
    him too and feels about him as they feel about Willis; beside anyone else he is a stranger."""
    w, s = night
    assert cheat(s, "/spawn fredrick").ok
    fred0 = w.store.query_one("SELECT body_id FROM bodies WHERE content_ref = 'cheat_admin:actor/fredrick'")[0]
    assert not w.store.query("SELECT 1 FROM acquaintance WHERE subject_id = ?", (fred0,)), "a stranger"
    excepted(s, s.pc_id)
    knowers = [x[0] for x in w.store.query("SELECT holder_id FROM acquaintance WHERE subject_id = ? ORDER BY holder_id",
                                           (s.pc_id,))]
    assert knowers
    r = cheat(s, "/spawn fredrick ally")
    assert r.ok
    fred = w.store.query_one("SELECT body_id FROM bodies WHERE content_ref = 'cheat_admin:actor/fredrick' AND body_id != ?",
                             (fred0,))[0]
    name = w.store.query_one("SELECT display_name FROM actors WHERE actor_id = ?", (fred,))[0]
    axes = "trust, fear, respect, affection, resentment, obligation"
    for k in knowers:
        row = w.store.query_one("SELECT known_name FROM acquaintance WHERE holder_id = ? AND subject_id = ?", (k, fred))
        assert row is not None and row[0] == name, k
        toward_pc = w.store.query_one(f"SELECT {axes} FROM relationships WHERE from_id = ? AND to_id = ?", (k, s.pc_id))
        toward_fred = w.store.query_one(f"SELECT {axes} FROM relationships WHERE from_id = ? AND to_id = ?", (k, fred))
        assert (None if toward_pc is None else tuple(toward_pc)) == (None if toward_fred is None else tuple(toward_fred)), k
    for (g,) in w.store.query("SELECT group_id FROM group_members WHERE actor_id = ? AND status = 'member'", (s.pc_id,)):
        assert w.store.query_one("SELECT status FROM group_members WHERE group_id = ? AND actor_id = ?", (g, fred))[0] == "member"


def test_every_fight_with_him_is_unwinnable(night, monkeypatch):
    """CHEAT-13: a blow that would kill anyone else may be his whim to seem to die — a corpse that looks
    like him lies where he stood, and he is somewhere else, unhurt; nobody saw where he went."""
    w, s = night
    mara = w.id("mara")
    excepted(s, mara)
    with w.store.transaction() as tx:
        cause = tx.query_one("SELECT event_id FROM events ORDER BY seq LIMIT 1")[0]
        now = tx.query_one("SELECT now_ms FROM world_clock")[0]
        here = tx.query_one("SELECT place_id FROM positions WHERE body_id = ?", (mara,))[0]
        monkeypatch.setattr(bodies, "DECOY_CHANCE", 0.0)
        assert apply_harm(tx, mara, WoundSpec("head", "gunshot", "catastrophic", 0), now, cause, 0, s.rng) == []
        assert tx.query_one("SELECT place_id FROM positions WHERE body_id = ?", (mara,))[0] == here, "not this time"
        monkeypatch.setattr(bodies, "DECOY_CHANCE", 1.0)
        assert apply_harm(tx, mara, WoundSpec("arm_l", "cut", "minor", 0), now, cause, 0, s.rng) == []
        assert tx.query_one("SELECT place_id FROM positions WHERE body_id = ?", (mara,))[0] == here, "a scratch is no death"
        assert apply_harm(tx, mara, WoundSpec("head", "gunshot", "catastrophic", 0), now, cause, 0, s.rng) == []
        ref, origin = tx.query_one("SELECT content_ref, origin FROM bodies WHERE body_id = ?", (mara,))
        (corpse,) = tx.query("SELECT b.body_id, b.alive, q.place_id FROM bodies b JOIN positions q ON q.body_id = b.body_id "
                             "WHERE b.content_ref IS ? AND b.origin = ? AND b.body_id != ?", (ref, origin, mara))
        assert (corpse[1], corpse[2]) == (0, here), "they think they won"
        assert tx.query_one("SELECT alive FROM bodies WHERE body_id = ?", (mara,))[0] == 1
        assert tx.query_one("SELECT place_id FROM positions WHERE body_id = ?", (mara,))[0] != here
        assert not tx.query("SELECT 1 FROM wounds WHERE body_id = ?", (mara,))


# =========================================================================== his wonders, his gifts
def intent(actor, def_id, verb, target=None, item=None):
    return Intent(actor_id=actor, bound=BoundAffordance(def_id=def_id, verb=Verb(verb), label=def_id, ui_label=def_id,
                                                        target_id=target, item_id=item),
                  speech=None, manner="", goal="", private_reason="", source="model", lod=LOD.HOT)


def do(tx, s, it, effect=None):
    start = tx.query_one("SELECT event_id FROM events ORDER BY seq DESC LIMIT 1")[0]
    at = tx.query_one("SELECT now_ms FROM world_clock")[0]
    ctx = effects.EffectCtx(turn_index=0, horizon_ms=at + 60_000, start_event_id=start, wave_start_ms=at)
    return effects.EFFECTS[effect or it.bound.def_id](tx, s.rng, it, at, ctx)


def cast(st):
    willis = st.query_one("SELECT body_id FROM bodies WHERE origin = 'wildcard'")[0]
    others = [r[0] for r in st.query("SELECT a.actor_id FROM actors a JOIN bodies b ON b.body_id = a.actor_id "
                                     "WHERE b.alive = 1 AND b.kind = 'human' AND a.actor_id NOT IN (?, ?) ORDER BY a.actor_id",
                                     (willis, st.meta("pc_actor_id")))]
    return willis, others


def test_only_he_is_offered_the_wonders(wild):
    """CHEAT-13: the wonders are on his menu (requires.capability_tags) and on nobody else's."""
    s = wild
    willis, others = cast(s.store)
    with s.store.transaction() as tx:
        at, T = tx.query_one("SELECT now_ms, turn_index FROM world_clock")
        mine = enumerate_affordances(tx, willis, tx.canon.all("affordance"), at, T)
        theirs = enumerate_affordances(tx, others[0], tx.canon.all("affordance"), at, T)
    assert "wonder_vanish" in {o.def_id for o in mine.pool}
    assert "wonder_vanish" not in {o.def_id for o in theirs.pool}
    assert any(r.def_id == "wonder_vanish" and r.detail == "not something they can do" for r in theirs.rejected)


def test_nothing_stops_what_he_does(wild):
    """CHEAT-13: no check, no contest — he ends a life, hurts, or is simply somewhere else."""
    s = wild
    willis, others = cast(s.store)
    a, b = others[0], others[1]
    with s.store.transaction() as tx:
        assert do(tx, s, intent(willis, "wonder_smite", "attack", target=a)).result == "smitten"
        assert tx.query_one("SELECT alive FROM bodies WHERE body_id = ?", (a,))[0] == 0
        assert json.loads(tx.query_one("SELECT payload FROM events WHERE type = 'DEATH' ORDER BY seq DESC LIMIT 1")[0])["cause"] \
            == "wonder"
        assert do(tx, s, intent(willis, "wonder_hurt", "attack", target=b)).result == "hurt"
        w = tx.query_one("SELECT type, severity FROM wounds WHERE body_id = ?", (b,))
        assert tuple(w) == ("blunt", "severe")
        here = tx.query_one("SELECT place_id FROM positions WHERE body_id = ?", (willis,))[0]
        assert do(tx, s, intent(willis, "wonder_vanish", "move")).result == "gone"
        assert tx.query_one("SELECT place_id FROM positions WHERE body_id = ?", (willis,))[0] != here
        assert do(tx, s, intent(b, "wonder_smite", "attack", target=willis)).result == "unmoved"


def test_the_endless_plate_of_samiches(wild):
    """D-102: his gift to a fascinating group — each samich eaten from the plate brings another, a random
    one; one taken off and kept brings nothing: there is no samich mountain."""
    s = wild
    willis, others = cast(s.store)
    x = others[0]
    with s.store.transaction() as tx:
        assert do(tx, s, intent(willis, "wonder_gift", "manipulate", target=x)).result == "given"
        plate, props = tx.query_one("SELECT item_id, props FROM items WHERE def_ref = 'cheat_admin:item/plate_of_samiches'")
        props = json.loads(props)
        assert props["gift_from"] == willis and x in props["gift_to"]
        assert temper.gifted_by(tx, willis, x)

        def on_plate():
            return [tuple(r) for r in tx.query("SELECT item_id, def_ref FROM items WHERE container_id = ?", (plate,))]
        (first,) = on_plate()
        assert first[1].startswith("cheat_admin:item/samich_")
        do(tx, s, intent(x, "eat_food", "manipulate", item=first[0]), "eat")
        (second,) = on_plate()
        assert second[0] != first[0], "another appears"
        where = tx.query_one("SELECT place_id FROM positions WHERE body_id = ?", (x,))[0]
        objects.transfer(tx, second[0], objects.Holder("place", where), None, 0, x, None, 0)
        assert on_plate() == [], "taking one off makes no new one"
        do(tx, s, intent(x, "eat_food", "manipulate", item=second[0]), "eat")
        assert len(on_plate()) == 1, "eating it does"
        made = tx.query("SELECT 1 FROM items WHERE json_extract(props, '$.refills') = ?", (plate,))
        assert len(made) == 1, "never more than one at a time"


# =========================================================================== what he shrugs off, and what he does not
def speak(tx, s, speaker, holder, words):
    at, T = tx.query_one("SELECT now_ms, turn_index FROM world_clock")
    ev = tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", at=at, turn_index=T, actor_id=speaker,
                               payload={"speaker_id": speaker, "words": words}))
    perception.grant(tx, holder, event_id=ev.event_id, channel="speech", fidelity="exact", text=f'"{words}"',
                     source_id=speaker, at=at, turn_index=T, detail={"addressed_to_me": True, "words": words})
    return temper.take_in(tx, s.rng, holder, T, at)


def shows(tx, holder, witness, def_id="wonder_vanish"):
    at, T = tx.query_one("SELECT now_ms, turn_index FROM world_clock")
    ev = tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=at, turn_index=T, actor_id=holder,
                               payload={"actor_id": holder, "def_id": def_id, "visible": True, "seen": "is suddenly not there"}))
    perception.grant(tx, witness, event_id=ev.event_id, channel="visual", fidelity="exact", text="He is suddenly not there.",
                     source_id=holder, at=at, turn_index=T)


def test_insults_and_blows_are_nothing_to_him(wild):
    """TEMPER-10: blatant disrespect gives him no heat at all."""
    s = wild
    willis, others = cast(s.store)
    with s.store.transaction() as tx:
        assert speak(tx, s, others[0], willis, "You useless freak, fuck off") is None
        assert not tx.query("SELECT 1 FROM tempers WHERE holder_id = ?", (willis,))


def test_worship_hurts(wild):
    """TEMPER-10: worship sends him past his breaking point at once — no holding it in — and his outlet
    is wrath."""
    s = wild
    willis, others = cast(s.store)
    with s.store.transaction() as tx:
        out = speak(tx, s, others[0], willis, "We worship you, my lord, all hail")
        assert out is not None and (out.toward_id, out.outlet) == (others[0], "wrath")


def test_one_stray_wish_is_let_pass_with_a_correction(wild):
    """TEMPER-10: someone who has seen what he can do and asks him for a wonder is let off once, with a
    serious, harmless correction; the second time he hurts them. Someone who has seen nothing is only
    asking."""
    from as_engine.mind import _impl_packet
    s = wild
    willis, others = cast(s.store)
    x, y = others[0], others[1]
    with s.store.transaction() as tx:
        at = tx.query_one("SELECT now_ms FROM world_clock")[0]
        assert speak(tx, s, y, willis, "Can you make us some food with your magic?") is None
        assert not tx.query("SELECT 1 FROM tempers WHERE holder_id = ?", (willis,)), "he has seen nothing"
        shows(tx, willis, x)
        assert speak(tx, s, x, willis, "Can you make us some food with your magic?") is None
        assert "genie" in _impl_packet._temper_feeling(tx, willis, x, at)
        out = speak(tx, s, x, willis, "Please, grant me a wish, make us rich")
        assert out is not None and (out.toward_id, out.outlet) == (x, "wrath")


def test_ingratitude_for_his_gift_is_not_a_joke(wild):
    """TEMPER-10: the same disrespect he shrugs off from anyone else, from someone he gave a gift, is
    ingratitude — and his wrath on them is the one that kills (turn.cognition builds wonder_smite)."""
    s = wild
    willis, others = cast(s.store)
    x = others[0]
    with s.store.transaction() as tx:
        do(tx, s, intent(willis, "wonder_gift", "manipulate", target=x))
        out = speak(tx, s, x, willis, "Shut up, you worthless freak")
        assert out is not None and (out.toward_id, out.outlet) == (x, "wrath")
        assert temper.gifted_by(tx, willis, x)
        kind = tx.query_one("SELECT json_extract(payload, '$.kind') FROM events WHERE type = 'TEMPER_CHANGE' AND actor_id = ? "
                            "AND json_extract(payload, '$.kind') != 'vented' ORDER BY seq DESC LIMIT 1", (willis,))[0]
        assert kind == "ingratitude"


# =========================================================================== the Wild Card
def test_the_wild_card_walks_a_normal_world(wild):
    """CHEAT-15: with the house rule on, Willis is in the world as a person of his own — origin
    'wildcard', out of the world's maths, in the reality exception, somewhere away from you — and
    the life is no Sandbox and no console is open."""
    s = wild
    st = s.store
    (row,) = st.query("SELECT body_id, content_ref, alive FROM bodies WHERE origin = 'wildcard'")
    willis = row[0]
    assert (row[1], row[2]) == (WILLIS, 1)
    assert st.query_one("SELECT source FROM dossiers WHERE actor_id = ?", (willis,))[0] == "wildcard"
    assert st.query_one("SELECT quarantine, display_name FROM actors WHERE actor_id = ?", (willis,))[0] == 1
    assert json.loads(st.meta("reality_exception")) == [willis]
    assert (st.meta("cheat_active"), st.meta("sandbox")) == ("0", "0")
    assert not st.query("SELECT 1 FROM cheat_log")
    zone = "SELECT p.zone_id FROM positions q JOIN places p ON p.place_id = q.place_id WHERE q.body_id = ?"
    assert st.query_one(zone, (willis,))[0] != st.query_one(zone, (s.pc_id,))[0], "not where you start"
    cup = st.query_one("SELECT item_id, def_ref FROM items WHERE holder_body = ? AND holder_slot = 'hand_r'", (willis,))
    assert cup[1] == "cheat_admin:item/coffee_cup"
    assert st.query_one("SELECT def_ref FROM items WHERE container_id = ?", (cup[0],))[0] == "cheat_admin:item/black_coffee", \
        "a raging coffee addict: the cup is never empty"
    assert not st.query("SELECT 1 FROM acquaintance WHERE holder_id = ? OR subject_id = ?", (willis, willis))


def test_friendly_never_a_friend(wild):
    """REL-06: he may come to trust and respect you; his fondness stops at the ant you picked up to play
    with, and he never owes anyone anything — and how you feel about him is yours."""
    s = wild
    st = s.store
    willis = st.query_one("SELECT body_id FROM bodies WHERE origin = 'wildcard'")[0]
    assert json.loads(st.meta("fickle")) == [willis]
    pc = s.pc_id
    other = st.query_one("SELECT a.actor_id FROM actors a JOIN bodies b ON b.body_id = a.actor_id WHERE b.alive = 1 "
                         "AND a.actor_id NOT IN (?, ?) ORDER BY a.actor_id", (willis, pc))[0]
    with st.transaction() as tx:
        cause = tx.query_one("SELECT event_id FROM events ORDER BY seq DESC LIMIT 1")[0]
        at = tx.query_one("SELECT now_ms FROM world_clock")[0]

        def rel(frm, to, axis, d):
            mind_mod.relate(tx, frm, to, axis, d, cause, at, 0)
            r = tx.query_one(f"SELECT {axis} FROM relationships WHERE from_id = ? AND to_id = ?", (frm, to))
            return 0 if r is None else r[0]
        assert rel(willis, pc, "affection", 3) == mind_mod.FICKLE_AFFECTION_MAX == 1
        assert rel(willis, other, "obligation", 2) == 0, "he owes nobody"
        assert rel(willis, pc, "trust", 3) == 3 and rel(willis, pc, "respect", 2) == 2
        assert rel(willis, pc, "affection", -3) == -2 and rel(willis, pc, "affection", 3) == 1
        assert rel(pc, willis, "affection", 3) == 3 and rel(other, willis, "obligation", 2) == 2


def test_he_is_never_where_you_left_him(wild):
    """CHEAT-15: each world day he is not in your active area he is somewhere else by morning (the
    off-screen stream); beside you he stays as long as he likes (WORLD-04)."""
    from as_engine.turn import timers
    s = wild
    st = s.store
    willis = st.query_one("SELECT body_id FROM bodies WHERE origin = 'wildcard'")[0]
    where = "SELECT place_id FROM positions WHERE body_id = ?"
    start = st.query_one(where, (willis,))[0]
    with st.transaction() as tx:
        now, t = tx.query_one("SELECT now_ms, turn_index FROM world_clock")
        timers.run_offscreen(tx, s.rng, now + 30 * 3_600_000, t)
    assert st.query_one(where, (willis,))[0] != start
    assert st.query_one("SELECT alive FROM bodies WHERE body_id = ?", (willis,))[0] == 1
