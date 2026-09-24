"""Request building (P7): one place turns a call class + its context into an LMRequest. Rules
LANE-03, PROMPT-01, SCHEMA-02. Nothing above this boundary writes messages by hand.

build_request(config, call_class, *, turn_index, actor_id=None, context=None, json_schema=None,
              regime=None, lane=None, **render_ctx) -> LMRequest
  regime = ``regime`` or config.regimes[call_class] (the HOT path passes config.hot_cognition).
  messages = prompts.render.render(call_class, **render_ctx) (the keyword names are the ones
  prompts/render.py lists: p= for cognition, a=/cue_ids= for writeback, k=/words=/fix= for
  narration, ctx= for everything else).
  LMRequest(call_class, lane = ``lane`` or regime.lane, messages, schema_name = call_class.value
  when json_schema is given else None, json_schema, temperature / top_p / max_tokens / thinking /
  deadline_s from the regime, cache_key = prompts.render.cache_key(messages) (sha256 of the system
  message: PROMPT-01 keeps it stable per actor), actor_id, turn_index, context).
  ``context`` is the structured object the messages were rendered from (the fake model reads it;
  it is never sent over HTTP, contracts/lanes.py).

repair_request(config, failed, error, packet, json_schema) -> LMRequest   (LANE-06)
  The one repair call a failed actor decision gets: INTENT_REPAIR (regime and lane from
  config.regimes[INTENT_REPAIR], not the failed call's lane),
  context = ctx = RepairContext(packet=packet, raw_text=error.get('raw') or '', error=error.get
  ('error') or ''), json_schema = the same cognition schema, turn_index and actor_id copied from
  ``failed`` (the request that failed). ``error`` is a dict {raw, error}.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..contracts.common import CallClass, Lane
    from ..contracts.lanes import LMRequest
    from ..contracts.mind import SkullPacket
    from ..contracts.settings import CallRegime, EngineConfig


def build_request(config: "EngineConfig", call_class: "CallClass", *, turn_index: int | None, actor_id: str | None = None,
                  context: Any = None, json_schema: dict | None = None, regime: "CallRegime | None" = None,
                  lane: "Lane | None" = None, **render_ctx: Any) -> "LMRequest":
    raise NotImplementedError("P7")


def repair_request(config: "EngineConfig", failed: "LMRequest", error: dict, packet: "SkullPacket",
                   json_schema: dict) -> "LMRequest":
    raise NotImplementedError("P7")
