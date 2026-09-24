"""Everybody has a breaking point (P5, the owner's H1). Rules TEMPER-01..05, TEMPER-07
(mind/temper.py; contracts/dossier.py Temper; kernel/schema.sql tempers).

People here are smart, but human smart: strain wears them down, anger at one person builds and
fades, a grudge keeps it warm, and past the breaking point a person snaps — unless they swallow it,
which costs them nerve. The world is a bar room (a dict scenario): Reggie Tate, a big man with a
short enough fuse who swings when he blows, a metre from the player; Irene and Tess, who is like a
daughter to her, at a table; a stranger, Cal, by the door.
"""

from __future__ import annotations

import copy
import json

import pytest

from as_engine.contracts.dossier import Temper
from as_engine.contracts.events import Event, EventType
from as_engine.contracts.settings import RulesConfig, TemperRules
from as_engine.action import effects
from as_engine.mind import mind as mindmod, perception, temper
from as_engine.mind.temper import Outburst, Provocation
from as_engine.physical import bodies
from as_engine.physical.bodies import WoundSpec
from as_engine.testing.scenario import load_scenario

pytestmark = pytest.mark.phase(5)

MIN = 60_000

BAR = {
    "schema": "as.scenario.v1", "name": "bar_room", "seed": 44, "start": {"day": 3100, "time": "21:00"},
    "places": [{"id": "bar", "name": "Bar room", "material": "brick", "light": 3, "width_m": 14, "depth_m": 8}],
    "bodies": [
        {"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "bar", "x": 2, "y": 4},
        {"id": "reggie", "dossier": "core:actor/reggie_tate", "place": "bar", "x": 3, "y": 4, "resolve": 0},
        {"id": "irene", "dossier": "core:actor/irene_kowalski", "place": "bar", "x": 6, "y": 4},
        {"id": "tess", "dossier": "core:actor/tess_nakamura", "place": "bar", "x": 7, "y": 4},
        {"id": "cal", "stub": {"name": "Cal Hobbs", "age": 30, "sex": "male"}, "place": "bar", "x": 12, "y": 2},
    ],
    "relationships": [{"from": "irene", "to": "tess", "kind": "friend", "trust": 2, "affection": 3}],
}


@pytest.fixture
def bar(fixture_packs, core_pack_dir):
    worlds = []

    def _load(rules=None, change=None):
        spec = copy.deepcopy(BAR)
        if change is not None:
            change(spec)
        w = load_scenario(spec, packs_root=fixture_packs, core_pack_dir=core_pack_dir, rules=rules)
        worlds.append(w)
        return w

    yield _load
    for w in worlds:
        w.store.close()


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def commit(w, ev):
    with w.store.transaction() as tx:
        return tx.commit_event(ev)


def say(w, who, words, to, at):
    return commit(w, Event(type=EventType.SPEECH, writer="action.propagate", actor_id=w.id(who), at=at, turn_index=0,
                           payload={"words": words, "volume": "normal", "to": [w.id(x) for x in to], "source_db": 60}))


def act(w, who, def_id, target, at):
    return commit(w, Event(type=EventType.ACTION_START, writer="action.resolve", actor_id=w.id(who), at=at, turn_index=0,
                           payload={"actor_id": w.id(who), "def_id": def_id, "verb": "attack", "target_id": w.id(target),
                                    "destination_id": None, "item_id": None, "est_duration_s": 1.0, "visible": True,
                                    "seen": effects.SEEN.get(def_id), "label": def_id, "goal": ""}))


def hit(w, who, target, at):
    start = act(w, who, "punch", target, at)
    with w.store.transaction() as tx:
        bodies.apply_harm(tx, w.id(target), WoundSpec("chest", "blunt", "minor", 0), at, start.event_id, 0, w.rng)
    return start


def look(w, holder, at):
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id(holder), at, 0)


def provoked(w, holder, at):
    with w.store.transaction() as tx:
        return temper.provocations(tx, w.id(holder), 0, at)


def take_in(w, holder, at):
    with w.store.transaction() as tx:
        return temper.take_in(tx, w.rng, w.id(holder), 0, at)


def strain(w, who, delta, at):
    from as_engine.mind import actor
    with w.store.transaction() as tx:
        c = tx.commit_event(Event(type=EventType.OVERRIDE, writer="audit", at=at, turn_index=0, payload={"what": "test"}))
        actor.adjust_stress(tx, w.id(who), delta, c.event_id, at, 0)


def events(w, type_):
    return [dict(r, payload=json.loads(r["payload"])) for r in w.store.query("SELECT * FROM events WHERE type = ? ORDER BY seq",
                                                                             (type_,))]


