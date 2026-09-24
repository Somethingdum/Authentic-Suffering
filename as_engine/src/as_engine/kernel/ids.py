"""Deterministic id minting (P0). Rule STORE-06.

Format: ``f"{kind}_{n:06d}"`` where n starts at 1 per kind and is stored in ``counters``.
Ids are deterministic so replay reproduces them. Unknown kinds raise ValueError.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .store import Tx

ID_KINDS: tuple[str, ...] = (
    "evt",  # event
    "act",  # body / actor (an actor id IS its body id)
    "zon", "plc", "anc", "prt", "rte",  # space
    "itm", "lot",  # objects
    "wnd", "cnd",  # wounds, conditions
    "clm", "prp", "pct",  # truth claim, proposition, percept
    "ref", "olp", "lsn", "epi", "vln",  # refusal, open loop, lesson, episode, voice line
    "tsk", "que", "scn", "rct",  # task, queue entry, scene, pending reaction
    "dos", "ddl",  # dossier, dossier delta
    "grp", "hh", "stl", "wkp", "coh", "rtn",  # society
    "his", "ops", "trc", "rum", "hrd",  # world (hrd: a horde, P10)
    "aud", "err", "cht",  # audit, error log, cheat log
)


def format_id(kind: str, n: int) -> str:
    if kind not in ID_KINDS:
        raise ValueError(f"unknown id kind: {kind}")
    return f"{kind}_{n:06d}"


def mint(tx: "Tx", kind: str) -> str:
    """Return the next id of ``kind`` and advance ``counters`` (bookkeeping write, owner kernel.meta)."""
    raise NotImplementedError("P0 — docs/as/03_DATA_MODEL.md §Ids")
