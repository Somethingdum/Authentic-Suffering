"""The only entropy door (L10, rule DET-10). Phase P0.

Core generator (IMPLEMENTED — do not change; test vectors in tests/fixtures/vectors/rng.json):
  * seeding: blake2b(f"{run_seed}:{stream}".encode(), digest_size=8) -> little-endian u64 -> four
    successive SplitMix64 outputs form the xoshiro256** state.
  * generator: xoshiro256** (Blackman & Vigna).
  * bounded draw ``draw(n)`` in [1, n]: rejection sampling — limit = (2**64 // n) * n; take x from
    the generator until x < limit; return x % n + 1.

Streams are independent so adding draws in one subsystem never shifts another's sequence.
Stream names: 'resolve', 'perception', 'cascade', 'offscreen', 'worldgen:<stage>', 'names',
'loot', 'quirks', 'infected', 'rumour', 'scheduler', 'cheats', 'test'.
Every draw is written to ``prng_ledger`` (bookkeeping) with its purpose, and the stream state is
persisted in ``rng_streams`` so a reload continues the same sequence.
Using ``random``, ``secrets``, ``uuid4``, ``time`` or ``os.urandom`` anywhere under
``as_engine`` (except lanes/ for HTTP timing) is forbidden (DET-11, AST-scanned).
"""

from __future__ import annotations

from hashlib import blake2b
from typing import TYPE_CHECKING, Sequence, TypeVar

if TYPE_CHECKING:
    from .store import Tx

MASK64 = (1 << 64) - 1
T = TypeVar("T")


def splitmix64(x: int) -> tuple[int, int]:
    """Return (next_state, output)."""
    x = (x + 0x9E3779B97F4A7C15) & MASK64
    z = x
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK64
    return x, z ^ (z >> 31)


def _rotl(x: int, k: int) -> int:
    return ((x << k) | (x >> (64 - k))) & MASK64


def xoshiro_next(state: tuple[int, int, int, int]) -> tuple[tuple[int, int, int, int], int]:
    """One xoshiro256** step. Returns (new_state, output_u64)."""
    s0, s1, s2, s3 = state
    result = (_rotl((s1 * 5) & MASK64, 7) * 9) & MASK64
    t = (s1 << 17) & MASK64
    s2 ^= s0
    s3 ^= s1
    s1 ^= s2
    s0 ^= s3
    s2 ^= t
    s3 = _rotl(s3, 45)
    return (s0, s1, s2, s3), result


def derive_state(run_seed: int, stream: str) -> tuple[int, int, int, int]:
    seed = int.from_bytes(blake2b(f"{run_seed}:{stream}".encode(), digest_size=8).digest(), "little")
    words = []
    for _ in range(4):
        seed, out = splitmix64(seed)
        words.append(out)
    return tuple(words)  # type: ignore[return-value]


def bounded(state: tuple[int, int, int, int], n: int) -> tuple[tuple[int, int, int, int], int]:
    """Unbiased draw in [1, n] from ``state``. Returns (new_state, value)."""
    if n < 1:
        raise ValueError("n must be >= 1")
    limit = ((1 << 64) // n) * n
    while True:
        state, x = xoshiro_next(state)
        if x < limit:
            return state, x % n + 1


def encode_state(state: tuple[int, int, int, int]) -> str:
    return "-".join(f"{w:016x}" for w in state)


def decode_state(text: str) -> tuple[int, int, int, int]:
    parts = text.split("-")
    if len(parts) != 4:
        raise ValueError("bad rng state")
    return tuple(int(p, 16) for p in parts)  # type: ignore[return-value]


class Rng:
    """Persistent, ledgered RNG bound to one run seed. NOT YET IMPLEMENTED (P0).

    Contract:
      * ``draw(tx, stream, purpose, n)`` loads the stream state from ``rng_streams`` (deriving it
        with ``derive_state`` on first use), calls ``bounded``, saves the new state, appends a
        ``prng_ledger`` row (seq = max(seq)+1, turn_index = current world_clock.turn_index), and
        returns the value. ``purpose`` is a short machine string, e.g. 'check:act_000004:climb'.
      * ``d10`` = draw(n=10). ``range_int(lo, hi)`` = lo + draw(hi-lo+1) - 1.
      * ``chance(p)`` = draw(1_000_000) <= round(p * 1_000_000), p clamped to [0, 1].
      * ``choice(seq)`` = seq[draw(len(seq)) - 1]; empty seq raises ValueError.
      * ``weighted(items: list[tuple[T, float]])``: cumulative weights scaled to integers by
        round(w * 1000); draw(total) picks the first item whose cumulative >= value.
      * ``shuffle(seq)`` returns a new list: Fisher-Yates from the end, j = draw(i + 1) - 1.
    """

    def __init__(self, run_seed: int):
        self.run_seed = run_seed

    def draw(self, tx: "Tx", stream: str, purpose: str, n: int) -> int:
        raise NotImplementedError("P0 — kernel/rng.py docstring")

    def d10(self, tx: "Tx", stream: str, purpose: str) -> int:
        raise NotImplementedError("P0")

    def range_int(self, tx: "Tx", stream: str, purpose: str, lo: int, hi: int) -> int:
        raise NotImplementedError("P0")

    def chance(self, tx: "Tx", stream: str, purpose: str, p: float) -> bool:
        raise NotImplementedError("P0")

    def choice(self, tx: "Tx", stream: str, purpose: str, seq: Sequence[T]) -> T:
        raise NotImplementedError("P0")

    def weighted(self, tx: "Tx", stream: str, purpose: str, items: Sequence[tuple[T, float]]) -> T:
        raise NotImplementedError("P0")

    def shuffle(self, tx: "Tx", stream: str, purpose: str, seq: Sequence[T]) -> list[T]:
        raise NotImplementedError("P0")
