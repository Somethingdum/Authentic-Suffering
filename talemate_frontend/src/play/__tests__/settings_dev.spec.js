// The settings dialog and the developer panel (10_UI §2.8, §2.9; 11_SETTINGS §1.2). PROTECTED.
import { describe, expect, test } from 'vitest'
import SettingsDialog from '../components/SettingsDialog.vue'
import DevPanel from '../panels/DevPanel.vue'
import PlayScreen from '../screens/PlayScreen.vue'
import { SETTINGS_TEXT } from '../words.js'
import { byId, field, fixture, flush, has, mountWith, one, storeWith } from './helpers.js'

async function dialog(...names) {
  const { store, sock } = storeWith(...names)
  store.openSettings()
  const w = mountWith(SettingsDialog, { store })
  await flush()
  return { store, sock, w }
}

describe('Settings', () => {
  test('Models is the Connect card pair; Gameplay lists exactly the changeable settings with their words', async () => {
    const { w, sock } = await dialog('run_loaded', 'settings', 'config', 'models_a', 'models_b')
    expect(has(w, 'lane-A-card') && has(w, 'lane-B-card')).toBe(true)
    await one(w, 'settings-tab-gameplay').trigger('click')
    await flush()
    const shown = byId(w, 'setting-row').map((r) => r.attributes('data-field'))
    expect(shown).toEqual(['turn_depth', 'narration_length', 'narration_person', 'narration_tense', 'pc_voice', 'intensity',
      'show_mechanics', 'read_aloud', 'autosave_ring'])        // dev_mode lives under Advanced
    const length = byId(w, 'setting-row').find((r) => r.attributes('data-field') === 'narration_length')
    expect(length.text()).toContain(SETTINGS_TEXT.narration_length.label)
    expect(length.text()).toContain(SETTINGS_TEXT.narration_length.help)
    for (const label of Object.values(SETTINGS_TEXT.narration_length.choices)) expect(length.text()).toContain(label)
    sock.sent.length = 0
    await one(w, 'setting-narration_length-long').trigger('click')
    await field(w, 'setting-autosave_ring').setValue('10')     // fires input and change: send on change, once
    expect(sock.sent).toEqual([{ action: 'settings_set', patch: { narration_length: 'long' } },
      { action: 'settings_set', patch: { autosave_ring: 10 } }])
  })

  test('without a run, Gameplay says there is nothing to change yet', async () => {
    const { w } = await dialog('welcome_home', 'config')
    await one(w, 'settings-tab-gameplay').trigger('click')
    await flush()
    expect(byId(w, 'setting-row')).toEqual([])
    expect(one(w, 'settings-no-run').text().length).toBeGreaterThan(20)
  })

  test('Advanced: developer mode, background thinking, the Workshop', async () => {
    const { w, sock } = await dialog('run_loaded', 'settings', 'config')
    await one(w, 'settings-tab-advanced').trigger('click')
    await flush()
    sock.sent.length = 0
    await one(w, 'setting-dev_mode-true').trigger('click')
    await one(w, 'setting-background-false').trigger('click')
    expect(sock.sent).toEqual([{ action: 'settings_set', patch: { dev_mode: true } },
      { action: 'config_set', patch: { background_cognition: false } }])
    expect(one(w, 'open-workshop').attributes('href')).toBe('?ui=workshop')
    await one(w, 'settings-close').trigger('click')
  })
})

describe('Developer panel', () => {
  test('only with developer mode on', async () => {
    let { store } = storeWith('run_loaded', 'view_rich', 'settings')
    let w = mountWith(PlayScreen, { store })
    await flush()
    expect(has(w, 'dev-panel')).toBe(false)
    ;({ store } = storeWith('run_loaded', 'view_rich', 'settings_dev'))
    w = mountWith(PlayScreen, { store })
    await flush()
    expect(has(w, 'dev-panel')).toBe(true)
  })

  test('a tab per kind of record; it asks for that record and lists the rows', async () => {
    const { store, sock } = storeWith('run_loaded', 'view_rich', 'settings_dev')
    const w = mountWith(DevPanel, { store })
    await flush()
    const tabs = ['trace', 'intents', 'packets', 'events', 'gate', 'errors', 'calls']
    for (const t of tabs) expect(has(w, `dev-tab-${t}`), t).toBe(true)
    sock.sent.length = 0
    await one(w, 'dev-tab-gate').trigger('click')
    expect(sock.sent).toEqual([{ action: 'dev_get', what: 'gate', turn_index: null }])
    sock.emit(fixture('dev_gate'))
    await flush()
    const rows = byId(w, 'dev-row')
    expect(rows.length).toBe(1)
    expect(rows[0].text()).toContain(fixture('dev_gate').data.rows[0].world_bits)
    await one(w, 'dev-tab-trace').trigger('click')
    sock.emit(fixture('dev_trace'))
    await flush()
    expect(byId(w, 'dev-row').length).toBe(20)
  })
})
