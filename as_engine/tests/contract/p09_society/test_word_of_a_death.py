"""Word of a death (D-222). Core CAS-111; settings ResolveRules.drains 'word_of_a_death'; action/cascade.py
drain_resolve (grieved once).

Seeing someone you love die wears you down (CAS-008), and a guardian told their child is dead is broken by it
(CAS-030). Mae, told her husband Hal was dead, felt nothing at all. Now being told costs less than seeing it, and a
loss is grieved once however many times it is told.
"""

from __future__ import annotations

import pytest

from as_engine.action import cascade
from as_engine.world import rumours

from society_kit import accident, now

pytestmark = pytest.mark.phase(9)


def seed(w, holder, about):
    with w.store.transaction() as tx:
        cause = accident(tx, now(w), "found dead on the road")
        return rumours.seed(tx, w.id(holder), w.id(about), "dead", now(w), 0, cause.event_id, confidence=3)


def tell(w, rid, teller, listener):
    with w.store.transaction() as tx:
        rs = rumours.spread_one(tx, rid, w.id(teller), w.id(listener), now(w), 0, None)
        return cascade.sweep(tx, [rs], tx.canon.all("cascade"), now(w), 0)


def drains(w, who):
    return [r[0] for r in w.store.query("SELECT json_extract(payload, '$.reason') FROM events WHERE type = 'RESOLVE_CHANGE' AND "
                                        "json_extract(payload, '$.actor_id') = ?", (w.id(who),))]


def test_mae_is_told_hal_is_dead(settle):
    w = settle
    rid = seed(w, "finn", "hal")
    tell(w, rid, "finn", "mae")
    assert drains(w, "mae") == ["word_of_a_death"]
    tell(w, rid, "finn", "kit")
    assert drains(w, "kit") == [], "Kit was not close to him"


def test_told_twice_grieved_once(settle):
    w = settle
    rid = seed(w, "finn", "hal")
    tell(w, rid, "finn", "mae")
    tell(w, rid, "finn", "kit")
    tell(w, rid, "kit", "mae")
    assert drains(w, "mae") == ["word_of_a_death"]


def test_a_guardian_told_is_broken_once(settle):
    """Hal told his daughter Pip is dead: CAS-030's lost_dependent, not a second drain from CAS-111."""
    w = settle
    rid = seed(w, "finn", "pip")
    tell(w, rid, "finn", "hal")
    assert drains(w, "hal") == ["lost_dependent"]


def test_never_the_player_character(settle):
    w = settle
    rid = seed(w, "finn", "hal")
    made = tell(w, rid, "finn", "pc")
    assert not [e for e in made if e.type == "RESOLVE_CHANGE"]
