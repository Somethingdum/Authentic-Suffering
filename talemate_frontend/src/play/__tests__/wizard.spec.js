// The New Life wizard (10_UI §2.3; 11_SETTINGS §1): who you are, what kind of world, the house rules,
// then one run_new with exactly those choices — and a draft that survives a cancelled build. PROTECTED.
import { describe, expect, test } from 'vitest'
import WizardScreen from '../screens/WizardScreen.vue'
import { DETAIL_TEXT, DIFFICULTY_HELP, ERA_TEXT, SETTINGS_TEXT, TEXT } from '../words.js'
import { byId, field, fixture, flush, has, mountWith, one, storeWith } from './helpers.js'

const CARDS = fixture('pcs').data.cards
const TIERS = ['bitch_mode', 'easy', 'normal', 'realism', 'actually_hell', 'fuck_you']
const TIER_NAMES = ['Bitch Mode', 'Easy', 'Normal', 'Realism', 'Actually Hell', 'Fuck You']
const ERAS = ['early', 'established', 'mature']
const DETAILS = ['gotta_go_to_work_soon', 'quick_look', 'standard', 'settle_in', 'not_using_my_laptop_today']
const COMMON = ['save_mode', 'turn_depth', 'narration_length', 'intensity', 'show_mechanics']
const MORE = ['narration_person', 'narration_tense', 'pc_voice', 'read_aloud', 'autosave_ring']

async function open(...msgs) {
  const { store, sock } = storeWith('pcs', ...msgs)
  store.go('wizard')
  const w = mountWith(WizardScreen, { store })
  await flush()
  sock.sent.length = 0
  return { store, sock, w }
}

const pressed = (el) => el.attributes('aria-pressed') === 'true'
const disabled = (el) => el.attributes('disabled') !== undefined
const card = (w, name) => byId(w, 'pc-card').find((c) => c.get('[data-testid="pc-card-name"]').text() === name)

async function click(w, id) {
  await one(w, id).trigger('click')
  await flush()
}

async function choose(w, name) {
  await card(w, name).trigger('click')
  await flush()
}

async function toStep2(w, name) {
  await choose(w, name)
  await click(w, 'wizard-next')
}

describe('step 1: who are you?', () => {
  test('asks for the characters once and shows each as a card, in the CMG words', async () => {
    const { store, sock } = storeWith()
    store.go('wizard')
    mountWith(WizardScreen, { store })
    await flush()
    expect(sock.actions().filter((a) => a === 'pcs_list')).toEqual(['pcs_list'])
    sock.emit(fixture('pcs'))
    sock.sent.length = 0
    const w = mountWith(WizardScreen, { store })
    await flush()
    expect(sock.sent).toEqual([])
    const cards = byId(w, 'pc-card')
    expect(cards.length).toBe(CARDS.length)
    CARDS.forEach((c, i) => {
      const get = (id) => cards[i].get(`[data-testid="${id}"]`).text()
      expect(get('pc-card-name')).toBe(c.display_name)
      expect(get('pc-card-identity')).toBe(c.one_line_identity)
      for (const [id, label, value] of [['pc-card-survives', TEXT.survivesBy, c.survives_by],
        ['pc-card-starts', TEXT.startsAs, c.starts_as], ['pc-card-note', TEXT.note, c.note]]) {
        expect(get(id)).toContain(label)
        expect(get(id)).toContain(value)
      }
      expect(get('pc-card-age')).toBe(c.world_age_note)
    })
    expect(has(w, 'pc-import') || has(w, 'pc-quickmake')).toBe(false)
  })

  test('the steps are named; Next waits for a character, and one at a time is chosen', async () => {
    const { w } = await open()
    expect([1, 2, 3, 4].map((n) => one(w, `wizard-step-${n}`).text())).toEqual(TEXT.wizardSteps)
    expect([1, 2, 3, 4].map((n) => one(w, `wizard-step-${n}`).attributes('data-state'))).toEqual(['current', 'todo', 'todo', 'todo'])
    expect(disabled(one(w, 'wizard-next'))).toBe(true)
    expect(has(w, 'wizard-start')).toBe(false)
    await choose(w, 'Owen Marsh')
    expect(pressed(card(w, 'Owen Marsh'))).toBe(true)
    await choose(w, 'Ruth Castillo')
    expect(byId(w, 'pc-card').map(pressed)).toEqual(CARDS.map((c) => c.display_name === 'Ruth Castillo'))
    expect(disabled(one(w, 'wizard-next'))).toBe(false)
    await click(w, 'wizard-next')
    expect([1, 2, 3, 4].map((n) => one(w, `wizard-step-${n}`).attributes('data-state'))).toEqual(['done', 'current', 'todo', 'todo'])
  })

  test('Back from the first step goes home; from the second it keeps the choice', async () => {
    const { store, w } = await open()
    await toStep2(w, 'Addison Flores')
    await click(w, 'wizard-back')
    expect(pressed(card(w, 'Addison Flores'))).toBe(true)
    await click(w, 'wizard-back')
    expect(store.screen).toBe('home')
  })
})

