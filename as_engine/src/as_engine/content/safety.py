"""The one hard content line (CNT-11, CHEAT-08). PROTECTED: tools/as/protect.py lists this file.

No record, generated text or cheat-spawned dossier may combine a minor with sexual or romantic
content. This check cannot be disabled by any setting, pack, cheat or developer flag.

Which records are checked: every ActorDossier/PCDossier whose identity.age < 18; every scenario
body whose dossier is such a record; every WORLDGEN_ACTOR / PC_QUICKMAKE / DOSSIER_INTAKE result
whose age < 18; every cheat /spawn result (CHEAT-08). All string VALUES are scanned (never keys — identity.sex is a field name), including
writers_notes and depth_reference.

How: whole-word, case-insensitive match against MINOR_UNSAFE_TERMS after lowercasing and replacing
every non-letter with a space. Negation is NOT understood ("never romantic" still matches), on
purpose: a record about a child simply must not contain these words, and the engine already
enforces the line, so no author ever needs to write them into a child's record. A hit is a hard
error naming the file, field and term (never the surrounding text).
"""

from __future__ import annotations

MINOR_UNSAFE_TERMS: frozenset[str] = frozenset({
    "sex", "sexual", "sexually", "sexy", "nude", "nudity", "naked", "erotic", "aroused",
    "arousal", "seduce", "seductive", "seduction", "lingerie", "intercourse", "orgasm", "fetish",
    "lust", "lustful", "lewd", "romantic", "romance", "flirt", "flirting", "flirtatious",
    "dating", "lover", "lovers", "sensual", "kinky",
})


def unsafe_terms(text: str) -> list[str]:
    """Terms from MINOR_UNSAFE_TERMS found in text (implemented)."""
    import re

    words = set(re.sub(r"[^a-z]+", " ", text.lower()).split())
    return sorted(words & MINOR_UNSAFE_TERMS)
