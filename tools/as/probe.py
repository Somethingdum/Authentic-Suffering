#!/usr/bin/env python3
"""Lane probe (docs/as/08_LLM_CALLS.md §3.1–3.2, §7). Run on your machines with LM Studio up.

  python tools/as/probe.py            probe both lanes, print a report, write as_runs/reports/probe.json
  python tools/as/probe.py --write    also write thinking_mode / structured_with_thinking into as_config.yaml

Per lane: reachable? the configured model loaded? For thinking OFF, which thinking_mode actually
suppresses reasoning (fastest of those that do)? Does JSON-schema output validate? Does JSON schema
still allow reasoning when thinking is ON (structured_with_thinking)? Needs the engine's P1
(transport, client, config loader).
"""

from __future__ import annotations

import asyncio
import json
import sys
import time

from _live import REPORTS, load_config, need, save_config

MODES = ("native", "system_no_think", "chat_template_kwargs", "prefill_empty_think", "none")
SCHEMA = {"type": "object", "properties": {"ok": {"type": "boolean"}, "word": {"type": "string"}},
          "required": ["ok", "word"], "additionalProperties": False}


async def probe_lane(lane_id, cfg, transport) -> dict:
    from as_engine.contracts.common import CallClass
    from as_engine.contracts.lanes import ChatMessage, LMRequest

    lane = cfg.lanes[lane_id]
    out = {"lane": lane_id.value, "base_url": lane.base_url, "model": lane.model}
    try:
        out["reachable"] = await transport.health(lane_id, lane)
        out["models"] = await transport.list_models(lane_id, lane)
    except NotImplementedError:
        need("P1", "lanes.transport.HttpTransport")
    except Exception as e:  # noqa: BLE001
        out["reachable"], out["error"] = False, str(e)
        return out
    out["model_loaded"] = lane.model in out.get("models", [])
    msgs = [ChatMessage(role="system", content="You answer in one word."), ChatMessage(role="user", content="Say: ready")]
    results = []
    for mode in MODES:
        lc = lane.model_copy(update={"thinking_mode": mode})
        req = LMRequest(call_class=CallClass.PROBE, lane=lane_id, messages=msgs, thinking=False, max_tokens=64, deadline_s=60)
        t = time.perf_counter()
        try:
            resp = await transport.send(lc, req)
            ms = (time.perf_counter() - t) * 1000
            reasoned = bool(resp.reasoning) or "<think>" in (resp.text or "")
            results.append({"mode": mode, "ms": round(ms), "reasoning": reasoned, "text": (resp.text or "")[:40]})
        except Exception as e:  # noqa: BLE001
            results.append({"mode": mode, "error": str(e)[:120]})
    out["thinking_off_trials"] = results
    good = [r for r in results if "error" not in r and not r["reasoning"]]
    out["thinking_mode"] = min(good, key=lambda r: (r["ms"], MODES.index(r["mode"])))["mode"] if good else None
    chosen = lane.model_copy(update={"thinking_mode": out["thinking_mode"] or lane.thinking_mode})
    jreq = LMRequest(call_class=CallClass.PROBE, lane=lane_id, messages=msgs, thinking=False, max_tokens=64,
                     schema_name="probe", json_schema=SCHEMA, deadline_s=60)
    try:
        r = await transport.send(chosen, jreq)
        json.loads(r.text)
        out["json_schema"] = "ok"
    except Exception as e:  # noqa: BLE001
        out["json_schema"] = f"failed: {str(e)[:80]}"
    treq = jreq.model_copy(update={"thinking": True, "max_tokens": 1024})
    try:
        r = await transport.send(chosen, treq)
        parsed_ok = True
        try:
            json.loads(r.text)
        except ValueError:
            parsed_ok = False
        out["structured_with_thinking"] = "supported" if (r.reasoning and parsed_ok) else "unsupported"
    except Exception as e:  # noqa: BLE001
        out["structured_with_thinking"] = f"unknown ({str(e)[:60]})"
    return out


async def main(write: bool) -> int:
    from as_engine.contracts.common import Lane
    from as_engine.lanes.transport import HttpTransport

    cfg = load_config()
    transport = HttpTransport()
    report = []
    try:
        for lane_id in (Lane.A, Lane.B):
            report.append(await probe_lane(lane_id, cfg, transport))
    finally:
        try:
            await transport.aclose()
        except Exception:  # noqa: BLE001
            pass
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "probe.json").write_text(json.dumps(report, indent=1), encoding="utf-8")
    for r in report:
        print(f"lane {r['lane']}: reachable={r.get('reachable')} model_loaded={r.get('model_loaded')} "
              f"thinking_mode={r.get('thinking_mode')} json={r.get('json_schema')} structured_with_thinking={r.get('structured_with_thinking')}")
    if write:
        lanes = dict(cfg.lanes)
        for r in report:
            lid = Lane(r["lane"])
            upd = {}
            if r.get("thinking_mode"):
                upd["thinking_mode"] = r["thinking_mode"]
            if r.get("structured_with_thinking") in ("supported", "unsupported"):
                upd["structured_with_thinking"] = r["structured_with_thinking"]
            lanes[lid] = lanes[lid].model_copy(update=upd)
        save_config(cfg.model_copy(update={"lanes": lanes}))
        print("as_config.yaml updated")
    return 0 if all(r.get("reachable") and r.get("model_loaded") for r in report) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main("--write" in sys.argv)))
