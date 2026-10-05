"""Said to your face (D-215). mind/firewall.py classify_form THREAT; action/cascade.py threatened_to_their_face and
threatened_by_the_violent; core CAS-089, CAS-090.

The owner: "If I treat them like shit … I do expect reactions, and proper ones." "I'm gonna fucking kill you." was
a statement: only ten fixed phrases made a threat, a phone's curly apostrophe broke even those, and a threat with
nothing in hand cost the one who made it nothing at all. Now a promise of violence is a threat however it is put —
and "I'll never hurt you" is not one — and being threatened to your face costs the one who did it some of your
trust, once an hour however often they say it; from someone you have seen hurt a person, it frightens you too.
"""

from __future__ import annotations

import pytest

from as_engine.action import cascade
from as_engine.contracts.common import Anatomy, UtteranceForm as F, WoundSeverity, WoundType
from as_engine.contracts.events import Event, EventType
from as_engine.mind import firewall, perception
from as_engine.physical import bodies, space
from as_engine.physical.bodies import WoundSpec

pytestmark = pytest.mark.phase(9)

RULES = ("CAS-038", "CAS-089", "CAS-090")


@pytest.mark.parametrize("text", [
    "I'm gonna fucking kill you.",
    "I’ll kill you.",                                  # typed on a phone
    "Touch her again and you're dead.",
    "I'll break your arm.",
    "We're going to feed you to the dead.",
    "You'll pay for this.",
    "I'll end you.",
    "I'll put a bullet in your head.",
    "I'll beat the shit out of you.",
    "We'll kill all of you.",
    "Imma smash your face in.",
    "I'll slit your throat.",
])
def test_a_threat_however_it_is_put(text):
    assert firewall.classify_form(text) == F.THREAT


@pytest.mark.parametrize("text, form", [
    ("I'll never hurt you.", F.STATEMENT),
    ("I'm not going to hurt you.", F.STATEMENT),
    ("I will not let them hurt you.", F.STATEMENT),
    ("They'll kill you out there.", F.STATEMENT),          # a warning, not a threat
    ("I'll cut the rope for you.", F.STATEMENT),
    ("I'll cut your hair later.", F.STATEMENT),
    ("You're dead to me.", F.STATEMENT),
    ("You'll pay me back tomorrow?", F.QUESTION),
    ("I’ll give you two cans.", F.OFFER),
    ("Don’t move!", F.ORDER),
])
def test_not_a_threat(text, form):
    assert firewall.classify_form(text) == form


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def rel(w, a, b, axis):
    r = w.store.query_one(f"SELECT {axis} FROM relationships WHERE from_id = ? AND to_id = ?", (w.id(a), w.id(b)))
    return r[0] if r else 0


def lit(w):
    with w.store.transaction() as tx:
        space.change_place(tx, w.id("sales_floor"), {"light_level": 4}, "test", now(w), None, 0)


def say(w, who, to, words, at, *, armed=False):
    with w.store.transaction() as tx:
        ev = tx.commit_event(Event(type=EventType.SPEECH, writer="action.propagate", actor_id=w.id(who), at=at, turn_index=0,
                                   payload={"words": words, "volume": "normal", "to": [w.id(to)], "source_db": 60,
                                            "armed": armed}))
        perception.compile_aftermath(tx, w.id(to), [ev], at + 500, 0)
    return ev


def sweep(w, ev, at):
    with w.store.transaction() as tx:
        return cascade.sweep(tx, [ev], [r for r in w.canon.all("cascade") if r.id in RULES], at, 0)


