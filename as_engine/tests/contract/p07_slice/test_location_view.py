"""Where you are, and the whole play view (P7). Rules UI-LOC-01, UI-SKULL-01, UI-CLARITY-01,
UI-REF-01, UI-SUG-01, UI-SUG-02 (narration/location.py describe, service/view.py build_view).
docs/as/10_UI.md §5 (word tables) and §6 (location templates).

The player always has a reliable, code-built description of where they are, built only from what
the PC perceives: the room as it is, the people the PC can see, the ways out the PC knows. Nobody
the PC has not perceived appears anywhere in the view, and no internal id ever reaches the page.
"""

from __future__ import annotations

import json
import re

import pytest

from as_engine.contracts.view import PlayView
from as_engine.mind import perception
from as_engine.narration.location import describe
from as_engine.service.view import build_view

pytestmark = pytest.mark.phase(7)

INTERNAL_ID = re.compile(r"\b(act|itm|plc|prt|anc|pct|prp|clm|epi|lop|ref|que|evt|tsk|wnd|dos|scn)_\d{6}\b")


def now(w):
    return w.store.query_one("SELECT now_ms FROM world_clock")[0]


def looked(w, local="pc"):
    """The PC's first look at the room (a standing view at the start time), then describe()."""
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id(local), now(w), 0)
        return describe(tx, w.id(local), now(w))


def test_the_sales_floor_described_by_code(scenario, fake):
    """UI-LOC-01 / 10 §6: the line templates, in order; no model call."""
    w = scenario("metal_fence")
    loc = looked(w)
    assert (loc.place_name, loc.area_name) == ("Sales floor", "")
    assert loc.description_lines == [
        "A large brick room, dim.",                      # 14 x 9 m (126 m², not twice as long as wide), brick, light 1
        "Wind pushes at the building.",                  # indoor + wind
        "There are a counter, a gap behind the counter and a front window here.",   # first three notable anchors
        "One other person is here.",                     # the PC sees Mara; Alice is hidden behind the counter
        "The gap behind the counter would stop a bullet.",   # best cover (3); no concealment-only anchor
    ]
    assert loc.noise_text == "quiet"
    assert fake.requests == []


def test_exits_say_what_the_pc_knows(scenario):
    """GEO-01 orthogonal state words; 'locked' only after the PC tried it; leads_to only for known places."""
    w = scenario("metal_fence")
    loc = looked(w)
    assert [(x.label, x.state_words, x.leads_to) for x in loc.exits] == [
        ("storeroom door", ["open"], "Stockroom"),
        ("office door", ["closed"], "Office"),
        ("front door", ["closed", "barricaded"], "Maple Street"),
        ("boarded front window", ["closed", "barricaded"], "Maple Street"),
    ], "the front door is locked, but nobody here has tried it"
    assert all(x.ref.startswith("x") for x in loc.exits)


def test_people_are_the_ones_the_pc_sees(scenario):
    """UI-SKULL-01: a person chip for every body in the PC's current view, named only if known."""
    w = scenario("metal_fence")
    loc = looked(w)
    assert [(p.label, p.known) for p in loc.people] == [("Mara", True)]
    nita = looked(w, "nita")
    labels = [p.label for p in nita.people]
    assert "the thin man who watches the back fence" in labels, "Nita knows him only by description"
    assert not any("Dale" in x for x in labels)


def test_describe_writes_nothing(scenario):
    w = scenario("metal_fence")
    with w.store.transaction() as tx:
        perception.compile_scene(tx, w.id("pc"), now(w), 0)
    n = w.store.query_one("SELECT COUNT(*) FROM events")[0]
    with w.store.transaction() as tx:
        describe(tx, w.id("pc"), now(w))
    assert w.store.query_one("SELECT COUNT(*) FROM events")[0] == n


