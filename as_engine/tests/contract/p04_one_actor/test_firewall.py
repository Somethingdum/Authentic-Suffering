"""The Request Firewall (P4). Rules WILL-00..10 (mind/firewall.py).

A request never becomes an action: it is an utterance the receiver perceives, labelled with the
form and standing AS THE RECEIVER classifies them, and the receiver chooses what to do.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.common import ResponseClass, Standing, UtteranceForm, Verb
from as_engine.mind import firewall
from as_engine.mind.affordance import BoundAffordance

pytestmark = pytest.mark.phase(4)

F = UtteranceForm


# --------------------------------------------------------------------------- form (WILL-10)
@pytest.mark.parametrize("text,form", [
    ("Could you hand me that hammer?", F.REQUEST),
    ("Please stay here.", F.REQUEST),                  # REQUEST is checked before the imperative
    ("Help me with this window", F.REQUEST),
    ("Open the door.", F.ORDER),
    ("Mara, stay where you are.", F.ORDER),            # a leading name + comma is skipped
    ("Quiet.", F.ORDER),
    ("Don't move!", F.ORDER),
    ("Give me the gun or I'll shoot.", F.THREAT),
    ("Last warning.", F.THREAT),
    ("I'll give you two cans for the hammer.", F.OFFER),
    ("I'll trade you the lighter.", F.OFFER),
    ("Thanks for your help.", F.STATEMENT),            # 'for your' alone is not an offer
    ("Who else is in here?", F.QUESTION),
    ("It's getting dark.", F.STATEMENT),
    ("", F.STATEMENT),                                 # TONE_ONLY words
])
def test_classify_form(text, form):
    assert firewall.classify_form(text) == form


def test_an_imperative_at_gunpoint_is_a_threat():
    assert firewall.classify_form("Open the door.", weapon_pointed_at_receiver=True) == F.THREAT
    assert firewall.classify_form("Who are you?", weapon_pointed_at_receiver=True) == F.QUESTION


def test_effective_form():
    assert firewall.effective_form(F.ORDER, Standing.VALID_ORDER) == F.ORDER
    for s in (Standing.PEER, Standing.STRANGER, Standing.CLAIMED_AUTHORITY, Standing.SUBORDINATE, Standing.HOSTILE):
        assert firewall.effective_form(F.ORDER, s) == F.DEMAND
    assert firewall.effective_form(F.REQUEST, Standing.HOSTILE) == F.REQUEST


# --------------------------------------------------------------------------- standing (WILL-04)
def test_standing_comes_from_the_receivers_record(scenario):
    w = scenario("request_firewall")
    mara, ray, pc, eli = (w.id(x) for x in ("mara", "ray", "pc", "eli"))
    with w.store.transaction() as tx:
        assert firewall.classify_standing(tx, ray, mara, "Keep boarding.") == Standing.VALID_ORDER
        assert firewall.classify_standing(tx, pc, mara, "Put the hammer down.") == Standing.STRANGER
        assert firewall.classify_standing(tx, pc, mara, "I'm in charge here. Put it down.") == Standing.CLAIMED_AUTHORITY
        assert firewall.classify_standing(tx, eli, mara, "Mom?") == Standing.PEER
        # Mara accepts Ray's authority, so to Ray she is a subordinate speaking
        assert firewall.classify_standing(tx, mara, ray, "Stay by the door.") == Standing.SUBORDINATE
        # claims never create authority: Ray saying it changes nothing, the PC saying it is only a claim
        assert firewall.classify_standing(tx, ray, mara, "That's an order.") == Standing.VALID_ORDER


def _hostile_world(fixture_packs, core_pack_dir, **rel):
    from as_engine.testing.scenario import load_scenario

    return load_scenario({
        "schema": "as.scenario.v1", "name": "hostile", "seed": 3, "start": {"day": 30, "time": "12:00"},
        "places": [{"id": "room", "name": "Room", "anchors": [{"id": "a", "name": "corner", "x": 1, "y": 1}]}],
        "bodies": [{"id": "pc", "dossier": "core:pc/owen_marsh", "controller": "human", "place": "room", "anchor": "a"},
                   {"id": "mara", "dossier": "core:actor/mara_voss", "place": "room", "x": 3, "y": 3,
                    "accepted_authority": ["pc"]}],
        "relationships": [{"from": "mara", "to": "pc", **rel}],
        "knows": [{"holder": "mara", "subject": "pc", "name": "Owen"}],
    }, packs_root=fixture_packs, core_pack_dir=core_pack_dir)


@pytest.mark.parametrize("rel", [{"trust": -2}, {"fear": 2}])
def test_hostility_beats_everything(fixture_packs, core_pack_dir, rel):
    """Even an accepted authority is HOSTILE once the receiver distrusts (<= -2) or fears (>= 2) them."""
    w = _hostile_world(fixture_packs, core_pack_dir, **rel)
    try:
        with w.store.transaction() as tx:
            assert firewall.classify_standing(tx, w.id("pc"), w.id("mara"), "Open it.") == Standing.HOSTILE
    finally:
        w.store.close()


def test_mild_distrust_is_not_hostility(fixture_packs, core_pack_dir):
    w = _hostile_world(fixture_packs, core_pack_dir, trust=-1, fear=1)
    try:
        with w.store.transaction() as tx:
            assert firewall.classify_standing(tx, w.id("pc"), w.id("mara"), "Open it.") == Standing.VALID_ORDER
    finally:
        w.store.close()


# --------------------------------------------------------------------------- signature (WILL-08)
ENT = {"the window being boarded": "anc_000001", "window": "anc_000001", "front door": "prt_000001",
       "door": "anc_000003", "hammer": "itm_000002", "claw hammer": "itm_000002", "eli": "act_000003"}


@pytest.mark.parametrize("text,sig", [
    ("Could you guard the window, please?", "guard_anchor:anc_000001"),
    ("Could you please open the front door?", "open_portal:prt_000001"),   # politeness stripped repeatedly
    ("Mara, open the front door.", "open_portal:prt_000001"),              # leading name dropped
    ("Close the door.", "close_portal:anc_000003"),                        # longest key contained: 'door'
    ("Open the cellar.", "open_portal:*"),                                 # nothing known by that name
    ("Give me the hammer.", "give_item:act_000009"),                       # {speaker}
    ("Hand it over!", "give_item:act_000009"),
    ("Put the claw hammer down.", "drop_item:*"),
    ("Come with me.", "follow_body:act_000009"),
    ("Get out.", "leave_place:*"),
    ("Shut up!", "wait_here:*"),
    ("Look at the window.", "watch_target:anc_000001"),
    ("What time is it?", "*:*"),
])
def test_request_signature(text, sig):
    assert firewall.request_signature(text, "act_000009", "act_000002", ENT) == sig


def test_the_same_ask_gets_the_same_signature():
    a = firewall.request_signature("Please, open the front door!", "act_000009", "act_000002", ENT)
    b = firewall.request_signature("open the FRONT door", "act_000009", "act_000002", ENT)
    assert a == b == "open_portal:prt_000001"


# --------------------------------------------------------------------------- response (WILL-09)
def opt(def_id, verb=Verb.MANIPULATE, target=None, dest=None, item=None, cost=None):
    return BoundAffordance(def_id=def_id, verb=verb, label=def_id, ui_label=def_id, target_id=target,
                           destination_id=dest, item_id=item, cost_note=cost)


def classify(sig, chosen, speech=None, resolve_cur=3, form=F.REQUEST, block=False, drained=False, steps_toward=frozenset()):
    return firewall.classify_response(sig, chosen, speech, resolve_cur, form, entrenched_block=block,
                                      resolve_drained_this_turn=drained, steps_toward=steps_toward)


def test_compliance_classes():
    door = opt("open_portal", target="prt_000001")
    assert classify("open_portal:prt_000001", door) == ResponseClass.READY_COMPLIANCE
    assert classify("open_portal:*", door) == ResponseClass.READY_COMPLIANCE, "'*' target matches any"
    assert classify("open_portal:prt_000001", door, drained=True) == ResponseClass.RELUCTANT_COMPLIANCE
    costly = opt("open_portal", target="prt_000001", cost="It means leaving your post at the front window.")
    assert classify("open_portal:prt_000001", costly) == ResponseClass.RELUCTANT_COMPLIANCE
    assert classify("open_portal:prt_000001", door, resolve_cur=0, form=F.THREAT) == ResponseClass.COERCED_COMPLIANCE
    assert classify("open_portal:prt_000001", door, resolve_cur=1, form=F.THREAT) == ResponseClass.READY_COMPLIANCE
    walk = opt("guard_anchor", verb=Verb.GUARD, dest="anc_000001")
    assert classify("guard_anchor:anc_000001", walk) == ResponseClass.READY_COMPLIANCE, "destination counts"


def test_refusal_classes():
    other = opt("keep_working", verb=Verb.CONTINUE_TASK)
    sig = "drop_item:*"
    assert classify(sig, other) == ResponseClass.REFUSAL
    assert classify(sig, other, speech="No.") == ResponseClass.REFUSAL
    assert classify(sig, other, speech="Yeah, okay, in a second.") == ResponseClass.DEFERRED_ASSENT
    assert classify(sig, other, speech="I'll do it.") == ResponseClass.UNRESOLVED_ASSENT
    assert classify(sig, other, speech="Yesterday you said the same.") == ResponseClass.REFUSAL, "'yes' is a whole word"
    assert classify(sig, other, speech="I'll give you the nails instead.") == ResponseClass.COUNTER_OFFER
    assert classify(sig, other, block=True, speech="Sure.") == ResponseClass.ENTRENCHED_REFUSAL


def test_an_unreadable_ask_is_never_complied_with_by_accident():
    """'*:*' matches nothing — not even an option whose def happens to be anything."""
    for chosen in (opt("wait_here", verb=Verb.WAIT), opt("open_portal", target="prt_000001")):
        assert classify("*:*", chosen) == ResponseClass.REFUSAL


def test_a_yes_is_not_a_lie_by_itself():
    """WILL-09 (AC09): a yes and something else is preparation, a condition, a delay, a question back
    or simply unresolved — never FALSE_COMPLIANCE, which nothing produces any more."""
    sig = "open_portal:prt_000001"
    work = opt("keep_working", verb=Verb.CONTINUE_TASK)
    walk = opt("move_to_anchor", verb=Verb.MOVE, dest="anc_000004")
    assert classify(sig, work, speech="Okay, what exactly do you mean?") == ResponseClass.CLARIFYING
    assert classify(sig, work, speech="Why?") == ResponseClass.CLARIFYING
    assert classify(sig, work, speech="Yes, after I finish this.") == ResponseClass.DEFERRED_ASSENT
    assert classify(sig, work, speech="Sure, once the cans are counted.") == ResponseClass.DEFERRED_ASSENT
    assert classify(sig, walk, speech="Okay.", steps_toward=frozenset({"anc_000004"})) == ResponseClass.PREPARING
    assert classify(sig, walk, speech="Okay.") == ResponseClass.UNRESOLVED_ASSENT, "a walk somewhere else"
    assert classify(sig, work, speech="Sure.") == ResponseClass.UNRESOLVED_ASSENT
    assert classify(sig, work, speech="Yes, and I'll give you the nails for it.") == ResponseClass.UNRESOLVED_ASSENT
    assert classify(sig, work, speech="I'll give you the nails instead.") == ResponseClass.COUNTER_OFFER
    assert classify(sig, work) == ResponseClass.REFUSAL


def test_open_the_door_means_the_door_guard_it_means_where_you_stand():
    """WILL-08 (B5 fix): a door and the anchors at it often share a name; the kind the ask acts on
    decides which one it means."""
    ents = {"back door": "anc_000007", "anchor|back door": "anc_000007", "portal|back door": "prt_000003"}
    assert firewall.request_signature("Open the back door.", "act_000001", "act_000002", ents) == "open_portal:prt_000003"
    assert firewall.request_signature("Close the back door.", "act_000001", "act_000002", ents) == "close_portal:prt_000003"
    assert firewall.request_signature("Guard the back door.", "act_000001", "act_000002", ents) == "guard_anchor:anc_000007"
    assert firewall.request_signature("Open the back door.", "act_000001", "act_000002", {"back door": "prt_000003"}) == \
        "open_portal:prt_000003", "plain keys still work"