def test_threatened_with_nothing_in_hand(scenario):
    """Owen, empty-handed in his words, to Alice: she trusts him less and holds it against him — not afraid: she has
    never seen him hurt anyone. Said again a minute later, it is the same threat."""
    w = scenario("metal_fence")
    lit(w)
    t = now(w)
    trust, fear, grudge = rel(w, "alice", "pc", "trust"), rel(w, "alice", "pc", "fear"), rel(w, "alice", "pc", "resentment")
    threat = say(w, "pc", "alice", "I'm gonna fucking kill you.", t)
    with w.store.transaction() as tx:
        assert cascade.select(tx, "threatened_to_their_face(trigger.event_id)", threat) == [w.id("alice")]
        assert cascade.select(tx, "threatened_by_the_violent(trigger.event_id)", threat) == []
    assert sorted(e.rule_cited for e in sweep(w, threat, t + 1000)) == ["CAS-089", "CAS-089"]
    assert rel(w, "alice", "pc", "trust") == max(-3, trust - 1)
    assert rel(w, "alice", "pc", "resentment") == min(3, grudge + 1)
    assert rel(w, "alice", "pc", "fear") == fear
    again = say(w, "pc", "alice", "You heard me. You're dead.", t + 60_000)
    with w.store.transaction() as tx:
        assert cascade.select(tx, "threatened_to_their_face(trigger.event_id)", again) == [], "once an hour"
    later = say(w, "pc", "alice", "I'll break your arm.", t + 3_700_000)
    with w.store.transaction() as tx:
        assert cascade.select(tx, "threatened_to_their_face(trigger.event_id)", later) == [w.id("alice")], "an hour on, again"


def test_kind_words_are_not_a_threat(scenario):
    w = scenario("metal_fence")
    lit(w)
    t = now(w)
    ev = say(w, "pc", "alice", "I'll never hurt you.", t)
    assert sweep(w, ev, t + 1000) == []


def test_from_someone_she_saw_hurt_a_person_it_frightens(scenario):
    """Alice saw Owen open Mara's arm; his threat after that, empty-handed, frightens her too."""
    w = scenario("metal_fence")
    lit(w)
    t = now(w)
    with w.store.transaction() as tx:
        st = tx.commit_event(Event(type=EventType.ACTION_START, writer="action.resolve", at=t, turn_index=0, actor_id=w.id("pc"),
                                   payload={"actor_id": w.id("pc"), "def_id": "strike_melee", "verb": "attack",
                                            "target_id": w.id("mara")}))
        hurt = bodies.apply_harm(tx, w.id("mara"), WoundSpec(Anatomy.ARM_L, WoundType.CUT, WoundSeverity.MINOR), t + 500,
                                 st.event_id, 0, w.rng)
        perception.compile_aftermath(tx, w.id("alice"), [st, *hurt], t + 1000, 0)
    fear = rel(w, "alice", "pc", "fear")
    threat = say(w, "pc", "alice", "You're next.  I'll cut you.", t + 30_000)
    with w.store.transaction() as tx:
        assert cascade.select(tx, "threatened_by_the_violent(trigger.event_id)", threat) == [w.id("alice")]
    sweep(w, threat, t + 31_000)
    assert rel(w, "alice", "pc", "fear") == min(3, fear + 1)


def test_at_gunpoint_it_is_both(scenario):
    """The same words with the Glock on her: afraid (CAS-038) and trusting him less (CAS-089); CAS-090 is for a bare
    hand only — the gun already frightened her."""
    w = scenario("metal_fence")
    lit(w)
    t = now(w)
    threat = say(w, "pc", "alice", "Hand it over or I'll shoot you.", t, armed=True)
    with w.store.transaction() as tx:
        assert cascade.select(tx, "threatened_to_their_face(trigger.event_id)", threat) == [w.id("alice")]
        assert cascade.select(tx, "threatened_by_the_violent(trigger.event_id)", threat) == []
    assert sorted(e.rule_cited for e in sweep(w, threat, t + 1000)) == ["CAS-038", "CAS-089", "CAS-089"]


def test_never_the_player_character(scenario):
    w = scenario("metal_fence")
    lit(w)
    t = now(w)
    threat = say(w, "mara", "pc", "Say that again and I'll gut you.", t)
    with w.store.transaction() as tx:
        assert cascade.select(tx, "threatened_to_their_face(trigger.event_id)", threat) == []
