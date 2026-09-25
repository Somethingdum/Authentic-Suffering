"""The developer word and what it unlocks (P12). Rules CHEAT-01, CHEAT-04..11 (cheats/commands.py;
docs/as/CHEATS.md). The night at Delgado's, Owen on the sales floor with Mara, Alice, June, Eli and
Nita about.

Every command that changes or reveals anything is on the record (cheat_log and a CHEAT_OVERRIDE
of origin 'cheat') and marks the run Sandbox for good; nothing rewrites the past; what the
console tells the Boss never reaches the story or a mind — except /brief, which goes in through
the ordinary door.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from as_engine.audit import abuse
from as_engine.cheats import _impl_cheats, commands as cheats
from as_engine.contracts.common import CallClass
from as_engine.physical.bodies import WoundSpec, apply_harm

pytestmark = pytest.mark.phase(12)


def meta(w, key):
    r = w.store.query_one("SELECT value FROM meta WHERE key = ?", (key,))
    return None if r is None else r[0]


def cheat(s, line):
    """Activates when needed, then runs one command line; the CheatResult."""
    if meta_s(s, "cheat_active") != "1":
        cheats.activate(s)
    cmd = cheats.parse(line)
    assert isinstance(cmd, cheats.CheatCommand), cmd
    return asyncio.run(cheats.execute(s, cmd))


def meta_s(s, key):
    r = s.store.query_one("SELECT value FROM meta WHERE key = ?", (key,))
    return None if r is None else r[0]


def logged(w):
    return [dict(r) for r in w.store.query("SELECT * FROM cheat_log ORDER BY rowid")]


def overrides(w, writer=None):
    rows = w.store.query("SELECT writer, origin, payload FROM events WHERE type = 'CHEAT_OVERRIDE' ORDER BY seq")
    return [(r[0], r[1], json.loads(r[2])) for r in rows if writer in (None, r[0])]


def test_the_word_is_a_standalone_number():
    assert cheats.detect_activation("I scratch 2508 into the door")
    assert not cheats.detect_activation("12508") and not cheats.detect_activation("25080")


def test_waking_it_consumes_the_line_and_marks_nothing(night):
    w, s = night
    t0 = w.store.query_one("SELECT now_ms, turn_index FROM world_clock")
    r = cheats.activate(s)
    assert (r.ok, r.persona_line, r.detail) == (True, cheats.ACTIVATION_LINE, cheats.SHIMMER_NOTICE)
    assert meta(w, "cheat_active") == "1" and meta(w, "sandbox") == "0", "activation alone is not a Sandbox"
    assert w.store.query_one("SELECT now_ms, turn_index FROM world_clock") == t0, "no turn, no time"
    kinds = [r[0] for r in w.store.query("SELECT kind FROM story_log ORDER BY entry_id")]
    assert kinds[-2:] == ["notice", "cheat"]
    (ev,) = w.store.query("SELECT writer, origin FROM events WHERE type = 'CHEAT_ACTIVATED'")
    assert tuple(ev) == ("kernel.meta", "cheat")


def test_every_command_is_on_the_record_and_the_run_is_a_sandbox(night):
    w, s = night
    r = cheat(s, '/give ammo_38 5 to Mara')
    assert r.ok and r.persona_line
    (row,) = logged(w)
    assert row["command"] == '/give ammo_38 5 to Mara' and row["outcome"].startswith("gave 5")
    assert row["persona_line"] == r.persona_line and row["event_id"]
    assert [(x[0], x[1], x[2]["command"]) for x in overrides(w, "cheats")] == [("cheats", "cheat", "give")]
    assert meta(w, "sandbox") == "1"
    got = w.store.query("SELECT qty, origin, holder_slot FROM items WHERE holder_body = ? AND origin = 'cheat'", (w.id("mara"),))
    assert [tuple(g) for g in got] == [(5, "cheat", "pack")], "ammo stacks: one row of five"
    cheat(s, "/off")
    assert meta(w, "cheat_active") == "0" and meta(w, "sandbox") == "1", "the Sandbox mark stays forever"
    assert len(logged(w)) == 1, "/off is not logged"


def test_heal_and_god(night):
    w, s = night
    pc = w.id("pc")
    cause = w.store.query_one("SELECT event_id FROM events ORDER BY seq DESC LIMIT 1")[0]
    with w.store.transaction() as tx:
        apply_harm(tx, pc, WoundSpec("arm_l", "cut", "significant", 0), 0, cause, 0, s.rng)
    assert w.store.query("SELECT 1 FROM wounds WHERE body_id = ? AND healed_at IS NULL", (pc,))
    assert cheat(s, "/heal").ok
    assert not w.store.query("SELECT 1 FROM wounds WHERE body_id = ? AND healed_at IS NULL", (pc,))
    assert tuple(w.store.query_one("SELECT blood_loss_pct, pain FROM bodies WHERE body_id = ?", (pc,))) == (0.0, 0)
    assert cheat(s, "/god on").ok and json.loads(meta(w, "god_bodies")) == [pc]
    with w.store.transaction() as tx:
        assert apply_harm(tx, pc, WoundSpec("arm_l", "cut", "significant", 0), 0, cause, 0, s.rng) == []
    assert not w.store.query("SELECT 1 FROM wounds WHERE body_id = ? AND healed_at IS NULL", (pc,)), "harm no longer lands"
    with w.store.transaction() as tx:
        assert apply_harm(tx, w.id("mara"), WoundSpec("arm_l", "cut", "minor", 0), 0, cause, 0, s.rng), "per body, never per player"
    cheat(s, "/god off")
    assert json.loads(meta(w, "god_bodies")) == []


def test_tp_set_time_weather_rep(night):
    w, s = night
    pc, mara = w.id("pc"), w.id("mara")
    assert cheat(s, '/tp "Rear alley"').ok
    assert w.store.query_one("SELECT place_id FROM positions WHERE body_id = ?", (pc,))[0] == w.id("alley")
    assert not w.store.query("SELECT 1 FROM events WHERE type = 'MOVE' AND actor_id = ? AND origin = 'cheat'", (pc,)), \
        "not a MOVE: nobody saw it"
    assert cheat(s, "/set A 9").ok
    assert json.loads(w.store.query_one("SELECT special FROM bodies WHERE body_id = ?", (pc,))[0])["A"] == 9
    assert cheat(s, "/set resolve 99 Mara").ok
    rmax, rcur = w.store.query_one("SELECT resolve_max, resolve_cur FROM actors WHERE actor_id = ?", (mara,))
    assert rcur == rmax, "never above the maximum"
    assert cheat(s, "/set firearms 3 Mara").ok
    from as_engine.mind.actor import fused
    with w.store.transaction() as tx:
        skills = {x.domain.value: x.rank for x in fused(tx, mara).capability.skills}
    assert skills["firearms"] == 3
    t = w.store.query_one("SELECT now_ms FROM world_clock")[0]
    assert cheat(s, "/time +2h").ok
    assert w.store.query_one("SELECT now_ms FROM world_clock")[0] == t + 2 * 3_600_000, "the world lived two hours"
    assert cheat(s, "/weather storm").ok
    assert tuple(w.store.query_one("SELECT weather, wind_level FROM world_clock")) == ("storm", 3)
    assert cheat(s, "/rep \"Delgado's crew\" 4").ok
    assert w.store.query_one("SELECT standing FROM group_standing WHERE group_id = ? AND actor_id = ?", (w.id("crew"), pc))[0] == 4


def test_names_that_are_not_there_or_not_one(night):
    w, s = night
    r = cheat(s, "/heal Zebediah")
    assert not r.ok and r.persona_line == "Never heard of anyone called 'Zebediah', Boss."
    assert logged(w) == [] and meta(w, "sandbox") == "0", "nothing happened: nothing on the record"


def test_spawn_despawn_and_the_quarantine(night):
    w, s = night
    r = cheat(s, "/spawn shambler x2")
    assert r.ok
    dead = w.store.query("SELECT body_id FROM bodies WHERE kind = 'infected' AND origin = 'cheat'")
    assert len(dead) == 2
    r = cheat(s, "/spawn fredrick ally")
    assert r.ok
    fred = w.store.query_one("SELECT a.actor_id, a.quarantine, a.accepted_authority, d.source, d.content_ref FROM actors a "
                             "JOIN dossiers d ON d.dossier_id = a.dossier_id WHERE a.display_name LIKE 'Fredrick%'")
    assert fred is not None and fred[1] == 1 and json.loads(fred[2]) == [w.id("pc")]
    assert (fred[3], fred[4]) == ("cheat", "cheat_admin:actor/fredrick")
    assert w.store.query_one("SELECT place_id FROM positions WHERE body_id = ?", (fred[0],))[0] == \
        w.store.query_one("SELECT place_id FROM positions WHERE body_id = ?", (w.id("pc"),))[0]
    with w.store.transaction() as tx:
        assert abuse.battery(tx) == [], "his absurd stats and his quarantine are nobody's business (CHEAT-05)"
    assert cheat(s, "/spawn campervan").persona_line == cheats.RETIRED_SPAWNS["campervan"]
    no = cheat(s, "/despawn Mara")
    assert not no.ok and no.persona_line == "Only what I made, Boss. That one was here before me."
    assert cheat(s, "/despawn Fredrick").ok
    assert w.store.query_one("SELECT alive FROM bodies WHERE body_id = ?", (fred[0],))[0] == 0
    assert w.store.query_one("SELECT 1 FROM positions WHERE body_id = ?", (fred[0],)) is None, "gone from the world"
    assert overrides(w, "cheats")[-1][2].get("reconciliation") is True


def test_kill_and_revive_cure_nothing(night):
    w, s = night
    mara = w.id("mara")
    w.store.conn.execute("INSERT INTO infections (body_id, pathway, exposed_at, stage, cause_event, known_to_self) "
                         "VALUES (?, 'air', 0, 'incubating', '', 0)", (mara,))
    before = [tuple(r) for r in w.store.query("SELECT * FROM infections WHERE body_id = ?", (mara,))]
    assert cheat(s, "/kill Mara").ok
    (d,) = w.store.query("SELECT payload FROM events WHERE type = 'DEATH'")
    assert json.loads(d[0])["cause"] == "cheat"
    assert cheat(s, "/revive Mara").ok
    assert tuple(w.store.query_one("SELECT alive, awareness FROM bodies WHERE body_id = ?", (mara,))) == (1, "awake")
    assert [tuple(r) for r in w.store.query("SELECT * FROM infections WHERE body_id = ?", (mara,))] == before, "nothing cures"
    assert w.store.query("SELECT 1 FROM events WHERE type = 'DEATH'"), "the past is not rewritten"


def test_reveal_mind_and_brief(night, fake):
    w, s = night
    r = cheat(s, "/reveal")
    assert r.ok and r.detail.splitlines()[0].startswith("Sales floor: ")
    m = cheat(s, "/mind Mara")
    assert m.ok and m.detail.startswith("Goal: ")
    story = " ".join(x[0] for x in w.store.query("SELECT text FROM story_log"))
    assert r.detail not in story and m.detail not in story, "the console's answers never reach the story (CHEAT-06)"
    b = cheat(s, "/brief June")
    assert b.ok
    got = w.store.query("SELECT p.predicate FROM claim_holdings h JOIN propositions p ON p.prop_id = h.claim_id "
                        "WHERE h.holder_id = ? AND h.provenance = 'cheat'", (w.id("june"),))
    assert got and {g[0] for g in got} <= {"location", "wants", "aims"}
    assert w.store.query("SELECT 1 FROM percept_log WHERE holder_id = ? AND json_extract(detail, '$.cheat') = 1",
                         (w.id("june"),)), "on the record: through the ordinary door"


def test_noise(night):
    w, s = night
    assert cheat(s, '/noise 90 at "front window"').ok
    (p,) = w.store.query("SELECT payload FROM events WHERE type = 'NOISE' AND origin = 'cheat'")
    pl = json.loads(p[0])
    assert (pl["source_db"], pl["anchor_id"]) == (90, w.id("front_window"))


def test_the_persona_never_says_the_same_canned_line_twice_in_a_row(night, fake):
    w, s = night
    fake.fail(CallClass.CHEAT_PERSONA, "timeout", times=4)
    lines = [cheat(s, "/weather rain").persona_line, cheat(s, "/weather fog").persona_line,
             cheat(s, "/weather clear").persona_line]
    assert all(x in cheats.CANNED_LINES["weather"] for x in lines)
    assert lines[0] != lines[1] and lines[1] != lines[2]


def test_the_hard_line(night, monkeypatch):
    """CHEAT-08: a child's record with the words is refused and logged, and nothing happens."""
    from as_engine.content.safety import MINOR_UNSAFE_TERMS
    w, s = night
    child = w.canon.get("core:actor/mara_voss").model_copy(deep=True)
    child.identity.age = 12
    child.writers_notes = f"Scan probe word: {sorted(MINOR_UNSAFE_TERMS)[0]}."
    monkeypatch.setattr(_impl_cheats, "_spawn_ref", lambda tx, session, what: ("core:actor/probe", child))
    r = cheat(s, "/spawn probe")
    assert not r.ok and r.persona_line == "No. Not that, not ever, Boss."
    (row,) = logged(w)
    assert row["outcome"] == "refused: the hard line" and meta(w, "sandbox") == "0"
    assert not w.store.query("SELECT 1 FROM bodies WHERE origin = 'cheat'")


def test_cheat_packs_are_for_the_console_only(night):
    """CHEAT-10: the run's own content has no cheat_ record; only /spawn reads those packs."""
    w, s = night
    assert not [r for k in ("actor", "pc") for r in w.canon.refs(k) if r.startswith("cheat_")]
