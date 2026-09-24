// PlayApp.vue: the screen router, the error notice and the settings dialog (10_UI §3). PROTECTED.
import { mount } from '@vue/test-utils'
import { describe, expect, test } from 'vitest'
import PlayApp from '../PlayApp.vue'
import { TEXT } from '../words.js'
import { byId, fixture, flush, has, one, storeWith, vuetify } from './helpers.js'

function mountApp(store) {
  return mount(PlayApp, { props: { store }, global: { plugins: [vuetify()] } })
}

describe('PlayApp.vue', () => {
  test('routes by store.screen', async () => {
    const { store, sock } = storeWith()
    const w = mountApp(store)
    expect(has(w, 'connect-screen')).toBe(true)
    sock.emit(fixture('welcome_home'))
    await flush()
    expect(has(w, 'home-screen')).toBe(true)
    store.go('content')
    await flush()
    expect(has(w, 'content-screen')).toBe(true)
    sock.emit(fixture('run_loaded'))
    sock.emit(fixture('view_rich'))
    await flush()
    expect(has(w, 'play-screen')).toBe(true)
    for (const later of ['wizard', 'worldgen', 'dead', 'worlds']) {
      store.go(later)
      await flush()
      expect(has(w, 'later-screen'), later).toBe(true)
      expect(one(w, 'later-screen').text()).toContain(TEXT.notBuilt)
    }
    await one(w, 'later-back').trigger('click')
    expect(store.screen).toBe('home')
  })

  test('errors appear as a dismissable notice (never for the other-tab case, which Connect shows)', async () => {
    const { store, sock } = storeWith('welcome_home')
    const w = mountApp(store)
    sock.emit(fixture('error_busy'))
    await flush()
    expect(one(w, 'error-toast').text()).toContain(fixture('error_busy').data.message)
    await one(w, 'error-dismiss').trigger('click')
    await flush()
    expect(has(w, 'error-toast')).toBe(false)
    sock.setStatus('other_tab')
    await flush()
    expect(has(w, 'error-toast')).toBe(false)
    expect(one(w, 'other-tab-notice').text()).toBe(TEXT.otherTab)
  })

  test('the settings dialog opens over any screen', async () => {
    const { store } = storeWith('welcome_home')
    const w = mountApp(store)
    store.openSettings()
    await flush()
    expect(byId(w, 'settings-dialog').length + document.querySelectorAll('[data-testid="settings-dialog"]').length).toBeGreaterThan(0)
  })
})
