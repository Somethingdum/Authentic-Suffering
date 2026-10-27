"""What a hosted story never does (P13, D-299). Rules INTAKE-10, LIMIT-01, META-01, CNT-18
(turn/intake.py, narration/lint.py, narration/narrator.py, content/pack.py).

A story never asks the player a question: a hosted intake reads an unclear move as the offered
option nearest to it. The one hard limit holds whatever model writes: no sexual content where anyone
under 18 is present — a draft that crosses it is never shown, and when every draft does, the moment
is told plainly by code. A draft in which the model steps out of the story to refuse, apologise or
talk about itself is written again. An intimate act is offered only between two adults, and a
content pack that offers one otherwise does not load.
"""

from __future__ import annotations

import pytest
from host_kit import call, only

from as_engine.contracts.common import CallClass
from as_engine.contracts.narration import NarratorLine, NarratorPacket
from as_engine.contracts.settings import RulesConfig
from as_engine.host.protocol import b64
from as_engine.narration import lint, narrator

pytestmark = pytest.mark.phase(13)

NUM = RulesConfig().style


@pytest.fixture
def style(canon):
    return canon.find("style", "narration")


def packet(**kw):
    base = dict(turn_index=1, world_time_text="23:14, day 18 since the Fall (night)", place_text="Sales floor", pc_name="Owen",
                allowed_names=["Owen", "Mara", "June"], length="short",
                lines=[NarratorLine(seconds=0, kind="sight", text="Mara holds the door.")])
    base.update(kw)
    return NarratorPacket(**base)


PLAIN = ("Owen crosses the sales floor. Mara holds the door for him and watches the street. The rain keeps on against "
         "the glass. He counts the cans on the shelf twice and finds the same number both times, then he looks back at her.")


def rules(report):
    return {f.rule for f in report.findings}


def test_the_hard_limit_is_kept_when_someone_young_is_present(style):
    bad = PLAIN + " Then she touches him in a sexual way."
    assert "LIMIT-01" in rules(lint.lint_prose(bad, packet(minors_present=True), style, NUM, ["Owen", "Mara", "June"]))
    assert "LIMIT-01" not in rules(lint.lint_prose(bad, packet(minors_present=False), style, NUM, ["Owen", "Mara", "June"]))
    quoted = PLAIN + ' "Get the sexual predator away from the kids," Mara says.'
    assert "LIMIT-01" in rules(lint.lint_prose(quoted, packet(minors_present=True), style, NUM, ["Owen", "Mara", "June"])), \
        "the limit reads everything, speech too"
    for dark in (" The dead man's throat is open to the bone and the blood has gone black.",
                 " He gropes for the flashlight in the dark.", " The noise aroused the dead in the alley.",
                 " She undresses the wound and he holds the boy still."):
        r = lint.lint_prose(PLAIN + dark, packet(minors_present=True), style, NUM, ["Owen", "Mara", "June"])
        assert "LIMIT-01" not in rules(r), ("fiction may be as dark as it likes; the one limit is the only limit", dark)


def test_a_draft_that_steps_out_of_the_story(style):
    for out in ("I'm sorry, but I can't continue this scene.", "As an AI, I cannot write that.",
                "Note: this content may be disturbing."):
        r = lint.lint_prose(PLAIN + " " + out, packet(), style, NUM, ["Owen", "Mara", "June"])
        assert "META-01" in rules(r) and not r.passed, out
    said = PLAIN + ' "I\'m sorry, but I can\'t help you," Mara says.'
    assert "META-01" not in rules(lint.lint_prose(said, packet(), style, NUM, ["Owen", "Mara", "June"])), \
        "a character may say it; the narrator may not"


async def test_a_draft_over_the_limit_is_never_shown(style, config):
    from as_engine.contracts.lanes import LMResponse
    from as_engine.lanes.client import LaneClient

    class Writer:
        async def send(self, lane, request):
            return LMResponse(call_class=request.call_class, lane=request.lane, text=PLAIN + " Then they have sex.")

        async def list_models(self, lane_id, lane):
            return [lane.model]

        async def health(self, lane_id, lane):
            return True
    pk = packet(minors_present=True)
    prose, findings, attempts, passed = await narrator.narrate(LaneClient(config, Writer()), pk, style, NUM, config=config,
                                                               all_known_names=["Owen", "Mara", "June"], turn_index=1)
    assert "have sex" not in prose and prose == narrator.code_render(pk) and not passed
    assert attempts == NUM.max_narration_attempts and any(f.rule == "LIMIT-01" for f in findings)


async def test_the_packet_knows_who_is_young(world0, host, hosted):
    svc = hosted(host())
    await call(svc, "open", world=b64(world0))
    st = svc.session.store
    from as_engine.narration.narrator import build_narrator_packet
    with st.transaction() as tx:
        place = tx.query_one("SELECT place_id FROM positions WHERE body_id=?", (svc.session.pc_id,))[0]
        young = [r[0] for r in tx.query("SELECT b.body_id FROM bodies b JOIN positions p ON p.body_id=b.body_id "
                                        "WHERE p.place_id=? AND b.age_years < 18", (place,))]
        pk = build_narrator_packet(tx, svc.session.pc_id, 0, 0, svc.session.settings)
    assert pk.minors_present is bool(young)


async def test_a_hosted_intake_never_asks(world0, host, hosted):
    h = host()
    svc = hosted(h)
    await call(svc, "open", world=b64(world0))
    req = []
    orig = svc.host_transport.send

    async def keep(lane, request):
        req.append(request)
        return await orig(lane, request)
    svc.host_transport.send = keep
    for _ in range(2):                  # the first look and the second (INTAKE-07)
        h.fake.script(CallClass.INTAKE, response={"choice": "NONE", "none_reason": "unclear", "clarify": "Which door do you mean?"})
    got = await call(svc, "turn", mode="do", text="I do the thing with the door.", tier=3)
    intake = [r for r in req if r.call_class.value == "intake"]
    assert intake and intake[0].context.closest is True
    assert "Never answer \"unclear\"" in intake[0].messages[0].content
    rej = only(got, "turn_rejected")
    assert not rej.get("clarify"), "a story never asks the player a question"
    assert "?" not in rej["message"]


def test_an_intimate_act_needs_two_adults(tmp_path, core_pack_dir):
    from as_engine.content.pack import load_canon
    pk = tmp_path / "loose"
    (pk / "affordances").mkdir(parents=True)
    (pk / "pack.yaml").write_text("schema: as.pack.v1\nid: loose\nname: test\nversion: 1.0.0\ndescription: test\n"
                                  "depends_on: [core]\nauthors: [tests]\n", encoding="utf-8")
    (pk / "affordances" / "a.yaml").write_text(
        "- schema: as.affordance.v1\n  id: caress\n  verb: signal\n  label: \"Caress {target}\"\n  ui_label: \"Caress {target}\"\n"
        "  binds: body\n  range: touch\n  requires: {target_kinds: [human]}\n  duration: {base_s: 3}\n  noise_db: 0\n"
        "  effect: signal\n  tags: [touch, intimate, quiet]\n", encoding="utf-8")
    _canon, issues = load_canon([core_pack_dir, pk])
    found = [i for i in issues if i.code == "CNT-18"]
    assert found and found[0].severity == "error" and "adults_only" in found[0].message
    _c, core = load_canon([core_pack_dir])
    assert not [i for i in core if i.code == "CNT-18"], "the core pack's kiss is between adults (D-292)"
