"""Plausibility-gate expression language (P10; CNT-09 parses it at content load).

Grammar: expr   := clause ( 'and' clause )*          ('and' is a whole word, lower case)
         clause := NAME OP INT | 'entity_type' '=' WORD
         OP     := '>=' | '<=' | '==' | '!=' | '>' | '<'   (a single '=' only after entity_type)
         NAME   := CONDITION_NAMES (every integer field of WorldParams and its blocks, e.g.
                   faction_density, hostile_human, ammo, days_since_fall) or 'start_trust'
         INT    := one or more digits (no sign)      WORD := faction | group | none
         Whitespace around operators and between tokens is optional ('ammo>=1' parses).
parse(expr) -> [(name, op, value_text), ...] in order, e.g.
         parse('entity_type = faction and start_trust >= 4')
             == [('entity_type', '=', 'faction'), ('start_trust', '>=', '4')]
         Empty text, 'or', parentheses, unknown names, a non-integer value, a WORD outside the
         three, or any leftover text -> ConditionSyntaxError whose message quotes the expression.
evaluate(expr, values: dict[str, int|str]) -> bool: parse, then every clause must hold (AND).
         A name missing from ``values`` -> ConditionSyntaxError (never a silent False).
A PlausibilityGate passes when ANY pass_any expression is true; hard fail when hard_fail_all is set
and true. Enforced at Bitch..Realism only (CMG §61 QC-2).
"""

from __future__ import annotations

from ...kernel.errors import ASError


class ConditionSyntaxError(ASError):
    rule = "CNT-09"


def _int_leaves() -> frozenset[str]:
    from ...contracts import worldgen as wg

    names = {"days_since_fall"}
    for block in (wg.ABlock, wg.BBlock, wg.CBlock, wg.DBlock, wg.EBlock, wg.SimMechanics):
        names |= {n for n, f in block.model_fields.items() if f.annotation is int}
    return frozenset(names)


CONDITION_NAMES: frozenset[str] = _int_leaves() | {"start_trust"}


import re as _re

_TOK = _re.compile(r"\s*(>=|<=|==|!=|>|<|=|[A-Za-z_][A-Za-z0-9_]*|\d+|\S)")


def parse(expr: str) -> list[tuple[str, str, str]]:
    toks = []
    pos = 0
    s = expr
    while pos < len(s):
        m = _TOK.match(s, pos)
        if not m:
            break
        toks.append(m.group(1))
        pos = m.end()
        if s[pos:].strip() == "":
            break
    if not toks:
        raise ConditionSyntaxError(f"empty condition {expr!r}")
    out = []
    i = 0
    while True:
        if i + 3 > len(toks):
            raise ConditionSyntaxError(f"incomplete clause in {expr!r}")
        name, op, val = toks[i:i + 3]
        if name == "entity_type":
            if op != "=" or val not in ("faction", "group", "none"):
                raise ConditionSyntaxError(f"bad entity_type clause in {expr!r}")
        else:
            if name not in CONDITION_NAMES:
                raise ConditionSyntaxError(f"unknown name {name!r} in {expr!r}")
            if op not in (">=", "<=", "==", "!=", ">", "<"):
                raise ConditionSyntaxError(f"bad operator {op!r} in {expr!r}")
            if not val.isdigit():
                raise ConditionSyntaxError(f"value {val!r} is not a whole number in {expr!r}")
        out.append((name, op, val))
        i += 3
        if i == len(toks):
            return out
        if toks[i] != "and":
            raise ConditionSyntaxError(f"expected 'and' in {expr!r}")
        i += 1


def evaluate(expr: str, values: dict[str, int | str]) -> bool:
    ops = {">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b, "==": lambda a, b: a == b,
           "!=": lambda a, b: a != b, ">": lambda a, b: a > b, "<": lambda a, b: a < b}
    for name, op, val in parse(expr):
        if name not in values:
            raise ConditionSyntaxError(f"no value for {name!r}")
        if name == "entity_type":
            if values[name] != val:
                return False
        elif not ops[op](int(values[name]), int(val)):
            return False
    return True
