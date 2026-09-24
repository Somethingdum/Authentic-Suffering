"""Implementation helpers of lanes/schemas.py (schema inlining and closing)."""
import copy
def _inline(node, defs):
    if isinstance(node, dict):
        if "$ref" in node:
            name = node["$ref"].split("/")[-1]
            target = copy.deepcopy(defs[name])
            rest = {k: v for k, v in node.items() if k != "$ref"}
            target.update(rest)
            return _inline(target, defs)
        return {k: _inline(v, defs) for k, v in node.items() if k not in ("title", "default", "$defs")}
    if isinstance(node, list):
        return [_inline(v, defs) for v in node]
    return node

def _close(node):
    if isinstance(node, dict):
        if node.get("type") == "object":
            node["additionalProperties"] = False
        for v in node.values():
            _close(v)
    elif isinstance(node, list):
        for v in node:
            _close(v)
    return node
