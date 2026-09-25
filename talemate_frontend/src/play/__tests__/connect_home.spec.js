// The Connect and Home screens and the Content screen (10_UI §2.1, §2.2, §2.7). PROTECTED.
import { describe, expect, test } from 'vitest'
import ConnectScreen from '../screens/ConnectScreen.vue'
import ContentScreen from '../screens/ContentScreen.vue'
import HomeScreen from '../screens/HomeScreen.vue'
import { TEXT } from '../words.js'
import { byId, field, fixture, flush, has, mountWith, one, storeWith } from './helpers.js'

describe('Connect', () => {
  test('asks for the models and the config; both models are picked from the one LM Studio list', async () => {
    const { store, sock } = storeWith('welcome_connect')
    sock.sent.length = 0
    const w = mountWith(ConnectScreen, { store })
    expect(sock.actions()).toEqual(expect.arrayContaining(['models_list', 'config_get']))
    sock.emit(fixture('config'))
    sock.emit(fixture('models_a'))
    sock.emit(fixture('models_b'))
    await flush()
    for (const lane of ['A', 'B']) {
      expect(has(w, `lane-${lane}-card`)).toBe(true)
      expect(has(w, `lane-${lane}-test`)).toBe(true)
    }
    expect(one(w, 'lane-A-card').text()).toContain('Main model')
    expect(one(w, 'lane-B-card').text()).toContain('Second model')
    expect(one(w, 'lane-A-model').text()).toContain('nemotron-cascade-2-30b-a3b')
    expect(one(w, 'lane-A-model').find('input').exists()).toBe(false)
    expect(byId(w, 'lane-A-model-option').map((o) => o.text())).toEqual(['nemotron-cascade-2-30b-a3b', 'qwen3-32b'])
    expect(byId(w, 'lane-B-model-option')).toEqual([])
    expect(has(w, 'lane-A-url')).toBe(false)
    await one(w, 'lane-A-advanced').trigger('click')
    expect(field(w, 'lane-A-url').element.value).toBe('http://localhost:1234/v1')
  })

  test('a model that is no longer loaded is replaced from the list, never typed', async () => {
    const { store, sock } = storeWith('welcome_connect', 'config')
    const w = mountWith(ConnectScreen, { store })
    const listed = ['nemotron-cascade-2-30b-a3b', 'nvidia-nemotron-3.5-lightning-30b-a3b']
    sock.emit({ type: 'as_game', action: 'models', data: { lane: 'B', models: listed, selected: listed[1], reachable: true } })
    sock.emit({ type: 'as_game', action: 'models', data: { lane: 'A', models: listed, selected: 'an-old-model', reachable: true } })
    await flush()
    expect(one(w, 'lane-A-model').text()).toContain(listed[0])
    expect(one(w, 'lane-A-model').text()).toContain('not saved yet')
    expect(one(w, 'lane-B-model').text()).toContain(listed[1])
    expect(one(w, 'lane-B-model').text()).not.toContain('not saved yet')
  })

  test('Test saves the picked model, then tests; the result is shown in words', async () => {
    const { store, sock } = storeWith('welcome_connect', 'config', 'models_a', 'models_b')
    const w = mountWith(ConnectScreen, { store })
    await flush()
    await byId(w, 'lane-A-model-option')[1].trigger('click')
    expect(one(w, 'lane-A-model').text()).toContain('qwen3-32b')
    await one(w, 'lane-A-advanced').trigger('click')
    await field(w, 'lane-A-url').setValue('http://127.0.0.1:1234/v1')
    sock.sent.length = 0
    await one(w, 'lane-A-test').trigger('click')
    expect(sock.sent).toEqual([
      { action: 'config_set', patch: { lanes: { A: { base_url: 'http://127.0.0.1:1234/v1', model: 'qwen3-32b' } } } },
      { action: 'models_test', lane: 'A' },
    ])
    sock.emit(fixture('test_a_ok'))
    sock.emit(fixture('test_b_down'))
    await flush()
    expect(one(w, 'lane-A-status').text()).toContain('Working — answered in 1.8 s.')
    expect(one(w, 'lane-B-status').text()).toContain('Not answering at http://localhost:1234/v1.')
  })

  test('Continue needs at least the main model; it asks the server where to go', async () => {
    const { store, sock } = storeWith('welcome_connect', 'config', 'models_a', 'models_b')
    const w = mountWith(ConnectScreen, { store })
    await flush()
    expect(one(w, 'connect-continue').attributes('disabled')).toBeDefined()
    sock.emit(fixture('test_b_down'))
    await flush()
    expect(one(w, 'connect-continue').attributes('disabled')).toBeDefined()
    sock.emit(fixture('test_a_ok'))
    await flush()
    expect(one(w, 'connect-continue').attributes('disabled')).toBeUndefined()
    sock.sent.length = 0
    await one(w, 'connect-continue').trigger('click')
    expect(sock.sent).toEqual([{ action: 'get_state' }])
  })
})

