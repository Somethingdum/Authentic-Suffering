// The Worldgen screen (10_UI §2.4) and the P10 screens under the clarity rules (§1). PROTECTED.
import { mount } from '@vue/test-utils'
import { describe, expect, test } from 'vitest'
import LoadingBar from '../components/LoadingBar.vue'
import PlayApp from '../PlayApp.vue'
import WizardScreen from '../screens/WizardScreen.vue'
import WorldgenScreen from '../screens/WorldgenScreen.vue'
import { BANNED_WORDS, ID_PATTERN, TEXT } from '../words.js'
import { byId, fixture, flush, has, mountWith, one, readable, storeWith, vuetify } from './helpers.js'

async function building(...extra) {
  const { store, sock } = storeWith('state_worldgen', 'worldgen_progress_wg2', 'progress_plan_worldgen',
    'progress_worldgen_wg2', ...extra)
  const w = mountWith(WorldgenScreen, { store })
  await flush()
  sock.sent.length = 0
  return { store, sock, w }
}

describe('building a world', () => {
  test('the bar, and the older line under it', async () => {
    const { store, w } = await building()
    expect(store.screen).toBe('worldgen')
    const old = fixture('worldgen_progress_wg2').data
    expect(one(w, 'worldgen-label').text()).toBe(old.label)
    expect(one(w, 'worldgen-progress').text()).toBe(`${Math.round(old.pct)}%`)
    expect(one(w, 'worldgen-eta').text()).toBe(TEXT.barEta(old.eta_s))
    const bar = one(w, 'loading-bar')
    expect(bar.get('[data-testid="bar-title"]').text()).toBe(fixture('progress_plan_worldgen').data.title)
    expect(bar.findAll('[data-testid="bar-phase"]').length).toBe(10)
  })

  test('no estimate yet, no estimate line', async () => {
    const early = fixture('worldgen_progress_wg2')
    early.data.eta_s = null
    const { w } = await building(early)
    expect(has(w, 'worldgen-eta')).toBe(false)
  })

  test('Cancel stops it and goes back to the wizard', async () => {
    const { store, sock, w } = await building()
    await one(w, 'worldgen-cancel').trigger('click')
    expect(sock.sent).toEqual([{ action: 'worldgen_cancel' }])
    sock.emit({ type: 'as_game', action: 'progress_done', data: { job_id: 'worldgen-1', kind: 'worldgen', ok: false,
      elapsed_s: 12.0 } })
    sock.emit(fixture('state_wizard'))
    expect(store.screen).toBe('wizard')
    expect(store.bar).toBe(null)
  })

  test('a world that cannot be made: its sentence, and the wizard again', async () => {
    const { store, sock } = storeWith('welcome_home', 'pcs')
    const app = mount(PlayApp, { props: { store }, global: { plugins: [vuetify()] } })
    store.go('wizard')
    store.newLife('p10_hopeless:pc/hopeless_hal', { difficulty: 'normal' })
    sock.emit(fixture('state_worldgen'))
    await flush()
    expect(has(app, 'worldgen-screen')).toBe(true)
    sock.emit(fixture('error_worldgen_aborted'))
    sock.emit(fixture('state_wizard'))
    await flush()
    expect(has(app, 'wizard-screen')).toBe(true)
    expect(one(app, 'error-toast').text()).toContain(fixture('error_worldgen_aborted').data.message)
  })

  test('a finished world opens the Play screen', async () => {
    const { store, sock } = await building()
    sock.emit(fixture('progress_done_worldgen'))
    sock.emit(fixture('run_loaded'))
    sock.emit(fixture('view_rich'))
    expect([store.screen, store.bar]).toEqual(['play', null])
  })
})

describe('clarity on the P10 screens (§1)', () => {
  async function wizardAt(step, { more = false } = {}) {
    const { store } = storeWith('pcs')
    store.go('wizard')
    const w = mountWith(WizardScreen, { store })
    await flush()
    if (step > 1) {
      await byId(w, 'pc-card')[1].trigger('click')
      await flush()
    }
    for (let n = 1; n < step; n++) {
      await one(w, 'wizard-next').trigger('click')
      await flush()
    }
    if (more) {
      await one(w, 'more-options-toggle').trigger('click')
      await flush()
    }
    return w
  }

  const SCREENS = [
    ['Wizard: who are you?', () => wizardAt(1)],
    ['Wizard: what kind of world?', () => wizardAt(2)],
    ['Wizard: house rules', () => wizardAt(3, { more: true })],
    ['Wizard: build the world', () => wizardAt(4)],
    ['Worldgen', async () => mountWith(WorldgenScreen, { store: storeWith('state_worldgen', 'worldgen_progress_wg2',
      'progress_plan_worldgen', 'progress_worldgen_wg6').store })],
    ['The bar during a move', async () => mountWith(LoadingBar, { store: storeWith('progress_plan_turn',
      'progress_turn_decide').store, props: { kinds: ['turn'] } })],
    ['The bar during the quiet hours', async () => mountWith(LoadingBar, { store: storeWith('progress_plan_quiet',
      'progress_quiet').store, props: { kinds: ['quiet_hours'] } })],
  ]

  test('UI-CLARITY-01 and -02: no engine words, no internal ids', async () => {
    const banned = new RegExp(`\\b(${BANNED_WORDS.join('|')})s?\\b`, 'i')
    for (const [name, make] of SCREENS) {
      const w = await make()
      await flush()
      const text = readable(w)
      expect(text.length, name).toBeGreaterThan(20)
      const hit = text.match(banned)
      expect(hit && hit[0], `${name}: "${hit && text.slice(Math.max(0, hit.index - 40), hit.index + 40)}"`).toBe(null)
      expect(text, name).not.toMatch(ID_PATTERN)
    }
  })

  test('UI-CLARITY-03: every control has words (its text, or an aria-label)', async () => {
    for (const [name, make] of SCREENS) {
      const w = await make()
      await flush()
      for (const el of w.element.querySelectorAll('button, a, [role="button"], [role="tab"], input:not([type="hidden"]), textarea')) {
        const own = (el.textContent || '').trim() || el.getAttribute('aria-label') || el.getAttribute('placeholder') ||
          el.getAttribute('title') || (el.id && w.element.querySelector(`label[for="${el.id}"]`)?.textContent?.trim()) ||
          el.closest('.v-input')?.querySelector('label')?.textContent?.trim()
        expect(own, `${name}: a control without words: ${el.outerHTML.slice(0, 160)}`).toBeTruthy()
      }
    }
  })
})