# --------------------------------------------------------------------------- TEMPER-01/02
def test_how_each_person_breaks_comes_from_them(bar, canon):
    w = bar()
    assert temper.temper_of(w.store, w.id("reggie")) == canon.get("core:actor/reggie_tate").temper
    assert temper.temper_of(w.store, w.id("reggie")).outlet == "fists"
    assert temper.temper_of(w.store, w.id("cal")) == Temper(), "a stranger with no temper on record: the middle of the road"


def test_strain_shortens_the_fuse(bar):
    w = bar()
    t = now(w)
    assert temper.threshold(w.store, w.id("reggie")) == 6
    strain(w, "reggie", 9, t)
    assert temper.threshold(w.store, w.id("reggie")) == 3
    assert temper.threshold(w.store, w.id("irene")) == 8, "it takes a lot to make Irene lose it"
    strain(w, "irene", 10, t)
    assert temper.threshold(w.store, w.id("irene")) == 5


def test_anger_fades_but_a_grudge_keeps_it_warm(bar):
    w = bar()
    t = now(w)
    with w.store.transaction() as tx:
        temper.provoke(tx, w.id("irene"), w.id("cal"), "insulted", "test:1", t, 0)
    row = w.store.query_one("SELECT heat, updated_at, last_kind FROM tempers WHERE holder_id = ? AND toward_id = ?",
                            (w.id("irene"), w.id("cal")))
    assert tuple(row) == (2, t, "insulted")
    heat = lambda at: temper.heat(w.store, w.id("irene"), w.id("cal"), at)  # noqa: E731
    assert (heat(t + 59 * MIN), heat(t + 60 * MIN), heat(t + 120 * MIN), heat(t + 600 * MIN)) == (2, 1, 0, 0)
    with w.store.transaction() as tx:
        mindmod.open_loop(tx, w.id("irene"), "grudge", "He called me names.", [w.id("cal")], 1, "test:1", t, 0)
    assert heat(t + 600 * MIN) == 1
    assert temper.heat(w.store, w.id("irene"), w.id("pc"), t) == 0


# --------------------------------------------------------------------------- TEMPER-03 what provokes
@pytest.mark.parametrize("words, kinds", [
    ("You're a useless bastard.", ["insulted"]),
    ("Shut up, you useless bastard.", ["ordered_about", "insulted"]),
    ("Back off or I'll hurt you.", ["threatened"]),
    ("Evening. Cold out there?", []),
])
def test_what_is_said_to_you(bar, words, kinds):
    w = bar()
    t = now(w)
    ev = say(w, "pc", words, ["reggie"], t)
    look(w, "reggie", t)
    assert provoked(w, "reggie", t) == [Provocation(w.id("pc"), k, ev.event_id) for k in kinds]


def test_an_order_from_someone_you_answer_to_is_not_being_ordered_about(bar):
    """Reggie answers to the player here (accepted_authority): 'Sit down.' from him is an order, not a
    provocation; the same words from a stranger are."""
    w = bar(change=lambda s: s["bodies"][1].update(accepted_authority=["pc"]))
    t = now(w)
    say(w, "pc", "Sit down.", ["reggie"], t)
    ev = say(w, "cal", "Sit down.", ["reggie"], t + 1000)
    look(w, "reggie", t + 1000)
    assert provoked(w, "reggie", t + 1000) == [Provocation(w.id("cal"), "ordered_about", ev.event_id)]


def test_an_insult_is_a_whole_word(bar):
    """'prick' is an insult; 'prickly' is not; 'shut up' counts wherever it stands."""
    w = bar()
    t = now(w)
    say(w, "pc", "You're a prickly one tonight.", ["reggie"], t)
    look(w, "reggie", t)
    assert provoked(w, "reggie", t) == []
    ev = say(w, "pc", "SHUT UP, prick.", ["reggie"], t + 1000)
    look(w, "reggie", t + 1000)
    assert [p.kind for p in provoked(w, "reggie", t + 1000)] == ["ordered_about", "insulted"]
    assert all(p.event_id == ev.event_id for p in provoked(w, "reggie", t + 1000))


def test_words_meant_for_someone_else_are_not_yours(bar):
    w = bar()
    t = now(w)
    say(w, "pc", "You're a useless bastard.", ["cal"], t)
    look(w, "reggie", t)
    assert provoked(w, "reggie", t) == []


