"""The guide's inputs (P8). Rules GUIDE-01..03, UI-SKULL-01 (service/guide.py).

The guide model is told only what the player can already see on screen, plus plain rules text
chosen by the words of the question.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.view import (
    BodyView,
    ClockView,
    ExitView,
    InventoryView,
    ItemView,
    LaneStatus,
    LanesView,
    LocationView,
    NeedView,
    PersonChip,
    PlayView,
    ResolveView,
    SeenThing,
    WoundView,
)
from as_engine.service.guide import GENERAL, GUIDE_TOPICS, MAX_FACTS, pc_facts, rules_for

pytestmark = pytest.mark.phase(8)

TOPIC = {name: GUIDE_TOPICS[i][1] for i, name in enumerate(
    ("checks", "wounds", "death", "stealth", "sound", "resolve", "needs", "time", "saving"))}


def test_rules_are_chosen_by_the_words_of_the_question():
    assert rules_for("How does bleeding work?") == [TOPIC["wounds"]]
    assert rules_for("If I hide, will they HEAR me?") == [TOPIC["stealth"], TOPIC["sound"]]
    assert rules_for("roll dice, bleed, die, sneak and save") == [TOPIC["checks"], TOPIC["wounds"], TOPIC["death"]], \
        "table order, at most three"
    assert rules_for("What should I do next?") == [GENERAL]
    assert rules_for("bleeding-edge") == [TOPIC["wounds"]], "words are runs of letters"


def view(**over):
    base = dict(
        run_id="owen_marsh_71a", turn_index=1, pc_name="Owen Marsh", alive=True,
        clock=ClockView(day=18, time_text="23:14", part_of_day="night", weather_text="Windy", light_text="Dim"),
        location=LocationView(place_name="Delgado's Market sales floor", area_name="Delgado's Market",
                              description_lines=["A long brick room, dim.", "Wind pushes at the building."],
                              can_see=[SeenThing(ref="i1", name="counter"), SeenThing(ref="i2", name="shelves", detail="half empty")],
                              people=[PersonChip(ref="p1", label="Mara", status_words=["armed"], known=True),
                                      PersonChip(ref="p2", label="an old woman", known=False)],
                              exits=[ExitView(ref="x1", label="Front door", state_words=["closed", "barricaded"], leads_to="unknown"),
                                     ExitView(ref="x2", label="Storeroom door", state_words=["open"], leads_to="Storeroom")],
                              dangers=["Something hit the back fence (you heard it)"], noise_text="noisy"),
        inventory=InventoryView(hands=[ItemView(ref="i3", name="Glock 19", qty=1, condition_word="good", detail="15 rounds")],
                                carried_mass_kg=6.2, load_word="light"),
        body=BodyView(wounds=[WoundView(where="left forearm", what="cut wound", severity_word="minor", bleeding_word="oozing",
                                        treated=False)],
                      needs=[NeedView(name="Thirst", level=2, word="noticeable"), NeedView(name="Hunger", level=1, word="fine")],
                      impairment_word="slowed", resolve=ResolveView(cur=4, max=6, word="shaken")),
        lanes=LanesView(A=LaneStatus(label="Main model", ok=True), B=LaneStatus(label="Second model", ok=True)),
    )
    base.update(over)
    return PlayView(**base)


def test_pc_facts_come_only_from_the_view():
    assert pc_facts(view(), "Metal crashed somewhere out back.") == [
        "Where you are: Delgado's Market sales floor, Delgado's Market.",
        "A long brick room, dim.",
        "Wind pushes at the building.",
        "You can see: counter, shelves (half empty).",
        "Mara is here (armed).",
        "an old woman is here.",
        "Way out: Front door (closed, barricaded).",
        "Way out: Storeroom door (open), leads to Storeroom.",
        "Danger you know about: Something hit the back fence (you heard it).",
        "In your hands: Glock 19 (15 rounds).",
        "Wound: minor cut wound on the left forearm, bleeding: oozing.",
        "Thirst: noticeable.",
        "You feel slowed.",
        "Resolve: 4 of 6 (shaken).",
        "What just happened: Metal crashed somewhere out back.",
    ]


def test_pc_facts_leave_out_what_is_not_there():
    v = view(location=LocationView(place_name="Alley", area_name="", description_lines=["A narrow street, pitch dark."],
                                   noise_text="quiet"),
             body=BodyView(impairment_word="clear-headed", resolve=ResolveView(cur=6, max=6, word="steady")),
             inventory=InventoryView(carried_mass_kg=0, load_word="light"))
    assert pc_facts(v, None) == ["Where you are: Alley.", "A narrow street, pitch dark.", "Resolve: 6 of 6 (steady)."]


def test_pc_facts_are_capped():
    many = [SeenThing(name=f"thing {i}") for i in range(3)]
    people = [PersonChip(ref=f"p{i}", label=f"person {i}", known=False) for i in range(40)]
    v = view(location=LocationView(place_name="Yard", area_name="", description_lines=["A yard."], can_see=many,
                                   people=people, noise_text="quiet"))
    facts = pc_facts(v, None)
    assert len(facts) == MAX_FACTS and facts[-1] == "person 26 is here."
