"""Asked, then said why (D-167). mind/firewall.py classify_form QUESTION.

A line was a question only when it ended with "?": "Mara, you got any rounds to spare? I'm down to six." came across
as a statement — so it was never an unanswered question in the thread, never made her decision one only she could
make (HOLD-02), and the model was told it "came across as a statement". People ask and then say why.
"""

from __future__ import annotations

import pytest

from as_engine.contracts.common import UtteranceForm as F
from as_engine.mind import firewall

pytestmark = pytest.mark.phase(4)


@pytest.mark.parametrize("text, form", [
    ("Mara, you got any rounds to spare? I'm down to six.", F.QUESTION),
    ("Where's Eli? I looked in the office.", F.QUESTION),
    ("What? No. Not now.", F.QUESTION),
    ("Can you hold the door? I'll be quick.", F.REQUEST),          # a request stays a request
    ("Stay there. Did you hear me?", F.ORDER),                      # an order stays an order
    ("It's getting dark.", F.STATEMENT),
])
def test_asked_then_said(text, form):
    assert firewall.classify_form(text) == form