def test_what_is_done_to_you_and_yours(bar):
    w = bar()
    t = now(w)
    shove = act(w, "pc", "shove", "reggie", t)
    blow = hit(w, "pc", "reggie", t + 1000)
    hurt = hit(w, "cal", "tess", t + 2000)
    look(w, "reggie", t + 2000)
    look(w, "irene", t + 2000)
    [felt] = [e for e in events(w, "HARM") if e["payload"]["body_id"] == w.id("reggie")]
    assert felt["cause_event_id"] == blow.event_id
    assert provoked(w, "reggie", t + 2000) == [Provocation(w.id("pc"), "shoved", shove.event_id),
                                                 Provocation(w.id("pc"), "struck", felt["event_id"])], \
        "the blow is felt (a tactile percept of the HARM), and who threw it is seen"
    [harm] = [e for e in events(w, "HARM") if e["payload"]["body_id"] == w.id("tess")]
    assert provoked(w, "irene", t + 2000) == [Provocation(w.id("cal"), "harmed_bonded", harm["event_id"])]
    assert hurt is not None


def test_a_blow_wears_you_down_a_shove_does_not(bar):
    """TEMPER-04: R.stress_from — struck adds 1 to stress (caused by the anger it gave), shoved nothing.
    (Irene: her breaking point of 8 is far off, so nothing else moves her stress.)"""
    w = bar()
    t = now(w)
    act(w, "pc", "shove", "irene", t)
    look(w, "irene", t)
    take_in(w, "irene", t)
    assert w.store.query_one("SELECT stress FROM actors WHERE actor_id = ?", (w.id("irene"),))[0] == 0
    hit(w, "pc", "irene", t + 1000)
    look(w, "irene", t + 1000)
    take_in(w, "irene", t + 1000)
    assert w.store.query_one("SELECT stress FROM actors WHERE actor_id = ?", (w.id("irene"),))[0] == 1
    [struck] = [e for e in events(w, "TEMPER_CHANGE") if e["payload"]["kind"] == "struck"]
    [worn] = [e for e in events(w, "RESOLVE_CHANGE") if e["payload"].get("stress_delta") == 1]
    assert worn["cause_event_id"] == struck["event_id"]


# --------------------------------------------------------------------------- TEMPER-04/05
def test_each_thing_provokes_once_and_it_builds(bar):
    w = bar()
    t = now(w)
    say(w, "pc", "You're a useless bastard.", ["reggie"], t)
    look(w, "reggie", t)
    assert take_in(w, "reggie", t) is None and take_in(w, "reggie", t) is None
    assert temper.heat(w.store, w.id("reggie"), w.id("pc"), t) == 2, "the same words count once"
    [ch] = events(w, "TEMPER_CHANGE")
    assert (ch["writer"], ch["actor_id"], ch["payload"]) == ("mind.temper", w.id("reggie"), {
        "holder_id": w.id("reggie"), "toward_id": w.id("pc"), "kind": "insulted", "event_id": ch["cause_event_id"],
        "heat": 2})


def test_disrespect_the_wrong_man_too_much_and_he_swings(bar):
    """Reggie at the end of his rope (stress 9: his breaking point is 3) with no nerve left to
    swallow it: the first insult builds, the second breaks him."""
    w = bar()
    t = now(w)
    strain(w, "reggie", 9, t)
    say(w, "pc", "You're a useless bastard.", ["reggie"], t)
    look(w, "reggie", t)
    assert take_in(w, "reggie", t) is None
    second = say(w, "pc", "You're a useless bastard, and everybody knows it.", ["reggie"], t + 5000)
    look(w, "reggie", t + 5000)
    out = take_in(w, "reggie", t + 5000)
    assert out == Outburst(w.id("pc"), "fists", second.event_id)
    [inv] = events(w, "INVOLUNTARY")
    assert (inv["writer"], inv["actor_id"], inv["cause_event_id"], inv["payload"]) == (
        "mind.temper", w.id("reggie"), second.event_id,
        {"actor_id": w.id("reggie"), "kind": "outburst", "outlet": "fists", "toward_id": w.id("pc")})
    assert temper.heat(w.store, w.id("reggie"), w.id("pc"), t + 5000) == 2, "4, halved: he let some of it out"
    assert w.store.query_one("SELECT stress FROM actors WHERE actor_id = ?", (w.id("reggie"),))[0] == 8
    [loop] = [dict(r) for r in w.store.query("SELECT * FROM open_loops WHERE holder_id = ? AND kind = 'grudge'",
                                               (w.id("reggie"),))]
    assert json.loads(loop["subject_ids"]) == [w.id("pc")] and loop["strength"] == 2
    rel = w.store.query_one("SELECT resentment FROM relationships WHERE from_id = ? AND to_id = ?", (w.id("reggie"), w.id("pc")))
    assert rel is not None and rel[0] == 1