describe('step 2: what kind of world?', () => {
  test('every difficulty, era and detail with its words; Normal, Mature and Standard to begin with', async () => {
    const { w } = await open()
    await toStep2(w, 'Owen Marsh')
    TIERS.forEach((t, i) => {
      const el = one(w, `difficulty-option-${t}`)
      expect(el.text()).toContain(TIER_NAMES[i])
      expect(el.text()).toContain(DIFFICULTY_HELP[t])
      expect(pressed(el)).toBe(t === 'normal')
    })
    for (const e of ERAS) {
      const el = one(w, `era-option-${e}`)
      expect(el.text()).toContain(ERA_TEXT[e].label)
      expect([pressed(el), disabled(el)]).toEqual([e === 'mature', false])
    }
    expect(ERAS.map((e) => ERA_TEXT[e].days)).toEqual([[14, 330], [400, 1460], [1830, 3650]])
    expect(DETAILS.map((d) => DETAIL_TEXT[d].minutes)).toEqual([3, 7, 15, 30, 60])
    for (const d of DETAILS) {
      const el = one(w, `detail-option-${d}`)
      expect(el.text()).toContain(DETAIL_TEXT[d].label)
      expect(el.text()).toContain(TEXT.buildTime(DETAIL_TEXT[d].minutes))
      expect(pressed(el)).toBe(d === 'standard')
    }
    await click(w, 'difficulty-option-realism')
    expect(TIERS.filter((t) => pressed(one(w, `difficulty-option-${t}`)))).toEqual(['realism'])
    expect(DIFFICULTY_HELP.normal).toBe('Survivable with consistent good decisions. Comfort is earned. Setbacks require active recovery.')
  })

  test('an era the character cannot live in is not offered, and says why', async () => {
    const { w } = await open()
    await toStep2(w, 'Addison Flores')
    const note = CARDS.find((c) => c.display_name === 'Addison Flores').world_age_note
    for (const e of ['early', 'established']) {
      expect(disabled(one(w, `era-option-${e}`))).toBe(true)
      expect(one(w, `era-reason-${e}`).text()).toBe(note)
    }
    expect(pressed(one(w, 'era-option-mature'))).toBe(true)
    expect(has(w, 'era-reason-mature')).toBe(false)
  })

  test('another character that cannot live in the chosen era moves it back to one that fits', async () => {
    const { w } = await open()
    await toStep2(w, 'Owen Marsh')
    await click(w, 'era-option-early')
    expect(pressed(one(w, 'era-option-early'))).toBe(true)
    await click(w, 'wizard-back')
    await toStep2(w, 'Ruth Castillo')
    expect(disabled(one(w, 'era-option-early'))).toBe(true)
    expect(ERAS.filter((e) => pressed(one(w, `era-option-${e}`)))).toEqual(['mature'])
  })

  test('days since the Fall must fit both the era and the character; the seed is a whole number', async () => {
    const { w } = await open()
    await toStep2(w, 'Addison Flores')
    expect(one(w, 'days-hint').text()).toBe(TEXT.daysHint(3287, 3650))
    for (const bad of ['3000', '3651', '3300.5', 'soon']) {
      await field(w, 'days-input').setValue(bad)
      await flush()
      expect(one(w, 'days-error').text(), bad).toBe(TEXT.daysRange(3287, 3650))
      expect(disabled(one(w, 'wizard-next'))).toBe(true)
    }
    await field(w, 'days-input').setValue('3300')
    await flush()
    expect(has(w, 'days-error')).toBe(false)
    expect(disabled(one(w, 'wizard-next'))).toBe(false)
    for (const bad of ['-3', '4.2', 'x']) {
      await field(w, 'seed-input').setValue(bad)
      await flush()
      expect(one(w, 'seed-error').text(), bad).toBe(TEXT.seedHelp)
      expect(disabled(one(w, 'wizard-next'))).toBe(true)
    }
    await field(w, 'seed-input').setValue('42')
    await flush()
    expect(has(w, 'seed-error')).toBe(false)
    expect(disabled(one(w, 'wizard-next'))).toBe(false)
  })
})

