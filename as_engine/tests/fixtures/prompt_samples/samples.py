"""Sample render contexts for every prompt template (PROTECTED; docs/as/12_TESTING.md §10).

``render_kwargs()`` returns {CallClass: kwargs for prompts.render.render(call_class, **kwargs)}.
The samples are Mara Voss at the moment of the metal-fence crash (docs/as/04_TURN_PIPELINE.md §7),
so a human can read the rendered prompts and judge them.
"""

from __future__ import annotations

from as_engine.contracts.calls import (
    AuditContext,
    CheatPersonaContext,
    DossierIntakeContext,
    GuideContext,
    IntakeContext,
    LintContext,
    ProbeContext,
    ReflectionContext,
    RepairContext,
    RumourContext,
    SayMyWayContext,
    SummaryContext,
    WorldgenContext,
)
from as_engine.contracts.common import LOD, CallClass, Channel, Fidelity, OpenLoopKind, Standing, UtteranceForm, Verb, Volume
from as_engine.contracts.mind import (
    AffordanceOption,
    AftermathPacket,
    BeliefLine,
    CognitionOutput,
    Commitments,
    LoopLine,
    MemoryLine,
    PacketEntity,
    PerceivedItem,
    RelationshipLine,
    SkullPacket,
    SpeechOut,
    Stakes,
    UtteranceView,
)
from as_engine.contracts.narration import NarratorLine, NarratorPacket


def mara_packet() -> SkullPacket:
    return SkullPacket(
        actor_id="act_000002", turn_index=1, lod=LOD.HOT, world_time_text="Day 18, 23:14, night, wind rising",
        identity_text="Mara Voss, 34, a former prison guard who holds the front window at night.",
        voice_capsule="Low, flat and short. Prison-count cadence; gets quieter when scared.",
        voice_exemplars=["Eat the peaches first. The beans'll keep.",
                         "Quiet. Everybody down. June — doorway, not past it.",
                         "I'm going to ask you one time to put it on the ground."],
        recent_lines=["Window's clear."], would_never_say=["Trust me.", "I'm sorry for your loss."],
        body_lines=["Tired: four hours of sleep.", "No injuries."],
        capability_lines=["Firearms: skilled (eight years of qualification).", "Brawling: skilled."],
        resolve_cur=5, resolve_max=6, position_text="At the front window of the sales floor, standing.",
        perceived_now=[PerceivedItem(handle="S1", channel=Channel.AUDITORY, fidelity=Fidelity.EXACT,
                                     text="A loud metal crash from behind the store, out back.", seconds_ago=0.2)],
        utterances=[UtteranceView(handle="S2", speaker_handle="P2", words="What was that?", fidelity=Fidelity.EXACT,
                                  form=UtteranceForm.QUESTION, standing=Standing.PEER, addressed_to_me=False,
                                  volume=Volume.RAISED)],
        entities=[PacketEntity(handle="P1", description="Owen, the hired hand, at the counter", known_name="Owen"),
                  PacketEntity(handle="P2", description="June, in the stockroom", known_name="June",
                               relation_summary="friend; you trust her")],
        beliefs=[BeliefLine(text="Nita walks the alley at eleven; it's clear.", confidence=1,
                            provenance_text="Nita told you", age_text="this evening")],
        relationships=[RelationshipLine(handle="P2", text="June: your friend. You let her tease you.")],
        memories=[MemoryLine(handle="E1", text="A car alarm pulled a dozen of them up the street last week.", age_text="a week ago")],
        open_loops=[LoopLine(handle="L1", kind=OpenLoopKind.GOAL, text="Get a second barricade on the back door")],
        commitments=Commitments(current_task=None, plan_step="Watch the front window",
                                standing_orders=["On a loud noise: find the source and cover it."]),
        stakes=Stakes(dependents=["Eli, your son, asleep in the office"], obligations=["Night watch"]),
        resources=["Your .38 revolver: six loaded, eleven loose rounds."],
        motive_lines=["You want Eli to reach an age where he can survive without you."],
        moral_lines=["You will not leave Eli behind. You will not shoot a living child."],
        decision_lines=["Eli first; then your ability to keep standing watch; then Ray's rules."],
        active_traits=["vigilant: you move to cover the side the sound came from before you answer anyone."],
        writers_notes="Holding herself together with procedure; the warmth goes to Eli and June.",
        affordances=[AffordanceOption(handle="A1", verb=Verb.MOVE, label="Move to the end of the rear shelving (7 m, about 5 seconds)"),
                     AffordanceOption(handle="A2", verb=Verb.SPEAK, label="Say something to anyone who can hear (you choose the words and how loud)"),
                     AffordanceOption(handle="A3", verb=Verb.OBSERVE, label="Stay put and watch everything you can see and hear"),
                     AffordanceOption(handle="A4", verb=Verb.WAIT, label="Stay where you are and do nothing yet")],
        uncertainty=["You don't know what made the crash."],
        handles={"A1": "move_to_anchor:*:anc_000005:*", "A2": "speak:*:*:*", "A3": "observe_area:*:*:*",
                 "A4": "wait_here:*:*:*", "P1": "act_000001", "P2": "act_000004", "S1": "pct_000001", "S2": "pct_000002",
                 "E1": "epi_000001", "L1": "olp_000001"})