def test_the_last_one_to_push_him_gets_it(bar):
    """Two people threaten him in the same moment, equally hard: he turns on the one who did it last."""
    w = bar()
    t = now(w)
    strain(w, "reggie", 9, t)
    say(w, "cal", "Back off or I'll hurt you.", ["reggie"], t)
    last = say(w, "pc", "Back off or I'll hurt you.", ["reggie"], t + 500)
    look(w, "reggie", t + 500)
    out = take_in(w, "reggie", t + 500)
    assert out == Outburst(w.id("pc"), "fists", last.event_id)


def test_swallowing_it_costs_nerve(bar):
    w = bar(rules=RulesConfig(temper=TemperRules(hold_per_resolve=1.0, hold_max=1.0)),
            change=lambda s: s["bodies"][1].update(resolve=3))
    t = now(w)
    strain(w, "reggie", 9, t)
    say(w, "pc", "Shut up, you useless bastard.", ["reggie"], t)
    look(w, "reggie", t)
    assert take_in(w, "reggie", t) is None, "he holds it in"
    assert events(w, "INVOLUNTARY") == []
    [drain] = [e for e in events(w, "RESOLVE_CHANGE") if e["payload"].get("reason") == "held_temper"]
    assert drain["actor_id"] == w.id("reggie") and drain["payload"]["delta"] == -1


def test_the_player_is_never_made_to_snap(bar):
    """Owen at the end of his rope with no nerve left (resolve 0) — well past his breaking point —
    and still nothing is done with his hands: not a snap, not even the cost of holding it in."""
    w = bar(change=lambda s: s["bodies"][0].update(resolve=0))
    t = now(w)
    strain(w, "pc", 10, t)
    for k in range(3):
        say(w, "reggie", "You're a useless bastard.", ["pc"], t + k * 1000)
    look(w, "pc", t + 3000)
    assert take_in(w, "pc", t + 3000) is None
    assert temper.heat(w.store, w.id("pc"), w.id("reggie"), t + 3000) == 6, "the anger is real and on record"
    assert temper.heat(w.store, w.id("pc"), w.id("reggie"), t + 3000) >= temper.threshold(w.store, w.id("pc"))
    assert events(w, "INVOLUNTARY") == []
    assert not [e for e in events(w, "RESOLVE_CHANGE") if e["payload"].get("reason") == "held_temper"]


# --------------------------------------------------------------------------- TEMPER-07 / LOOP-07
def test_an_old_grudge_makes_it_quicker_and_deeper(bar):
    """Reggie already holds a grudge against the player (strength 1): it keeps his anger warm, so
    the first insult on a strained night is enough — and the grudge deepens instead of doubling."""
    w = bar()
    t = now(w)
    with w.store.transaction() as tx:
        mindmod.open_loop(tx, w.id("reggie"), "grudge", "He has a mouth on him.", [w.id("pc")], 1, "test:g", t, 0)
    strain(w, "reggie", 9, t)
    say(w, "pc", "You're a useless bastard.", ["reggie"], t)
    look(w, "reggie", t)
    out = take_in(w, "reggie", t)
    assert out is not None and out.outlet == "fists", "1 (the grudge) + 2 reaches his breaking point of 3"
    loops = [dict(r) for r in w.store.query("SELECT * FROM open_loops WHERE holder_id = ? AND kind = 'grudge'", (w.id("reggie"),))]
    assert len(loops) == 1 and loops[0]["strength"] == 2
    [deeper] = events(w, "LOOP_STRENGTH")
    [inv] = events(w, "INVOLUNTARY")
    assert (deeper["writer"], deeper["cause_event_id"], deeper["payload"]) == (
        "mind.mind", inv["event_id"], {"loop_id": loops[0]["loop_id"], "holder_id": w.id("reggie"), "old": 1, "new": 2})


def test_a_grudge_deepens_until_it_is_never_forgotten(bar):
    """LOOP-07: strengthen_loop moves an open loop's strength within 1..3; at the bound nothing is
    committed; a closed or missing loop is an error."""
    w = bar()
    t = now(w)
    with w.store.transaction() as tx:
        lid = mindmod.open_loop(tx, w.id("irene"), "grudge", "She shorted me.", [w.id("tess")], 2, "test:g", t, 0)
        ev = mindmod.strengthen_loop(tx, lid, 1, None, t, 0)
        assert ev.type == EventType.LOOP_STRENGTH and ev.payload["new"] == 3
        assert mindmod.strengthen_loop(tx, lid, 1, None, t, 0) is None
        assert mindmod.strengthen_loop(tx, lid, -5, None, t, 0).payload["new"] == 1
        mindmod.close_loop(tx, lid, "abandoned", None, t, 0)
        with pytest.raises(ValueError):
            mindmod.strengthen_loop(tx, lid, 1, None, t, 0)
        with pytest.raises(ValueError):
            mindmod.strengthen_loop(tx, "olp_999999", 1, None, t, 0)