describe('step 3: house rules', () => {
  test('the common rules with their words and defaults; more options shows the rest', async () => {
    const { w } = await open()
    await toStep2(w, 'Owen Marsh')
    await click(w, 'wizard-next')
    expect(has(w, 'house-rules')).toBe(true)
    const rows = () => byId(w, 'wizard-setting').map((r) => r.attributes('data-field'))
    expect(rows()).toEqual(COMMON)
    const defaults = { save_mode: 'free', turn_depth: 'balanced', narration_length: 'medium', intensity: 'full',
      show_mechanics: 'summary', narration_person: 'third_limited', narration_tense: 'past', pc_voice: 'exact',
      read_aloud: 'false' }
    for (const f of COMMON) {
      const row = byId(w, 'wizard-setting').find((r) => r.attributes('data-field') === f)
      expect(row.text()).toContain(SETTINGS_TEXT[f].label)
      expect(row.text()).toContain(SETTINGS_TEXT[f].help)
      for (const v of Object.keys(SETTINGS_TEXT[f].choices)) {
        const b = one(w, `wizard-setting-${f}-${v}`)
        expect(b.text()).toContain(SETTINGS_TEXT[f].choices[v])
        expect(pressed(b), `${f}=${v}`).toBe(defaults[f] === v)
      }
    }
    expect(Object.keys(SETTINGS_TEXT.save_mode.choices)).toEqual(['free', 'ironman'])
    await click(w, 'more-options-toggle')
    expect(rows()).toEqual([...COMMON, ...MORE])
    for (const f of MORE.filter((x) => x !== 'autosave_ring')) {
      for (const v of Object.keys(SETTINGS_TEXT[f].choices)) expect(pressed(one(w, `wizard-setting-${f}-${v}`))).toBe(defaults[f] === v)
    }
    expect(field(w, 'wizard-setting-autosave_ring').element.value).toBe('5')
  })
})

describe('step 4: build the world', () => {
  async function allTheWay(w, { days = '', seed = '' } = {}) {
    await toStep2(w, 'Addison Flores')
    await click(w, 'difficulty-option-realism')
    await click(w, 'detail-option-quick_look')
    if (days) await field(w, 'days-input').setValue(days)
    if (seed) await field(w, 'seed-input').setValue(seed)
    await flush()
    await click(w, 'wizard-next')
    await click(w, 'wizard-setting-save_mode-ironman')
    await click(w, 'wizard-setting-turn_depth-deep')
    await click(w, 'wizard-next')
  }

  test('the summary names every choice, and Start sends exactly one run_new with them', async () => {
    const { store, sock, w } = await open()
    await allTheWay(w, { days: '3300', seed: '42' })
    const summary = one(w, 'wizard-summary').text()
    for (const bit of ['Addison Flores', 'Realism', ERA_TEXT.mature.label, DETAIL_TEXT.quick_look.label, '3300', '42',
      SETTINGS_TEXT.save_mode.choices.ironman]) expect(summary).toContain(bit)
    expect(has(w, 'wizard-next')).toBe(false)
    sock.sent.length = 0
    await click(w, 'wizard-start')
    expect(sock.sent).toEqual([{ action: 'run_new', pc_ref: 'core:pc/addison_flores', settings: {
      difficulty: 'realism', era: 'mature', world_detail: 'quick_look', save_mode: 'ironman', turn_depth: 'deep',
      narration_length: 'medium', intensity: 'full', show_mechanics: 'summary', narration_person: 'third_limited',
      narration_tense: 'past', pc_voice: 'exact', read_aloud: false, autosave_ring: 5, days_since_fall: 3300, seed: 42 } }])
    expect(store.screen).toBe('worldgen')
  })

  test('without days or a seed the world draws them itself', async () => {
    const { sock, w } = await open()
    await allTheWay(w)
    sock.sent.length = 0
    await click(w, 'wizard-start')
    const [msg] = sock.sent
    expect('days_since_fall' in msg.settings || 'seed' in msg.settings).toBe(false)
  })

  test('a cancelled or refused build comes back to the same choices; a started life clears them', async () => {
    const { store, sock, w } = await open()
    await allTheWay(w, { days: '3300' })
    const summary = one(w, 'wizard-summary').text()
    await click(w, 'wizard-start')
    sock.emit(fixture('state_wizard'))
    expect(store.screen).toBe('wizard')
    const again = mountWith(WizardScreen, { store })
    await flush()
    expect(one(again, 'wizard-step-4').attributes('data-state')).toBe('current')
    expect(one(again, 'wizard-summary').text()).toBe(summary)
    sock.emit(fixture('run_loaded'))
    expect([store.wizard.step, store.wizard.pcRef]).toEqual([1, null])
  })
})
