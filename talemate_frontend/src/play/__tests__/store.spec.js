// store.js — reactive state + actions over the socket (10_UI §4). PROTECTED.
import { afterEach, describe, expect, test, vi } from 'vitest'
import { CLIENT_VERSION, createPlayStore } from '../store.js'
import { TEXT } from '../words.js'
import { fakeSocket, fixture, storeWith } from './helpers.js'

afterEach(() => vi.useRealTimers())

describe('connecting', () => {
  test('hello whenever the socket opens; welcome picks the screen and asks for what it needs', () => {
    const sock = fakeSocket('connecting')
    const store = createPlayStore(sock)
    expect(store.screen).toBe('connect')
    expect(sock.sent).toEqual([])
    sock.setStatus('open')
    expect(store.connected).toBe(true)
    expect(sock.sent).toEqual([{ action: 'hello', client_version: CLIENT_VERSION }])
    sock.emit(fixture('welcome_home'))
    expect([store.screen, store.modelsOk, store.hasRuns, store.serverVersion]).toEqual(['home', true, true, '0.1.0'])
    expect(sock.actions().slice(1)).toEqual(['runs_list'])
    sock.setStatus('closed')
    expect(store.connected).toBe(false)
    sock.setStatus('open')
    expect(sock.actions().at(-1)).toBe('hello')
  })

  test('welcome on play (a reloaded page) asks for the view, the story and the settings', () => {
    const { store, sock } = storeWith()
    sock.emit({ type: 'as_game', action: 'welcome', data: { server_version: '0.1.0', screen: 'play', has_runs: true, models_ok: true } })
    expect(store.screen).toBe('play')
    expect(sock.actions().slice(1)).toEqual(['get_state', 'view_get', 'story_get', 'settings_get'])
  })

  test('a second tab: the connect screen with the plain notice, nothing else', () => {
    const { store, sock } = storeWith('welcome_home')
    sock.setStatus('other_tab')
    expect(store.screen).toBe('connect')
    expect(store.error).toEqual({ code: 'other_tab', message: TEXT.otherTab })
  })
})

describe('messages -> state', () => {
  test('models, tests, config, runs', () => {
    const { store } = storeWith('models_a', 'models_b', 'test_a_ok', 'test_b_down', 'config', 'runs')
    expect(store.models.A.models).toEqual(['nemotron-cascade-2-30b-a3b', 'qwen3-32b'])
    expect(store.models.B.reachable).toBe(false)
    expect(store.laneTests.A.ok).toBe(true)
    expect(store.laneTests.B.detail).toMatch(/^Not answering/)
    expect(store.config.lanes.A.base_url).toBe('http://localhost:1234/v1')
    expect(store.runs.map((r) => r.run_id)).toEqual(['owen_marsh_71a', 'addison_flores_5c2'])
    expect(store.hasRuns).toBe(true)
  })

  test('run_loaded opens the play screen and asks for the settings; view and story fill it', () => {
    const { store, sock } = storeWith('run_loaded', 'view_rich', 'story_anchor')
    expect(sock.actions()).toEqual(['hello', 'settings_get'])
    expect([store.screen, store.runId, store.ironman, store.sandbox]).toEqual(['play', 'addison_flores_5c2', true, false])
    expect(store.notices).toEqual(['Your content changed since this run started. People already in the world keep who they were.'])
    expect(store.settings.save_mode).toBe('ironman')
    expect(store.view.pc_name).toBe('Addison Flores')
    expect(store.lanes.B.ok).toBe(false)
    expect(store.story.length).toBe(fixture('story_anchor').data.entries.length)
  })

  test('a turn: busy, progress, result, the story, then idle', () => {
    const { store, sock } = storeWith('run_loaded', 'view_rich')
    store.submit('do', 'I force the steel door.')
    expect(sock.last('turn_submit')).toEqual({ action: 'turn_submit', mode: 'do', text: 'I force the steel door.',
      suggestion_ref: null, addressee_refs: [] })
    sock.emit({ type: 'as_game', action: 'state', data: { screen: 'play', run_id: 'addison_flores_5c2', busy: true } })
    expect(store.busy).toBe(true)
    sock.emit(fixture('turn_progress_6'))
    expect(store.progress).toEqual({ turnIndex: 42, stage: 6, label: 'People decide…', pct: 31.6, elapsed: 12.4 })
    sock.emit(fixture('turn_result_anchor'))
    expect(store.progress).toBe(null)
    expect(store.view.pc_name).toBe('Owen Marsh')
    expect(store.story.length).toBe(0)       // the story arrives as its own message
    sock.emit(fixture('story_anchor'))
    expect(store.story.at(-1).kind).toBe('notice')
    sock.emit({ type: 'as_game', action: 'state', data: { screen: 'play', run_id: 'addison_flores_5c2', busy: false } })
    expect([store.busy, store.progress]).toEqual([false, null])
  })

  test('a rejection is shown until the next submit', () => {
    const { store } = storeWith('run_loaded', 'view_rich', 'turn_progress_6', 'turn_rejected')
    expect(store.rejection).toEqual({ reasonCode: 'unclear', message: "It isn't clear what you want to do.",
      clarify: 'Do you want to force the door or pick the lock?' })
    expect(store.progress).toBe(null)
    store.submit('say', 'Tomas?', { addresseeRefs: ['p1'] })
    expect(store.rejection).toBe(null)
  })

  test('errors, saved, settings, developer data, lanes, packs, content reports', () => {
    const { store } = storeWith('error_busy', 'saved', 'settings_dev', 'dev_trace', 'dev_gate', 'lanes_status', 'packs',
      'content_report_bad')
    expect(store.error).toEqual({ code: 'busy', message: fixture('error_busy').data.message })
    expect(store.saved).toEqual({ slot: 'before_the_depot', label: 'Before the depot', turn_index: 41 })
    expect(store.settings.dev_mode).toBe(true)
    expect(store.changeable).toContain('dev_mode')
    expect(store.devData.trace.rows.length).toBe(20)
    expect(store.devData.gate.rows[0].passed).toBe(1)
    expect(store.lanes.A.ok).toBe(true)
    expect(store.packs.map((p) => p.pack_id)).toEqual(['core', 'my_content'])
    expect(store.contentReport.ok).toBe(false)
    store.clearError()
    expect(store.error).toBe(null)
  })

  test('cheat_activated shimmers for 1.2 s and joins the story; world_file downloads', () => {
    vi.useFakeTimers()
    const { store, sock, downloads } = storeWith('run_loaded', 'view_rich')
    sock.emit({ type: 'as_game', action: 'cheat_activated', data: { persona_line: 'Well, well. Hello, Boss.', ok: true, detail: '' } })
    expect(store.cheatShimmer).toBe(true)
    expect(store.sandbox).toBe(true)
    expect(store.story.at(-1)).toEqual({ turn_index: 41, kind: 'cheat', text: 'Well, well. Hello, Boss.', mode: null })
    vi.advanceTimersByTime(1200)
    expect(store.cheatShimmer).toBe(false)
    sock.emit({ type: 'as_game', action: 'world_file', data: { filename: 'w1.asworld', data_b64: 'UEsDBA==' } })
    expect(downloads).toEqual([{ filename: 'w1.asworld', dataB64: 'UEsDBA==' }])
  })
})

