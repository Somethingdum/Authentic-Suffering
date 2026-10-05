"""No two voices alike in one place (D-199). world/worldgen/people.py skeleton_dossier (PersonSeed.voices_taken; the
voice pools, doubled); worldgen WG6 deals a settlement's voices out with no repeats.

Every generated person drew their voice on their own — twenty adult voices, each with its three lines — so in a
settlement of thirty, more than twenty shared a voice and its very words ("Work's done. Could be worse.") with
someone else there, and the model, shown the same example lines, made them talk alike. The owner: "If they all talk
the same... I'll crash out."
"""

from __future__ import annotations

import dataclasses

import pytest

from as_engine.world.worldgen import people as P

pytestmark = pytest.mark.phase(10)


def seed(i, age=34, cohort="pre_fall_adult"):
    return P.PersonSeed(name=f"Person {i}", age=age, sex="female", cohort=cohort, occupation="farmer", skills={},
                        special={L: 5 for L in "SPECIAL"}, variant=i, settlement_name="Pumpwell", group_name="Pumpwell settlers")


def first_line(d):
    return d["voice"]["exemplars"]["low_stakes"]


def test_dealt_out_no_two_alike():
    heard = []
    for i in range(30):
        heard.append(first_line(P.skeleton_dossier(dataclasses.replace(seed(i), voices_taken=tuple(heard)))))
    assert len(set(heard)) == 30, "thirty adults, thirty voices"


def test_when_every_voice_is_taken_one_is_still_drawn():
    every = tuple(e[0] for e in P._EXEMPLARS)
    d = P.skeleton_dossier(dataclasses.replace(seed(1), voices_taken=every))
    assert first_line(d) in every


def test_the_pools_hold_enough():
    assert len(P._VOICES) == len(P._EXEMPLARS) >= 40
    for v, e in ((P._ELDER_VOICES, P._ELDER_EXEMPLARS), (P._TEEN_VOICES, P._TEEN_EXEMPLARS), (P._KID_VOICES, P._KID_EXEMPLARS)):
        assert len(v) == len(e) >= 10
    assert len({e[0] for e in P._EXEMPLARS}) == len(P._EXEMPLARS), "no two voices open with the same line"


def test_born_after_the_fall_still_never_remembers_before():
    heard = []
    for i in range(25):
        d = P.skeleton_dossier(dataclasses.replace(seed(i, 19, "post_fall_born"), voices_taken=tuple(heard)))
        heard.append(first_line(d))
        text = " ".join(d["voice"]["exemplars"].values()) + " " + " ".join(d["voice"]["speech_tendencies"])
        assert "before" not in text and "old world" not in text, text


def test_a_faction_team_does_not_sound_like_its_people(gw):
    """D-203: a Ghost decontamination team made mid-game is dealt voices nobody in the Depot, or among the Ghosts,
    already has — and no two operators share one."""
    from as_engine.mind.actor import fused
    from as_engine.world import factions
    s = gw
    g = s.store.query_one("SELECT group_id FROM groups WHERE content_ref = 'core:faction/ghosts'")[0]
    stl = factions.enclave(s.store, g)
    home = s.store.query_one("SELECT group_id, place_id FROM settlements WHERE settlement_id = ?", (stl,))
    t = s.store.query_one("SELECT now_ms FROM world_clock")[0]
    with s.store.transaction() as tx:
        here = {r[0] for r in tx.query("SELECT m.actor_id FROM group_members m JOIN bodies b ON b.body_id = m.actor_id WHERE "
                                       "m.group_id IN (?, ?) AND m.status IN ('member', 'probation') AND b.alive = 1",
                                       (home[0], g))}
        before = {fused(tx, a).voice.exemplars.low_stakes for a in here
                  if tx.query_one("SELECT controller FROM actors WHERE actor_id = ?", (a,))[0] != "human"}
        team = factions.team(tx, s.rng, g, t, 0, None)
        voices = [fused(tx, b).voice.exemplars.low_stakes for b in team]
    assert team and len(set(voices)) == len(voices), voices
    if len(before) + len(team) <= len(P._EXEMPLARS):
        assert not set(voices) & before, "none sounds like someone already there"
