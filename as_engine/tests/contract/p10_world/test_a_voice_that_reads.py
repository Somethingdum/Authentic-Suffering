"""A voice that reads (D-237). world/worldgen/people.py (the voice tables, the capsule); mind/identity.py and
mind/packet.py (the habits, each a sentence); mind/perception.py the_name (render_portal and every sentence that
opens on a thing's name).

Most of a world's people get their voice from the generator, and it is the first thing their own prompt says about
how they talk: "Victor soft-spoken and exact; never raises their voice, even now." — half the habits were not
something a person does ("dry jokes", "polite to a fault"), so the name and the habit made no sentence; the habits
said "their" and "themself" of a man; and the card listed them as "soft-spoken and exact. never raises …". A way the
world made — "the way to Pump house" — came out "The the way to Pump house is open."
"""

from __future__ import annotations

import re

import pytest

from as_engine.contracts.common import LOD
from as_engine.contracts.dossier import ActorDossier
from as_engine.mind import identity, perception
from as_engine.mind.affordance import enumerate_affordances
from as_engine.mind.packet import build_packet
from as_engine.mind.perception import render_portal
from as_engine.world.worldgen import people

pytestmark = pytest.mark.phase(10)

TABLES = (people._VOICES, people._KID_VOICES, people._TEEN_VOICES, people._ELDER_VOICES)


def unquoted(text):
    return re.sub(r"'[^']*'", "", text)


def test_every_habit_is_something_they_do():
    """Each habit follows a name as a sentence: it starts with what they do ('makes', 'is', 'never') — and says
    nothing of them as 'they', 'their', 'them' or 'themself' (a quoted word is their own)."""
    bad = []
    for table in TABLES:
        for pair in table:
            for habit in pair:
                first = habit.split()[0]
                verb = first in ("is", "never", "barely") or (first.endswith("s") and not first.endswith(("ous", "ss")))
                if not verb or re.search(r"\b(they|their|them|themself|themselves)\b", unquoted(habit)):
                    bad.append(habit)
    assert bad == []


def seed(i, age, sex):
    return people.PersonSeed(name=f"Victor{i} Hale", age=age, sex=sex, cohort="pre_fall_adult" if age > 20 else "post_fall_born",
                             occupation="watcher" if age >= 16 else "child", skills={"firearms": 1} if age >= 16 else {},
                             special={L: 5 for L in "SPECIAL"}, variant=(i * 37) % 1000, settlement_name="Vale",
                             group_name="the Vale")


@pytest.mark.parametrize("age", [8, 15, 35, 70])
def test_how_they_talk_reads_as_english(age):
    for i in range(60):
        d = people.skeleton_dossier(seed(i, age, "male"))
        first, rest = d["voice"]["capsule"].split(" ", 1)
        tend = d["voice"]["speech_tendencies"]
        assert rest == f"{tend[0]}; {tend[1]}." and first.startswith("Victor")
        texts = [ln.text for sec in identity.compile_identity(ActorDossier.model_validate(d)).sections for ln in sec.lines]
        assert d["voice"]["capsule"] in texts and not any(t.startswith("How you tend to speak") for t in texts), \
            "the capsule says the habits, once (D-246)"
        d["voice"]["capsule"] = f"{first} keeps to the point."               # a card whose habits say more than it
        texts = [ln.text for sec in identity.compile_identity(ActorDossier.model_validate(d)).sections for ln in sec.lines]
        [said] = [t.removeprefix("How you tend to speak: ") for t in texts if t.startswith("How you tend to speak: ")]
        assert all(s[:1].isupper() for s in re.split(r"(?<=\.) ", said)), said


def test_the_way_the_world_made(scenario):
    w = scenario("metal_fence")
    w.store.conn.execute("UPDATE portals SET name = 'the way to the alley' WHERE portal_id = ?", (w.id("back_door"),))
    with w.store.transaction() as tx:
        assert render_portal(tx, w.id("back_door")) == "The way to the alley is open."
        assert render_portal(tx, w.id("office_door")) == "The office door is closed."


def test_watching_the_way(scenario):
    """Where she may keep her eyes (FOCUS-01): a way the world made is watched as itself."""
    w = scenario("metal_fence")
    w.store.conn.execute("UPDATE portals SET name = 'the way to the alley' WHERE portal_id = ?", (w.id("back_door"),))
    t = w.store.query_one("SELECT now_ms FROM world_clock")[0]
    who = w.store.query_one("SELECT body_id FROM positions WHERE place_id = ? ORDER BY body_id LIMIT 1", (w.id("storeroom"),))[0]
    with w.store.transaction() as tx:
        perception.compile_scene(tx, who, t, 0)
        pkt = build_packet(tx, who, LOD.HOT, enumerate_affordances(tx, who, w.canon.all("affordance"), t, 0), 0, t)
    labels = [f.label for f in pkt.attention_points if pkt.handles[f.handle] == w.id("back_door")]
    assert labels == ["Watch the way to the alley"]