def aftermath() -> AftermathPacket:
    p = mara_packet()
    return AftermathPacket(holder_id=p.actor_id, turn_index=1, identity_text=p.identity_text,
                           voice_capsule=p.voice_capsule, percepts=p.perceived_now, utterances=p.utterances,
                           entities=p.entities, own_action_text='Said "Quiet." and moved to the end of the rear shelving.',
                           own_expectation_text="To cover the back door from the shelving.",
                           open_loops=p.open_loops, relationships=p.relationships,
                           handles={"S1": "pct_000001", "S2": "pct_000002", "P1": "act_000001", "P2": "act_000004", "L1": "olp_000001"})


def narrator_packet() -> NarratorPacket:
    return NarratorPacket(
        turn_index=1, world_time_text="Day 18, 23:14, night", place_text="the sales floor of Delgado's Market",
        pc_name="Owen", pc_state_lines=["Tired.", "Glock in your right hand."],
        lines=[NarratorLine(seconds=0.0, kind="sound", text="A loud metal crash from out back."),
               NarratorLine(seconds=0.4, kind="speech", text="Mara speaks.", speaker="Mara", words="Quiet."),
               NarratorLine(seconds=0.9, kind="speech", text="June calls out from the stockroom.", speaker="June", words="What was that?")],
        people_present=["Mara at the window", "Alice behind the counter"], allowed_names=["Owen", "Mara", "June", "Alice"],
        banned_phrases=["a testament to"], player_input_echo_block=["watch the front window"])


def render_kwargs() -> dict[CallClass, dict]:
    p = mara_packet()
    k = narrator_packet()
    brief = "Region: a river town. Era: early. Write the requested fields in plain English."
    return {
        CallClass.ACTOR_COGNITION: {"p": p},
        CallClass.ACTOR_REACTION: {"p": p},
        CallClass.INTAKE: {"ctx": IntakeContext(packet=p, player_text="I watch the front window and keep quiet.")},
        CallClass.INTENT_REPAIR: {"ctx": RepairContext(packet=p, raw_text="I think I'll go look {not json", error="no JSON object found")},
        CallClass.WRITEBACK: {"a": aftermath(), "cue_ids": ["loud_noise", "metal_crash", "knows_noise_draws_dead"]},
        CallClass.PORTRAYAL_AUDIT: {"ctx": AuditContext(packet=p, output=CognitionOutput(choice="A1", speech=SpeechOut(text="Quiet.", to=["everyone"], volume=Volume.NORMAL), goal="cover the back", private_reason="That was the fence."), chosen_label=p.affordances[0].label)},
        CallClass.NARRATION: {"k": k, "words": (90, 160), "fix": []},
        CallClass.RENDER_LINT: {"ctx": LintContext(packet=k, prose="A crash came from out back. Mara said, \"Quiet.\"", sentences=["A crash came from out back.", "Mara said, \"Quiet.\""])},
        CallClass.RUMOUR_DISTORT: {"ctx": RumourContext(teller_identity="June, a pharmacy tech who talks when she's nervous", claim_text="Something crashed out back at Delgado's last night.", teller_confidence=2)},
        CallClass.CASCADE_ADVISORY: {"ctx": WorldgenContext(stage="cascade", brief="A pump operator lost the use of an arm this morning.")},
        CallClass.GUIDE: {"ctx": GuideContext(question="What was that noise?", pc_name="Owen", pc_facts=["You heard a metal crash from out back."])},
        CallClass.REFLECTION: {"ctx": ReflectionContext(packet=p, recent_episodes=["You held the window through the storm."])},
        CallClass.SCENE_SUMMARY: {"ctx": SummaryContext(holder_name="Owen", lines=["A crash out back.", "Mara said quiet."], purpose="scene_summary")},
        CallClass.RECAP: {"ctx": SummaryContext(holder_name="Owen", lines=["You came to Delgado's on day three."], purpose="recap")},
        CallClass.SAY_MY_WAY: {"ctx": SayMyWayContext(packet=p, seed_text="Tell June to stay inside.", behavior_notes=["Says the conclusion first."])},
        CallClass.WORLDGEN_HISTORY: {"ctx": WorldgenContext(stage="history", brief=brief)},
        CallClass.WORLDGEN_ACTOR: {"ctx": WorldgenContext(stage="actor", brief=brief)},
        CallClass.WORLDGEN_OPENING: {"ctx": WorldgenContext(stage="opening", brief=brief)},
        CallClass.DOSSIER_INTAKE: {"ctx": DossierIntakeContext(target_kind="actor", source_text="Hal is a pump mechanic in his forties.", pack_id="my_content")},
        CallClass.PC_QUICKMAKE: {"ctx": WorldgenContext(stage="quickmake", brief="Name: Dana. Age 30. Before: bus driver.")},
        CallClass.CHEAT_PERSONA: {"ctx": CheatPersonaContext(command="/time +2h", outcome="The clock moved two hours.", recent_lines=["Done, Boss."])},
        CallClass.PROBE: {"ctx": ProbeContext(probe="hello")},
    }
