---
name: as-play-ui
description: P8 only - the Play UI inside the Talemate frontend fork, its protocol, test ids and vitest tests.
whenToUse: Working on P8 (service/game_service.py, the Talemate plugin, talemate_frontend/src/play/).
disable-model-invocation: false
---

# Play UI (P8)

- Read `docs/as/10_UI.md` (screens, components, test ids, copy, store, socket) — every `data-testid` in
  the tests is listed there. Do not invent ids. §2 says which screens are P8 (Connect, Home, Play,
  Content validator, Settings, Developer panel); the wizard, worldgen, death and worlds screens are
  P10 / P12 — until then PlayApp shows `LaterScreen.vue`.
- Backend first: `service/guide.py`, then `service/game_service.py` (`out`, `handle`, `push`, `idle`,
  `get_service`, then the `on_<action>` handlers). A turn runs as a background task
  (`asyncio.create_task`): `turn_submit` answers `state {busy: true}` at once and everything else is
  pushed. Stop cancels that task; `Store.transaction` must roll back on a `BaseException`.
- The frontend specs mount through `src/play/__tests__/helpers.js` (read it first): Vuetify with every
  component registered, `provide('playStore', store)`, a fake socket. Specs import `words.js`,
  `socket.js`, `store.js`, `PlayApp.vue`, the screens, the panels and `components/SettingsDialog.vue`
  by those exact paths. Nothing a spec clicks may be inside a teleported overlay (`v-menu`,
  `v-dialog`, `v-tooltip`, `v-select`): use inline lists and buttons (10 §2).
- `fixtures/*.json` are protocol messages the engine can send (the engine's `test_ui_fixtures.py`
  checks them); feed them to the store the way the specs do when you try a screen by hand.
- Backend: `as_engine/src/as_engine/service/game_service.py` speaks the protocol;
  `src/talemate/server/as_game_plugin.py` (02 §6 gives the whole file) only routes websocket
  messages to it. Talemate's `Plugin.__init__` calls `connect()`, and `WebsocketHandler.disconnect()`
  calls every plugin's `disconnect()` — the plugin relies on both.
- Talemate upstream edits are limited to `docs/as/02_ARCHITECTURE.md` §4.1; check with
  `python tools/as/gate.py --upstream-diff`.
- The frontend uses pnpm through corepack, never npm: after adding the devDependencies run
  `cd talemate_frontend && corepack pnpm install` (this rewrites `pnpm-lock.yaml`; commit it — the
  install scripts use `--frozen-lockfile`).
- Frontend tests: `cd talemate_frontend && corepack pnpm run test:play` (vitest + jsdom).
- Plugin test (needs Talemate's environment): from the fork root
  `python -m pytest tests/test_as_game_plugin.py -q -o addopts=""` (drops Talemate's `-n auto`).
- `python tools/as/gate.py --phase 8` runs all of these plus the upstream-diff check.
- The human finishes P8 with the smoke checklist in `talemate_frontend/src/play/README.md`.
