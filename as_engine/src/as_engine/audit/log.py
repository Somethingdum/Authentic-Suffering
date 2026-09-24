"""audit_log and error_repair_log writers (implemented; owner 'audit'). record() is the one way any
module records an audit row; repair() the one way it records an error/repair (e.g. a writeback
item dropped for citing something unperceived, MEM-02). For audit rows:
gate names are 'G<n>-<what>' (04_TURN_PIPELINE.md §1), producer is the module or call id that made
the thing judged, judge the module or call id that judged it (MUST differ: schema CHECK)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from ..contracts.events import WriteOp

if TYPE_CHECKING:
    from ..kernel.store import Tx


def record(tx: "Tx", gate: str, producer: str, result: Literal["pass", "fail", "warn"],
           findings: list[dict[str, Any]], turn_index: int, *, judge: str = "audit") -> str:
    """Insert one audit_log row (bookkeeping write) and return its id (kind 'aud')."""
    audit_id = tx.mint("aud")
    tx.bookkeep("audit", "audit_log", WriteOp.INSERT, {}, {
        "audit_id": audit_id, "turn_index": turn_index, "gate": gate, "producer": producer,
        "judge": judge, "result": result, "findings": findings,
    })
    return audit_id


def repair(tx: "Tx", kind: str, stage: int | None, rule_id: str | None, detail: dict[str, Any],
           turn_index: int, at_ms: int, *, repaired: bool = False) -> str:
    """Insert one error_repair_log row (bookkeeping write, owner 'audit') and return its id (kind
    'err'). kind is one of the schema's list (hallucinated_ref, schema_fail, lint_fail, ...)."""
    entry_id = tx.mint("err")
    tx.bookkeep("audit", "error_repair_log", WriteOp.INSERT, {}, {
        "entry_id": entry_id, "turn_index": turn_index, "at_ms": at_ms, "kind": kind, "stage": stage,
        "rule_id": rule_id, "detail": detail, "repaired": int(repaired),
    })
    return entry_id
