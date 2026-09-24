// Play UI test helpers (PROTECTED — docs/as/10_UI.md §3–4). Every spec mounts through these.
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import { createPlayStore } from '../store.js'

const FIXTURES = import.meta.glob('./fixtures/*.json', { eager: true, import: 'default' })

/** A protocol message from fixtures/<name>.json (a deep copy). */
export function fixture(name) {
  const f = FIXTURES[`./fixtures/${name}.json`]
  if (!f) throw new Error(`no fixture ${name}`)
  return JSON.parse(JSON.stringify(f))
}

export function vuetify() {
  return createVuetify({ components, directives })
}

/** A socket with the createSocket() interface (10_UI §3) that records what is sent. */
export function fakeSocket(status = 'open') {
  const handlers = {}
  const statusFns = []
  const s = {
    sent: [],
    status,
    send(msg) { s.sent.push(JSON.parse(JSON.stringify(msg))) },
    on(action, fn) { (handlers[action] ||= []).push(fn) },
    off(action, fn) { handlers[action] = (handlers[action] || []).filter((f) => f !== fn) },
    onStatus(fn) { statusFns.push(fn) },
    close() { s.closed = true },
    // test side
    emit(msg) {
      for (const fn of [...(handlers[msg.action] || []), ...(handlers['*'] || [])]) fn(msg.data, msg)
    },
    setStatus(st) { s.status = st; for (const fn of statusFns) fn(st) },
    actions() { return s.sent.map((m) => m.action) },
    last(action) { return [...s.sent].reverse().find((m) => m.action === action) },
  }
  return s
}

/** A store on a fake socket, fed the named fixture messages in order. */
export function storeWith(...names) {
  const sock = fakeSocket()
  const downloads = []
  const store = createPlayStore(sock, { download: (filename, dataB64) => downloads.push({ filename, dataB64 }) })
  for (const n of names) sock.emit(typeof n === 'string' ? fixture(n) : n)
  return { store, sock, downloads }
}

export function mountWith(component, { store, props = {}, attachTo } = {}) {
  return mount(component, {
    props,
    attachTo,
    global: { plugins: [vuetify()], provide: { playStore: store } },
  })
}

export const byId = (w, id) => w.findAll(`[data-testid="${id}"]`)
export const one = (w, id) => w.get(`[data-testid="${id}"]`)
export const has = (w, id) => w.find(`[data-testid="${id}"]`).exists()

/** The <input>/<textarea> for a test id (the element itself, or inside a Vuetify field). */
export function field(w, id) {
  const el = one(w, id)
  const tag = el.element.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' ? el : el.get('input, textarea')
}

/** Everything a player can read: text, plus aria-labels, titles and placeholders. */
export function readable(w) {
  const root = w.element
  const bits = [root.textContent || '']
  for (const el of root.querySelectorAll('[aria-label], [title], [placeholder]')) {
    for (const a of ['aria-label', 'title', 'placeholder']) {
      const v = el.getAttribute(a)
      if (v) bits.push(v)
    }
  }
  return bits.join(' \n ')
}

export async function flush() {
  await nextTick()
  await nextTick()
}
