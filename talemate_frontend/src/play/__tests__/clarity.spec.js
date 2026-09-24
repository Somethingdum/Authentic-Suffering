// The clarity rules over every P8 screen (10_UI §1): UI-CLARITY-01 (no engine words), -02 (no internal
// ids), -03 (every control has words), -05 (plain panel titles). The Developer panel is the exception to
// -01 and is left out here; the Content screen is an authoring screen and may name record kinds
// ("dossier", "affordance", "actor": the pack folders are called that, 09_CONTENT_PACKS). PROTECTED.
import { describe, expect, test } from 'vitest'
import SettingsDialog from '../components/SettingsDialog.vue'
import ConnectScreen from '../screens/ConnectScreen.vue'
import ContentScreen from '../screens/ContentScreen.vue'
import HomeScreen from '../screens/HomeScreen.vue'
import PlayScreen from '../screens/PlayScreen.vue'
import SessionsScreen from '../screens/SessionsScreen.vue'
import { BANNED_WORDS, ID_PATTERN, PANEL_TITLES } from '../words.js'
import { byId, flush, mountWith, one, readable, storeWith } from './helpers.js'

const PLAY_STATES = {
  'a rich moment, mid-turn': ['run_loaded', 'view_rich', 'story_anchor', 'settings', 'turn_progress_6'],
  'after a rejection': ['run_loaded', 'view_rich', 'story_anchor', 'settings', 'turn_rejected'],
  'the anchor turn of the slice': ['run_loaded', 'view_anchor', 'story_anchor', 'settings'],
  'dead, in a Sandbox run': ['view_dead_sandbox', 'story_anchor', 'settings'],
}

async function screens() {
  const out = []
  for (const [name, msgs] of Object.entries(PLAY_STATES)) {
    const { store } = storeWith(...msgs)
    out.push([`Play: ${name}`, mountWith(PlayScreen, { store }), false])
  }
  let s = storeWith('welcome_connect', 'config', 'models_a', 'models_b', 'test_a_ok', 'test_b_down')
  out.push(['Connect', mountWith(ConnectScreen, { store: s.store }), false])
  s = storeWith('welcome_home', 'runs')
  out.push(['Home', mountWith(HomeScreen, { store: s.store }), false])
  s = storeWith('welcome_home', 'runs')
  out.push(['Your lives', mountWith(SessionsScreen, { store: s.store }), false])
  s = storeWith('welcome_home', 'packs', 'content_report_bad')
  out.push(['Your characters & world', mountWith(ContentScreen, { store: s.store }), true])
  for (const tab of ['models', 'gameplay', 'advanced']) {
    s = storeWith('run_loaded', 'view_rich', 'settings', 'config', 'models_a', 'models_b')
    s.store.openSettings()
    const d = mountWith(SettingsDialog, { store: s.store })
    await one(d, `settings-tab-${tab}`).trigger('click')
    out.push([`Settings: ${tab}`, d, false])
  }
  await flush()
  return out
}

describe('clarity', () => {
  test('UI-CLARITY-01: no engine vocabulary anywhere a player can read', async () => {
    for (const [name, w, authoring] of await screens()) {
      const words = BANNED_WORDS.filter((b) => !(authoring && ['dossier', 'affordance', 'actor'].includes(b)))
      const banned = new RegExp(`\\b(${words.join('|')})s?\\b`, 'i')
      const text = readable(w)
      expect(text.length, name).toBeGreaterThan(40)
      const hit = text.match(banned)
      expect(hit && hit[0], `${name}: "${hit && text.slice(Math.max(0, hit.index - 40), hit.index + 40)}"`).toBe(null)
    }
  })

  test('UI-CLARITY-02: no internal ids on screen', async () => {
    for (const [name, w] of await screens()) expect(readable(w), name).not.toMatch(ID_PATTERN)
  })

  test('UI-CLARITY-03: every control has words (its text, or an aria-label)', async () => {
    for (const [name, w] of await screens()) {
      const controls = w.element.querySelectorAll('button, a, [role="button"], [role="tab"], input:not([type="hidden"]), textarea')
      expect(controls.length, name).toBeGreaterThan(0)
      for (const el of controls) {
        const own = (el.textContent || '').trim() || el.getAttribute('aria-label') || el.getAttribute('placeholder') ||
          el.getAttribute('title') || (el.id && w.element.querySelector(`label[for="${el.id}"]`)?.textContent?.trim()) ||
          el.closest('.v-input')?.querySelector('label')?.textContent?.trim()
        expect(own, `${name}: a control without words: ${el.outerHTML.slice(0, 160)}`).toBeTruthy()
      }
    }
  })

  test('UI-CLARITY-05: panel titles are the plain nouns', async () => {
    const titles = new Set(Object.values(PANEL_TITLES))
    for (const [name, w] of await screens()) {
      for (const t of byId(w, 'panel-title')) expect(titles.has(t.text().trim()), `${name}: ${t.text()}`).toBe(true)
    }
  })

  test('refs are handles for the server, never words on the page (UI-REF-01)', async () => {
    const { store } = storeWith('run_loaded', 'view_rich', 'settings')
    const w = mountWith(PlayScreen, { store })
    await flush()
    expect(readable(w)).not.toMatch(/\b[pixms]\d{1,3}\b/)
  })
})
