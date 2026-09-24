"""Canonical truth accessors (P0/P3). THE ONLY MODULE THAT READS `claims` / `canonical_truth`.

Import boundary (SKULL-02, BOUND-02): only these modules may import ``as_engine.kernel.truth``:
  as_engine.kernel.*, as_engine.mind.perception, as_engine.action.*, as_engine.world.*,
  as_engine.society.*, as_engine.audit.*, as_engine.cheats.*, as_engine.turn.*,
  as_engine.service.death (post-death reveal), as_engine.testing.* (the scenario loader writes
  truth claims for fixture beliefs with true_in_world). Any other importer fails BOUND-02.
It is FORBIDDEN in: as_engine.mind.packet, as_engine.mind.memory, as_engine.mind.retrieval,
as_engine.narration.*, as_engine.service.view (the view model is built from the PC's mind only).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..contracts.events import WriteOp, WriteRecord

if TYPE_CHECKING:
    from .store import Store, Tx


def fact_write(claim_id: str, subject_type: str, subject_id: str, predicate: str,
               object_value: str | None, true_from: int, origin_event: str) -> WriteRecord:
    """WriteRecord inserting a canonical fact (writer must be 'kernel.truth')."""
    return WriteRecord(op=WriteOp.INSERT, table="claims", values={
        "claim_id": claim_id, "subject_type": subject_type, "subject_id": subject_id,
        "predicate": predicate, "object_value": object_value, "true_from": true_from,
        "true_until": None, "origin_event": origin_event,
    })


def retire_write(claim_id: str, true_until: int) -> WriteRecord:
    return WriteRecord(op=WriteOp.UPDATE, table="claims", key={"claim_id": claim_id},
                       values={"true_until": true_until})


def current_facts(store: "Store | Tx", subject_type: str, subject_id: str,
                  predicate: str | None = None) -> list[dict[str, Any]]:
    """Rows of canonical_truth for a subject (optionally one predicate), ordered by claim_id."""
    sql = "SELECT * FROM canonical_truth WHERE subject_type=? AND subject_id=?"
    params = [subject_type, subject_id]
    if predicate is not None:
        sql += " AND predicate=?"
        params.append(predicate)
    return [dict(r) for r in store.query(sql + " ORDER BY claim_id", tuple(params))]
