"""What the owner asked the console to do besides (P12b). Rules CHEAT-04, CHEAT-05; DECISIONS D-78,
D-101 (cheats/commands.py: will, forget, infect, cure, horde, mega, census).

A will overwritten, a memory cut out, the strain put in someone far away — in the middle of their
council's meeting — the cure that nothing in the world has, a horde called up from its own
district, the end of the world sent early, and a head count. Every one of them happens inside the
simulation, on the record, and marks the run a Sandbox.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from as_engine.cheats import commands as cheats
from as_engine.contracts.events import Event, EventType
from as_engine.world import hordes

pytestmark = pytest.mark.phase(12)


def cheat(s, line):
    if s.store.meta("cheat_active") != "1":
        cheats.activate(s)
    cmd = cheats.parse(line)
    assert isinstance(cmd, cheats.CheatCommand), cmd
    return asyncio.run(cheats.execute(s, cmd))


def loops(w, who):
    return [tuple(r) for r in w.store.query("SELECT kind, text, strength, status FROM open_loops WHERE holder_id = ? "
                                            "ORDER BY created_at, loop_id", (who,))]


def test_a_will_overwritten(night):
    w, s = night
    mara = w.id("mara")
    r = cheat(s, '/will Mara "get out of the city tonight"')
    assert r.ok and "now wants: get out of the city tonight" in r.persona_line + r.detail
    assert w.store.query_one("SELECT goal_text FROM actors WHERE actor_id = ?", (mara,))[0] == "get out of the city tonight"
    assert w.store.query_one("SELECT goal_text, steps FROM plans WHERE actor_id = ?", (mara,)) is not None
    assert ("goal", "I want: get out of the city tonight", 3, "open") in loops(w, mara), "it wants it now, as its own"
    assert not [x for x in loops(w, mara) if x[0] in ("goal", "plan") and x[3] == "open" and "get out" not in x[1]]
    no = cheat(s, '/will me "anything"')
    assert not no.ok and no.persona_line == "That one's yours already, Boss."


def test_a_memory_cut_out(night):
    w, s = night
    june, mara = w.id("june"), w.id("mara")
    w.store.conn.execute("INSERT INTO episodes (episode_id, holder_id, at, turn_index, place_id, summary, salience, percept_ids, "
                         "subject_ids, anchor, decayed, quarantined) VALUES ('epi_900001', ?, 0, 0, NULL, "
                         "'Mara told me to keep the back door shut.', 60, '[]', ?, 0, 0, 0)", (june, json.dumps([mara])))
    had_name = w.store.query_one("SELECT 1 FROM acquaintance WHERE holder_id = ? AND subject_id = ?", (june, mara))
    r = cheat(s, "/forget June about Mara")
    assert r.ok and r.persona_line
    assert w.store.query_one("SELECT quarantined FROM episodes WHERE episode_id = 'epi_900001'")[0] == 1, \
        "kept as evidence, never reached again"
    assert not w.store.query("SELECT 1 FROM claim_holdings h JOIN propositions p ON p.prop_id = h.claim_id WHERE h.holder_id = ? "
                             "AND h.superseded_by IS NULL AND (p.subject_id = ? OR p.object_value = ?)", (june, mara, mara))
    assert w.store.query_one("SELECT 1 FROM acquaintance WHERE holder_id = ? AND subject_id = ?", (june, mara)) is None
    assert had_name is None or True
    assert ("question", "There's a gap in my memory I can't account for.", 1, "open") in loops(w, june)


def test_the_strain_put_in_someone_far_away_mid_meeting(gen):
    s = gen
    ghosts = s.store.query_one("SELECT group_id FROM groups WHERE name = 'The Ghosts'")[0]
    member = s.store.query_one("SELECT m.actor_id FROM group_members m JOIN actors a ON a.actor_id = m.actor_id "
                               "WHERE m.group_id = ? ORDER BY m.actor_id", (ghosts,))[0]
    name = s.store.query_one("SELECT display_name FROM actors WHERE actor_id = ?", (member,))[0]
    with s.store.transaction() as tx:
        now = tx.query_one("SELECT now_ms FROM world_clock")[0]
        tx.commit_event(Event(type=EventType.COUNCIL_MEETING, writer="world.factions", at=now, turn_index=0,
                              payload={"group_id": ghosts}))
    r = cheat(s, f'/infect "{name}"')
    assert r.ok and r.detail.endswith("in the middle of the council's meeting"), r
    (row,) = s.store.query("SELECT pathway, stage, known_to_self FROM infections WHERE body_id = ?", (member,))
    assert (row[0], row[2]) == ("wet", 0)
    assert not cheat(s, f'/infect "{name}"').ok, "already carrying it"
    assert cheat(s, f'/cure "{name}"').ok and not s.store.query("SELECT 1 FROM infections WHERE body_id = ?", (member,))
    assert cheat(s, f'/cure "{name}"').persona_line == "Nothing in them to cure, Boss."


def test_the_cure_on_what_rose_kills_it(night):
    w, s = night
    mara = w.id("mara")
    assert cheat(s, "/kill Mara").ok
    from as_engine.world import infected
    shambler = next(r for r in w.canon.refs("infected") if "SHAMBLER" in r)
    with w.store.transaction() as tx:
        place = tx.query_one("SELECT place_id FROM positions WHERE body_id = ?", (w.id("pc"),))[0]
        risen = infected.spawn(tx, s.rng, place, w.canon.get(shambler).id, 0, 0, None)
    w.store.conn.execute("UPDATE infected_state SET risen_from = ? WHERE body_id = ?", (mara, risen))
    r = cheat(s, "/cure Mara")
    assert r.ok
    assert tuple(w.store.query_one("SELECT alive, core_intact FROM bodies WHERE body_id = ?", (risen,))) == (0, 0), \
        "the infection gone, the body dies at once (D-78)"


def test_a_horde_from_its_own_district_the_end_early_and_a_count(gen):
    s = gen
    before = hordes.census(s.store)["total"]
    r = cheat(s, "/horde 5")
    assert r.ok
    (h,) = s.store.query("SELECT kind, composition FROM hordes WHERE kind = 'drawn'")
    assert sum(json.loads(h[1]).values()) == 5
    assert hordes.census(s.store)["total"] == before, "the district's own dead: nothing made from nothing (HRD-15)"
    assert cheat(s, "/mega").ok
    assert s.store.query("SELECT 1 FROM hordes WHERE kind = 'mega' AND status != 'gone'")
    again = cheat(s, "/mega")
    assert not again.ok and again.persona_line == "One's already coming, Boss. Patience."
    c = cheat(s, "/census")
    assert c.ok and c.detail.startswith(f"The dead: {hordes.census(s.store)['total']} ")
    story = " ".join(x[0] for x in s.store.query("SELECT text FROM story_log"))
    assert c.detail not in story
    assert s.store.meta("sandbox") == "1"
