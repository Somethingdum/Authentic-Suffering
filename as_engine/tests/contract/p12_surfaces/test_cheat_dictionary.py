"""The Cheat field's own words and its dictionary (P12). Rules CHEAT-20, CHEAT-21, CHEAT-03; DECISIONS D-115
(cheats/commands.py plain_command, dictionary, execute; service/game_service.py on_turn_compose,
on_cheat_dictionary_get).

The owner: "There needs to be an auto complete that shows all of the options, and a dictionary on that same
menu so I don't get confused. I should also just be able to say 'Spawn Fredrick' in the cheats thing."
"""

from __future__ import annotations

import asyncio

import pytest
from protocol_kit import actions, only, send

from as_engine.cheats import commands as cheats
from as_engine.contracts.common import CallClass
from as_engine.physical import bodies

pytestmark = pytest.mark.phase(12)


def opened(s):
    if s.store.meta("cheat_active") != "1":
        cheats.activate(s)


def story_count(store):
    return store.query_one("SELECT COUNT(*) FROM story_log")[0]


# ------------------------------------------------------------------------- CHEAT-20 plain_command


def test_a_command_word_first_is_that_command():
    cmd = cheats.plain_command("  Spawn Fredrick ")
    want = cheats.parse("/Spawn Fredrick")
    assert isinstance(cmd, cheats.CheatCommand) and (cmd.name, cmd.args) == (want.name, want.args) == ("spawn", want.args)
    assert cmd.raw == "Spawn Fredrick", "the line as the Boss typed it, stripped"
    give = cheats.plain_command("give bandage 3 to Mara")
    assert (give.name, give.args) == ("give", cheats.parse("/give bandage 3 to Mara").args)
    assert cheats.plain_command("Census").name == "census"
    assert cheats.plain_command("kill the lights").name == "kill", "whether it can happen is execute's to say"


@pytest.mark.parametrize("line", ["", "   ", "/spawn fredrick", "off with his head", "reveal the truth to Mara",
                                  "census the dead please", "Make that infected jig joyously", "spawn",
                                  "give", "time to go", "help me"])
def test_anything_else_is_plain_words(line):
    assert cheats.plain_command(line) is None, line


def test_every_command_has_its_words():
    assert set(cheats.ARGLESS) <= set(cheats.COMMAND_NAMES) and set(cheats.SLOTS) <= set(cheats.COMMAND_NAMES)
    for name in cheats.COMMAND_NAMES:
        assert cheats.MEANINGS[name] and cheats.USAGE[name].startswith(f"/{name}")
        ex = cheats.EXAMPLES[name]
        assert ex.startswith(f"/{name}") and isinstance(cheats.parse(ex), cheats.CheatCommand), (name, ex)
        assert (name in cheats.ARGLESS) == (cheats.parse(ex).args == {} and cheats.USAGE[name] == f"/{name}"), name


def test_a_plain_command_that_cannot_happen_leaves_no_trace(night):
    """CHEAT-20: so the line can go on to plain words as if it had never been tried."""
    w, s = night
    opened(s)
    before = story_count(w.store)
    r = asyncio.run(cheats.execute(s, cheats.plain_command("kill the lights")))
    assert not r.ok and r.untouched and story_count(w.store) == before
    assert not w.store.query("SELECT 1 FROM cheat_log") and w.store.meta("sandbox") != "1"
    slash = asyncio.run(cheats.execute(s, cheats.parse("/kill the lights")))
    assert not slash.ok and not slash.untouched and story_count(w.store) == before + 1, "a '/' line keeps its record"


# ------------------------------------------------------------------------- CHEAT-21 the dictionary


def test_the_dictionary_names_every_lever_and_what_it_can_take(night):
    w, s = night
    opened(s)
    with w.store.transaction() as tx:
        rows = cheats.dictionary(tx, s.pc_id, s.config.content_dir)
    assert [r["name"] for r in rows] == [n for n in cheats.COMMAND_NAMES if n != "wonder"], "wonder is Willis's alone"
    for r in rows:
        n = r["name"]
        assert set(r) == {"name", "usage", "meaning", "example", "slots"}
        assert (r["usage"], r["meaning"], r["example"]) == (cheats.USAGE[n], cheats.MEANINGS[n], cheats.EXAMPLES[n])
        assert list(r["slots"]) == list(cheats.SLOTS.get(n, ())), n
        for slot, opts in r["slots"].items():
            assert opts and len({o.lower() for o in opts}) == len(opts), (n, slot)
    slots = {k: v for r in rows for k, v in r["slots"].items()}
    assert slots["person"][0] == "me" and "Mara" in slots["person"]
    assert slots["person"][1:] == sorted(slots["person"][1:], key=str.lower)
    assert "fredrick" in slots["what"] and "shambler" in slots["what"], "the cheat packs and the dead by type"
    assert slots["stat"][:8] == list("SPECIAL") + ["resolve"]
    assert slots["kind"] == list(cheats.WEATHER_KINDS) and "wet" in slots["strain"]
    assert slots["place"] and slots["item"] == sorted(slots["item"], key=str.lower)
    excepted = bodies.grant_exception
    with w.store.transaction() as tx:
        excepted(tx, s.pc_id, 0, 0, origin="cheat")
    with w.store.transaction() as tx:
        assert cheats.dictionary(tx, s.pc_id)[-1]["name"] == "wonder"


async def test_nothing_about_the_console_before_the_word(svc, make_run):
    """CHEAT-03: before the word the dictionary is empty — the field does not exist."""
    assert only(await send(svc, "cheat_dictionary_get"), "cheat_dictionary") == {"commands": []}
    await send(svc, "run_load", run_id=make_run())
    assert only(await send(svc, "cheat_dictionary_get"), "cheat_dictionary") == {"commands": []}
    await send(svc, "turn_compose", cheat="2508")
    got = only(await send(svc, "cheat_dictionary_get"), "cheat_dictionary")["commands"]
    assert [c["name"] for c in got] == [n for n in cheats.COMMAND_NAMES if n != "wonder"]


# ------------------------------------------------------------------------- the Cheat field


async def test_spawn_fredrick_in_the_cheat_field(svc, make_run, fake):
    """CHEAT-20: a command word first is the command — no plain-words reading; anything it cannot do goes on
    to plain words untouched."""
    await send(svc, "run_load", run_id=make_run())
    await send(svc, "turn_compose", cheat="2508")
    st = svc.session.store
    r = await send(svc, "turn_compose", cheat="Spawn Fredrick")
    assert actions(r) == ["cheat_result", "view", "story"] and only(r, "cheat_result")["ok"] is True
    assert st.query("SELECT 1 FROM actors WHERE display_name LIKE 'Fredrick%'")
    assert [x[0] for x in st.query("SELECT command FROM cheat_log")] == ["Spawn Fredrick"]
    assert not fake.calls(CallClass.CHEAT_INTERPRET)
    fake.script(CallClass.CHEAT_INTERPRET, lambda q: {"ops": [], "clarify": "Which lights, Boss?", "summary": ""})
    before = story_count(st)
    r = await send(svc, "turn_compose", cheat="kill the lights")
    assert only(r, "cheat_result")["persona_line"] == "Which lights, Boss?", "on to plain words"
    assert len(fake.calls(CallClass.CHEAT_INTERPRET)) == 1 and story_count(st) - before <= 1
    assert not [t for (t,) in st.query("SELECT text FROM story_log") if t.startswith("kill the lights\n")]
