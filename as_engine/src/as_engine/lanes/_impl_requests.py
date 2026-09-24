"""Implementation of lanes/requests.py."""
from __future__ import annotations


def build_request(config, call_class, *, turn_index, actor_id=None, context=None, json_schema=None, regime=None,
                  lane=None, **render_ctx):
    from ..contracts.lanes import LMRequest
    from ..prompts.render import cache_key, render
    reg = regime or config.regimes[call_class]
    msgs = render(call_class, **render_ctx)
    return LMRequest(call_class=call_class, lane=lane or reg.lane, messages=msgs,
                     schema_name=call_class.value if json_schema is not None else None, json_schema=json_schema,
                     temperature=reg.temperature, top_p=reg.top_p, max_tokens=reg.max_tokens, thinking=reg.thinking,
                     deadline_s=reg.deadline_s, cache_key=cache_key(msgs), actor_id=actor_id, turn_index=turn_index,
                     context=context)


def repair_request(config, failed, error, packet, json_schema):
    from ..contracts.calls import RepairContext
    from ..contracts.common import CallClass
    raw = error.get("raw") or ""
    ctx = RepairContext(packet=packet, raw_text=raw, error=error.get("error") or "")
    return build_request(config, CallClass.INTENT_REPAIR, turn_index=failed.turn_index, actor_id=failed.actor_id,
                         context=ctx, json_schema=json_schema, ctx=ctx)