describe('Home', () => {
  test('big buttons with words; Continue names the newest run', async () => {
    const { store, sock } = storeWith('welcome_home', 'runs')
    const w = mountWith(HomeScreen, { store })
    await flush()
    for (const id of ['home-continue', 'home-new-life', 'home-sessions', 'home-worlds', 'home-content', 'home-settings']) {
      expect(one(w, id).text().trim().length, id).toBeGreaterThan(2)
    }
    expect(one(w, 'home-continue').text()).toContain('Owen Marsh')
    expect(one(w, 'home-continue').text()).toContain('day 18')
    expect(one(w, 'home-continue').text()).toContain('alive')
    sock.sent.length = 0
    await one(w, 'home-continue').trigger('click')
    expect(sock.sent).toEqual([{ action: 'run_load', run_id: 'owen_marsh_71a', save_slot: null }])
  })

  test('no runs: no Continue', async () => {
    const { store, sock } = storeWith('welcome_home')
    sock.emit({ type: 'as_game', action: 'runs', data: { runs: [] } })
    const w = mountWith(HomeScreen, { store })
    await flush()
    expect(has(w, 'home-continue')).toBe(false)
  })

  test('Your lives opens the list of every session (sessions.spec.js)', async () => {
    const { store } = storeWith('welcome_home', 'runs')
    const w = mountWith(HomeScreen, { store })
    await flush()
    expect(has(w, 'run-card')).toBe(false)
    await one(w, 'home-sessions').trigger('click')
    expect(store.screen).toBe('sessions')
  })

  test('Enter a code (P12, CHEAT-12): the box sends the code and answers in words, never saying what codes do', async () => {
    const { store, sock } = storeWith('welcome_home', 'runs')
    const w = mountWith(HomeScreen, { store })
    await flush()
    expect(one(w, 'home-code-label').text()).toContain(TEXT.codeLabel)
    await field(w, 'home-code').setValue('1234')
    sock.sent.length = 0
    await one(w, 'home-code-enter').trigger('click')
    expect(sock.sent).toEqual([{ action: 'code_enter', code: '1234' }])
    sock.emit({ type: 'as_game', action: 'code_result', data: { accepted: false } })
    await flush()
    expect(one(w, 'home-code-result').text()).toBe(TEXT.codeRejected)
    sock.emit({ type: 'as_game', action: 'code_result', data: { accepted: true } })
    await flush()
    expect(one(w, 'home-code-result').text()).toBe(TEXT.codeAccepted)
    expect(store.pcs).toEqual([])   // the New Life list asks again
  })

  test('the other buttons go where they say', async () => {
    const { store } = storeWith('welcome_home', 'runs')
    const w = mountWith(HomeScreen, { store })
    await one(w, 'home-content').trigger('click')
    expect(store.screen).toBe('content')
    await one(w, 'home-settings').trigger('click')
    expect(store.settingsOpen).toBe(true)
    await one(w, 'home-new-life').trigger('click')
    expect(store.screen).toBe('wizard')
    store.go('home')
    await one(w, 'home-worlds').trigger('click')
    expect(store.screen).toBe('worlds')
  })
})

describe('Your characters & world', () => {
  test('pack rows with counts; Validate shows the report in plain lines', async () => {
    const { store, sock } = storeWith('welcome_home')
    sock.sent.length = 0
    const w = mountWith(ContentScreen, { store })
    expect(sock.sent).toEqual([{ action: 'packs_list' }])
    sock.emit(fixture('packs'))
    await flush()
    const rows = byId(w, 'pack-row')
    expect(rows.length).toBe(2)
    expect(rows[0].text()).toContain('Authentic Suffering — core')
    expect(rows[0].text()).toContain('227 records')
    sock.sent.length = 0
    await rows[1].get('[data-testid="pack-validate"]').trigger('click')
    expect(sock.sent).toEqual([{ action: 'content_validate', pack_id: 'my_content' }])
    sock.emit(fixture('content_report_bad'))
    await flush()
    expect(byId(w, 'content-report-error').map((e) => e.text())).toEqual(
      ['actors/mara_voss.yaml — voice.would_never_say needs at least 3 lines (it has 1)'])
    expect(byId(w, 'content-report-warning').length).toBe(1)
    await one(w, 'content-back').trigger('click')
    expect(store.screen).toBe('home')
  })
})