describe('actions -> messages', () => {
  test('each action sends exactly its protocol message', () => {
    const { store, sock } = storeWith('run_loaded', 'view_rich')
    sock.sent.length = 0
    store.getState()
    store.listModels()
    store.testLane('B')
    store.getConfig()
    store.saveModels({ lanes: { B: { model: 'x' } } })
    store.listRuns()
    store.loadRun('owen_marsh_71a')
    store.loadRun('owen_marsh_71a', 'Before the fence')
    store.closeRun()
    store.deleteRun('owen_marsh_71a')
    store.save('Before the depot')
    store.cancelTurn()
    store.getView()
    store.getStory()
    store.getSettings()
    store.setSettings({ narration_length: 'long' })
    store.devGet('events', 3)
    store.listPacks()
    store.validatePack('my_content')
    store.submit('do', '', { suggestionRef: 's4' })
    store.submit('ask', 'How does bleeding work?')
    expect(sock.sent).toEqual([
      { action: 'get_state' }, { action: 'models_list' }, { action: 'models_test', lane: 'B' }, { action: 'config_get' },
      { action: 'config_set', patch: { lanes: { B: { model: 'x' } } } }, { action: 'runs_list' },
      { action: 'run_load', run_id: 'owen_marsh_71a', save_slot: null },
      { action: 'run_load', run_id: 'owen_marsh_71a', save_slot: 'Before the fence' },
      { action: 'run_close' }, { action: 'run_delete', run_id: 'owen_marsh_71a' },
      { action: 'run_save', slot_name: 'Before the depot' }, { action: 'turn_cancel' }, { action: 'view_get' },
      { action: 'story_get' }, { action: 'settings_get' }, { action: 'settings_set', patch: { narration_length: 'long' } },
      { action: 'dev_get', what: 'events', turn_index: 3 }, { action: 'packs_list' },
      { action: 'content_validate', pack_id: 'my_content' },
      { action: 'turn_submit', mode: 'do', text: '', suggestion_ref: 's4', addressee_refs: [] },
      { action: 'turn_submit', mode: 'ask', text: 'How does bleeding work?', suggestion_ref: null, addressee_refs: [] },
    ])
  })

  test('client-side navigation, the settings dialog and the Do box', () => {
    const { store, sock } = storeWith('welcome_home')
    const before = sock.sent.length
    store.go('content')
    expect(store.screen).toBe('content')
    sock.emit({ type: 'as_game', action: 'state', data: { screen: 'home', run_id: null, busy: false } })
    expect(store.screen).toBe('content')   // a client-only screen is not left for 'home'
    store.go('home')
    store.openSettings()
    expect(store.settingsOpen).toBe(true)
    store.closeSettings()
    expect(store.settingsOpen).toBe(false)
    store.compose('Reload the Glock 19')
    expect([store.mode, store.composeText]).toEqual(['do', 'Reload the Glock 19'])
    expect(sock.sent.length).toBe(before)    // none of these talk to the server
  })
})
