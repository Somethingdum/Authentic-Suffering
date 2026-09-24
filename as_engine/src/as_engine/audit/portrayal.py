"""Portrayal audit (Stage 15, P11). Rules AUDIT-01, PORT-01..03, L13.
A lane-B call that did NOT produce the intent judges "would this Actor do that?" against the
motive stack, moral line, decision stack, contradiction, stats, skills, relationships, stress and
commitments (prompts/portrayal_audit.j2). The judge's call id MUST differ from the producer's
(audit_log CHECK). Verdict 'out_of_character' before commit -> regenerate the intent once with the
reasons appended; a second failure keeps the intent, logs portrayal_fail, and continues.
Audits run for HOT actors every turn and for WARM actors on turns where they spoke or attacked.
"""

from __future__ import annotations
