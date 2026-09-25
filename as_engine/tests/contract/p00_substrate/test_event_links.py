"""An event can have several causes (P0, Actor v2 B5c — fidelity C10). Rule STORE-12
(kernel/store.py Tx.commit_event; kernel/events.py causes, effects; contracts/events.py EventLink).

cause_event_id stays the primary parent; ``links`` name the other events that contributed, or the
ask an answer replies to. They are stored with the event, read back with it, checked before anything
is written, and replay keeps them.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.events import LINK_ROLES, Event, EventLink, EventType, WriteOp, WriteRecord
from as_engine.kernel import events
from as_engine.kernel.errors import StoreError
from as_engine.kernel.store import Store

pytestmark = pytest.mark.phase(0)


def ev(cause=None, links=(), at=0, zone=None):
    writes = [WriteRecord(op=WriteOp.INSERT, table="zones", values={"zone_id": zone, "name": zone, "kind": "rural",
                                                                     "danger": {}})] if zone else []
    return Event(type=EventType.PLACE_DISCOVERED, writer="physical.space", at=at, turn_index=0, cause_event_id=cause,
                 links=list(links), writes=writes)


def three(store):
    """A shortage-like outcome of three causes: the first is the parent, the other two contribute."""
    with store.transaction() as tx:
        a = tx.commit_event(ev(at=1)).event_id
        b = tx.commit_event(ev(at=2)).event_id
        c = tx.commit_event(ev(at=3)).event_id
        out = tx.commit_event(ev(cause=a, links=[EventLink(event_id=c, role="contributed"),
                                                 EventLink(event_id=b, role="contributed")], at=4)).event_id
    return a, b, c, out


def test_the_roles():
    assert LINK_ROLES == ("contributed", "answered")


def test_links_are_kept_with_the_event_in_their_order():
    s = Store.memory(run_id="r", seed=1)
    a, b, c, out = three(s)
    e = events.get(s, out)
    assert e.cause_event_id == a
    assert [(x.event_id, x.role) for x in e.links] == [(c, "contributed"), (b, "contributed")]
    assert events.causes(s, out) == [(a, "primary"), (c, "contributed"), (b, "contributed")]
    assert events.causes(s, a) == []
    assert [x.event_id for x in events.cause_chain(s, out)] == [out, a], "the chain still follows the parent"
    s.close()


def test_what_an_event_caused_whichever_way_it_is_named():
    s = Store.memory(run_id="r", seed=1)
    a, b, c, out = three(s)
    with s.transaction() as tx:
        reply = tx.commit_event(ev(cause=c, links=[EventLink(event_id=b, role="answered")], at=5)).event_id
    assert [x.event_id for x in events.effects(s, b)] == [out, reply]
    assert [x.event_id for x in events.effects(s, c)] == [out, reply], "each once, by seq"
    assert [x.event_id for x in events.effects(s, a)] == [out]
    assert events.effects(s, reply) == []
    s.close()


@pytest.mark.parametrize("case", ["unknown", "same_as_parent", "twice", "bad_role"])
def test_a_bad_link_writes_nothing(case):
    s = Store.memory(run_id="r", seed=1)
    with s.transaction() as tx:
        a = tx.commit_event(ev(at=1)).event_id
        b = tx.commit_event(ev(at=2)).event_id
    links = {"unknown": [EventLink(event_id="evt_999999", role="contributed")],
             "same_as_parent": [EventLink(event_id=a, role="contributed")],
             "twice": [EventLink(event_id=b, role="contributed"), EventLink(event_id=b, role="answered")],
             "bad_role": [EventLink.model_construct(event_id=b, role="blamed")]}[case]
    before = s.query_one("SELECT COUNT(*) FROM events")[0]
    with pytest.raises(StoreError) as err:
        with s.transaction() as tx:
            tx.commit_event(ev(cause=a, links=links, at=3, zone="zon_000777"))
    assert err.value.rule == "STORE-12"
    assert s.query_one("SELECT COUNT(*) FROM events")[0] == before
    assert s.query("SELECT 1 FROM zones WHERE zone_id = 'zon_000777'") == []
    s.close()


def test_replay_keeps_every_link():
    s = Store.memory(run_id="r", seed=1)
    _a, _b, _c, out = three(s)
    d = events.replay_world(s)
    assert events.get(d, out).links == events.get(s, out).links
    assert events.causes(d, out) == events.causes(s, out)
    s.close()
    d.close()