def test_the_play_view_after_the_anchor_turn(metal_turn):
    """UI-SKULL-01, UI-CLARITY-01, UI-REF-01, UI-SUG-01/02 over the whole view model."""
    m = metal_turn
    w = m.w
    with w.store.transaction() as tx:
        v = build_view(tx, m.s)
    assert isinstance(v, PlayView) and v.turn_index == 1 and v.pc_name == "Owen Marsh" and v.alive
    text = json.dumps(v.model_dump(mode="json"))
    assert not INTERNAL_ID.search(text), "an internal id reached the page"
    for secret in ("Dale", "Pruitt", "thin man", "dumpster", "tall weeds"):
        assert secret not in text, f"the PC never perceived {secret!r}"
    assert (v.clock.day, v.clock.time_text, v.clock.part_of_day, v.clock.weather_text) == (18, "23:14", "night", "Windy")
    (gun,) = v.inventory.hands
    assert (gun.name, gun.detail, gun.condition_word) == ("Glock 19", "15 rounds", "pristine"), "14 in the magazine + 1 chambered"
    assert v.body.resolve.word == "steady" and v.body.impairment_word == "clear-headed"
    refs = m.s.extras["view_refs"]
    for p in v.location.people + v.people:
        assert refs[p.ref].startswith("act_")
    assert {p.label: p.last_seen_text for p in v.people}["Nita"] == "not seen yet"
    sugg = v.suggestions
    assert 1 <= len(sugg) <= 6 and sugg[-1].label == "Wait and watch"
    assert all(s.mode == "say" for s in sugg if s.label.startswith("Talk to"))
    smap = m.s.extras["suggestions"]
    assert set(smap) == {s.ref for s in sugg} and all("signature" in e or "remainder" in e for e in smap.values())


def test_a_suggestion_click_is_the_pcs_own_option(metal_turn):
    """UI-SUG-02: a chip maps to one of the PC's own bound options, re-validated at intake."""
    from slice_kit import play
    m = metal_turn
    w = m.w
    with w.store.transaction() as tx:
        v = build_view(tx, m.s)
    wait = v.suggestions[-1]
    sig = m.s.extras["suggestions"][wait.ref]["signature"]
    assert sig.startswith("observe_area:")
    out = play(m.s, "do", "", suggestion_ref=wait.ref)
    assert out.ok and out.turn_index == 2
    row = dict(w.store.query_one("SELECT * FROM player_inputs WHERE turn_index = 2"))
    assert (row["mode"], row["raw_text"], json.loads(row["mapped"])["signature"]) == ("suggestion", "Wait and watch", sig)
    stale = play(m.s, "do", "", suggestion_ref="s99")
    assert (stale.ok, stale.rejected_code) == (False, "suggestion_stale")
    assert w.store.query_one("SELECT turn_index FROM world_clock")[0] == 2, "a rejected input changes nothing"


def test_the_dice_receipt_names_a_defence_too(metal_turn):
    """service/view mechanics (P10 wording): one line per check the PC rolled this turn, in order —
    the defending side of an opposed check (def_id '<def>:defend') reads 'Resisting <what>'; 'full'
    adds the numbers."""
    from as_engine.contracts.events import Event, EventType
    m = metal_turn
    w = m.w
    pc = w.id("pc")
    T, at = w.store.query_one("SELECT turn_index, now_ms FROM world_clock")
    with w.store.transaction() as tx:
        for def_id, band, target, draw in (("grapple:defend", "fail", 4, 6), ("climb_obstacle", "cost", 6, 5)):
            tx.commit_event(Event(type=EventType.CHECK_RESOLVED, writer="action.resolve", at=at, turn_index=T,
                                  actor_id=pc, payload={"actor_id": pc, "def_id": def_id, "band": band, "target": target,
                                                        "draw": draw}))
        v = build_view(tx, m.s)
    assert v.mechanics.lines == ["Resisting grab: failure", "Climb over: success with a cost"]
    m.s.settings = m.s.settings.model_copy(update={"show_mechanics": "full"})
    with w.store.transaction() as tx:
        v = build_view(tx, m.s)
    assert v.mechanics.lines == ["Resisting grab: failure (needed 4 or less, rolled 6)",
                                 "Climb over: success with a cost (needed 6 or less, rolled 5)"]
