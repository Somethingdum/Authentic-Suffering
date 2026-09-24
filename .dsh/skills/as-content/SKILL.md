---
name: as-content
description: Authentic Suffering content packs - layout, validation codes (CNT-*), compiling, and what code may assume about content.
whenToUse: A test or the loader reports a CNT-* issue, or a task touches as_content/ or content/pack.py.
---

# Content packs

- Packs live in `as_content/packs/<pack>/` with `pack.yaml`, `cues.yaml` and one folder per kind
  (`actors/`, `pcs/`, `items/`, `affordances/`, `cascade/`, `laws/`, `infected/`, …).
- `content/pack.py` (P2) loads, validates (CNT-00..14) and compiles them into a `Canon`:
  `canon.get('core:item/glock_19')`, `canon.find('affordance', 'go_look')`, `canon.all('cascade')`.
- The rules for every CNT code are in the `content/pack.py` docstring and `docs/as/09_CONTENT_PACKS.md`.
- Code never hard-codes content ids except where a docstring names them (e.g. `SEEN` keys, the
  `CENTRE_MASS` table). New behaviour comes from content fields, not from `if def_id == ...`
  (the effect handlers switch on `AffordanceDef.effect`, not on the def id).
- `content/safety.py` is protected (CNT-11: no sexual content involving minors in any form).
- The core pack is part of the spec. If it seems wrong, file a spec issue; do not edit it to pass
  a test.
