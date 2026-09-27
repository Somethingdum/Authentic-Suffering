"""D-109 — Addison Flores rebuilt from the owner's writer's bible and canon (PROTECTED).

The owner (2026-09-26): she is from Boston and moved south after the Fall; ten at the Fall; pale;
a mild Boston accent; "forget the skort, it's light parkour pants now"; the laundromat — the lurker
that wore Dave's voice and hers, and the man she calls George — "is a cannon event, this actually
happened to Addison, and is a memory at start". A run begins "any time after".
"""

from __future__ import annotations

import json

import helpers
import pytest
from pydantic import ValidationError

from as_engine.contracts.dossier import CanonEvent
from as_engine.physical import objects
from as_engine.world.worldgen import opening

DAY = 86_400_000
H = 3_600_000


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def addison(canon):
    return canon.get("core:pc/addison_flores")


# =========================================================================== the card
def test_she_is_from_boston_with_a_boston_accent(canon):
    a = addison(canon)
    assert a.identity.birthplace.startswith("Boston")
    assert "Boston" in a.voice.dialect_notes
    blob = json.dumps(a.model_dump(mode="json"))
    assert "Mississippi" not in blob and "Hattiesburg" not in blob and "y'all" not in blob


def test_pale_skin_and_the_bun(canon):
    a = addison(canon)
    assert a.appearance.looks.complexion.startswith("pale skin")
    assert a.appearance.looks.hair_style == "in a tight low bun" and a.appearance.looks.hair_length == "long"
    assert "tan" not in a.appearance.skin.lower()


def test_light_parkour_pants_not_the_skort(canon):
    a = addison(canon)
    worn = {o.item for o in a.appearance.looks.outfit}
    assert "core:item/parkour_pants" in worn and "core:item/skort" not in worn
    assert "parkour pants" in a.appearance.clothing_usual and "skort" not in a.appearance.clothing_usual
    assert canon.get("core:item/parkour_pants").clothing.words == "light parkour pants"


def test_the_bible_voice_lines(canon):
    """Her three sample lines are the bible's, not the kit's inventions."""
    ex = addison(canon).voice.exemplars
    assert ex.low_stakes.startswith("Gotta ask, do you have those stick-on mustaches?")
    assert ex.at_the_limit == "You do not get to do that to me."


def test_hard_to_crash_out(canon):
    """Bible §15.7: 'She is hard to crash out. The compression holds.'"""
    t = addison(canon).temper
    assert t.fuse >= 4 and t.outlet == "cold"


def test_she_knows_the_mimicry(canon):
    a = addison(canon)
    assert "knows_lurker_mimicry" in a.knowledge.cues
    assert canon.find("cue", "knows_lurker_mimicry").description


def test_dressed_from_her_card(scenario, canon):
    """physical.objects.dress (as worldgen dresses a PC, WG-31): pants, bra and shoes cover her."""
    w = scenario("rooftops")
    pc = w.id("pc")
    with w.store.transaction() as tx:
        objects.dress(tx, pc, addison(canon).appearance.looks.outfit, now(w), None, 0, "scenario")
    got = {o["def_ref"]: o for o in objects.worn(w.store, pc) if o["clothing"]}
    assert {"core:item/parkour_pants", "core:item/sports_bra", "core:item/parkour_shoes"} <= set(got)
    assert got["core:item/sports_bra"]["colour"] == "pink"
    assert {"groin", "legs", "torso", "feet"} <= objects.coverage(w.store, pc)


# =========================================================================== the canon event
def test_the_laundromat_is_canon(canon):
    ev = addison(canon).canon_events
    assert [e.title for e in ev] == ["The laundromat"]
    assert "Dave" in ev[0].memory and "lurker" in ev[0].memory
    assert ev[0].days_before_start == (1, 365)


def test_days_before_start_must_be_a_real_range():
    with pytest.raises(ValidationError):
        CanonEvent(title="Too soon", memory="Something that happened on the very day.", days_before_start=(0, 3))
    with pytest.raises(ValidationError):
        CanonEvent(title="Backwards", memory="Something that happened, out of order.", days_before_start=(9, 3))


def test_canon_memories_writes_an_anchor_memory_before_the_run(scenario, canon):
    """WG-33b: one personal history row and one anchor episode, salience 100, on a day 1-365 before."""
    w = scenario("rooftops")
    pc = w.id("pc")
    dsf = now(w) // DAY
    with w.store.transaction() as tx:
        hws, ews = opening.canon_memories(tx, w.rng, addison(canon), pc, dsf)
    assert len(hws) == 1 and len(ews) == 1
    h, e = hws[0].values, ews[0].values
    assert h["kind"] == "personal" and h["truth_text"] == "The laundromat" and h["subject_ids"] == [pc]
    assert dsf - 365 <= h["day"] <= dsf - 1
    assert e["holder_id"] == pc and e["anchor"] == 1 and e["salience"] == 100
    assert e["at"] == h["day"] * DAY + 12 * H and e["summary"] == addison(canon).canon_events[0].memory


def test_no_canon_events_no_draw(scenario, canon):
    """A PC with none writes nothing and draws nothing (a ScriptedRng with no values would raise)."""
    w = scenario("rooftops")
    owen = canon.get("core:pc/owen_marsh")
    assert not owen.canon_events
    with w.store.transaction() as tx:
        assert opening.canon_memories(tx, helpers.ScriptedRng(), owen, w.id("pc"), 3400) == ([], [])


def test_the_day_is_drawn_on_the_opening_stream(scenario, canon):
    """The draw is rng.range_int on 'worldgen:opening', purpose 'canon:0' — scripted, it is exact."""
    w = scenario("rooftops")
    rng = helpers.ScriptedRng(30)
    with w.store.transaction() as tx:
        hws, ews = opening.canon_memories(tx, rng, addison(canon), w.id("pc"), 3400)
    assert rng.asked == [("range_int", "worldgen:opening", "canon:0")]
    assert hws[0].values["day"] == 3370 and ews[0].values["at"] == 3370 * DAY + 12 * H
