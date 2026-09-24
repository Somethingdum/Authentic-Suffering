// App.vue — the one upstream component change (02 §4.1): Play UI by default, Workshop with ?ui=workshop. PROTECTED.
import { mount } from '@vue/test-utils'
import { h } from 'vue'
import { afterEach, describe, expect, test, vi } from 'vitest'
import { has, vuetify } from './helpers.js'

vi.mock('@/components/TalemateApp.vue', () => ({ default: { name: 'TalemateApp', render: () => h('div', { 'data-testid': 'talemate-app' }) } }))
vi.mock('@/play/PlayApp.vue', () => ({ default: { name: 'PlayApp', render: () => h('div', { 'data-testid': 'play-app' }) } }))

afterEach(() => window.history.replaceState({}, '', '/'))

describe('App.vue', () => {
  test('the Play UI by default; the Workshop (Talemate) with ?ui=workshop', async () => {
    const { default: App } = await import('@/App.vue')
    let w = mount(App, { global: { plugins: [vuetify()] } })
    expect(has(w, 'play-app')).toBe(true)
    expect(has(w, 'talemate-app')).toBe(false)
    window.history.replaceState({}, '', '/?ui=workshop')
    w = mount(App, { global: { plugins: [vuetify()] } })
    expect(has(w, 'talemate-app')).toBe(true)
    expect(has(w, 'play-app')).toBe(false)
  })
})
