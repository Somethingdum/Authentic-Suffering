"""Implementation: action.intent.to_intent (Actor v2: ActionPayload, pace, limits)."""
from __future__ import annotations

import dataclasses

from ..contracts.common import Verb

PACE = {"careful": (1.5, -6.0), "rushed": (0.6, 6.0)}


def _words(text):
    return len(text.split())


def to_intent(packet, affordances, output, *, lod, source, reaction=False):
    from ..contracts.mind import ActionPayload, CognitionOutput, IntakeOutput
    from .intent import InscriptionAct, Intent, IntentError, SpeechAct
    is_intake = isinstance(output, IntakeOutput)
    is_v1 = isinstance(output, CognitionOutput)
    if is_intake and output.choice == "NONE":
        return IntentError("none_choice", output.none_reason or "")
    sig = packet.handles.get(output.choice) if output.choice.startswith("A") else None
    pool = affordances.pool or affordances.options
    bound = next((o for o in pool if o.signature == sig), None) if sig else None
    if bound is None:
        return IntentError("hallucinated_choice", output.choice)
    speech = None
    sp = None if is_intake else output.speech
    if sp is not None:
        to = []
        for h in sp.to:
            if h == "everyone":
                to.append("everyone")
            elif h.startswith("P") and h in packet.handles:
                to.append(packet.handles[h])
            else:
                return IntentError("hallucinated_target", h)
        n = _words(sp.text)
        if source == "model" and (n > 100 or (reaction and n > 12)):
            return IntentError("speech_too_long", str(n))
        speech = SpeechAct(text=sp.text, to=tuple(to) or ("everyone",), volume=sp.volume,
                           delivery=sp.delivery, timing=sp.timing)
        u = n / 2.5
        if bound.verb == Verb.SPEAK:
            bound = dataclasses.replace(bound, est_duration_s=max(bound.est_duration_s, u))
        else:
            if speech.timing == "alongside" and ({"sneak", "hide"} & set(bound.tags)):
                speech = dataclasses.replace(speech, timing="before")
            if speech.timing == "alongside":
                bound = dataclasses.replace(bound, est_duration_s=max(bound.est_duration_s, u))
            else:
                bound = dataclasses.replace(bound, est_duration_s=bound.est_duration_s + u)
    # INTENT-07 pace
    pace = "normal" if is_v1 else output.pace
    if pace != "normal" and pace not in bound.paces:
        if is_intake:
            pace = "normal"
        else:
            return IntentError("unsupported_pace", pace)
    if pace != "normal":
        mult, db = PACE[pace]
        bound = dataclasses.replace(bound, est_duration_s=bound.est_duration_s * mult,
                                    noise_db=min(180.0, max(0.0, bound.noise_db + db)))
    # INTENT-09 expression and writing
    inscription = None
    gesture = attention = None
    if isinstance(output, ActionPayload):
        for h, letter in ((output.gesture, "G"), (output.attention, "F")):
            if h is not None and not (h[:1] == letter and h in packet.handles):
                return IntentError("hallucinated_expression", h)
        if output.gesture is not None:
            gopt = next(g for g in packet.gestures if g.handle == output.gesture)
            if gopt.hands > packet.hands_free - bound.hands:
                return IntentError("no_free_hand", output.gesture)
            gid, _, tb = packet.handles[output.gesture].partition(":")
            gesture = (gid, None if tb == "*" else tb)
        if output.attention is not None:
            attention = packet.handles[output.attention]
        ins = output.inscription
        if ins is not None:
            if "write" not in bound.tags or _words(ins.text) > 35:
                return IntentError("bad_inscription", ins.text[:40])
            src = None
            if ins.quotation_source is not None:
                h = ins.quotation_source
                if not (h[:1] in ("S", "E") and h in packet.handles):
                    return IntentError("bad_inscription", h)
                texts = [x.text for x in packet.perceived_now if x.handle == h] + \
                        [u.words for u in packet.utterances if u.handle == h] + \
                        [m.text for m in packet.memories if m.handle == h]
                if not any(ins.text in t for t in texts):
                    return IntentError("bad_inscription", h)
                src = packet.handles[h]
            inscription = InscriptionAct(text=ins.text, quotation_source=src)
    if bound.verb == Verb.SPEAK and speech is None:
        return IntentError("empty", output.choice)
    if is_intake:
        goal, reason, manner = (output.manner or bound.label), "", output.manner
    elif is_v1:
        goal, reason, manner = output.goal, output.private_reason, output.manner
    else:
        goal, reason, manner = output.goal, output.private_reason or "", ""
    return Intent(actor_id=packet.actor_id, bound=bound, speech=speech, manner=manner, goal=goal,
                  private_reason=reason, source=source, lod=lod, pace=pace, inscription=inscription,
                  gesture=gesture, attention=attention)

