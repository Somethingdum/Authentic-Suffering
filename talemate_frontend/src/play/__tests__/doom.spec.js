// The Doom (10_UI §2.6.2; P12, D-106). The owner: everything freezes — the dust, the air, the thing
// you're fighting; about three seconds later the lights go out, even the sun; footsteps; Willis;
// something like a giant mantis takes him, a quarter of a second; then nothing, just you; then the
// Voice. The Voice has no name on any screen. PROTECTED.
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import PlayApp from '../PlayApp.vue'
import DoomOverlay from '../components/DoomOverlay.vue'
import { beatDelay } from '../doom.js'
import { BANNED_WORDS, ID_PATTERN, TEXT } from '../words.js'
import { byId, fixture, flush, has, mountWith, one, readable, storeWith } from './helpers.js'

const BEATS = fixture('doom_scene').data.beats

async function frozen () {
  const { store, sock } = storeWith('run_loaded', 'doom_scene')
  const w = mountWith(DoomOverlay, { store })
  await flush()
  return { store, sock, w }
}

const shown = (w) => byId(w, 'doom-beat').map((x) => x.text())

async function tick (ms) {
  vi.advanceTimersByTime(ms)
  await flush()
}

describe('the Doom', () => {
  beforeEach(() => { vi.useFakeTimers() })
  afterEach(() => { vi.useRealTimers() })

  test('the doom message opens the frozen moment over whatever screen is up', async () => {
    const { store, sock } = storeWith('run_loaded')
    const w = mountWith(PlayApp, { props: { store } })
    await flush()
    expect(has(w, 'doom-overlay')).toBe(false)
    sock.emit(fixture('doom_scene'))
    await flush()
    expect(store.doom.beats).toEqual(BEATS)
    expect(has(w, 'doom-overlay')).toBe(true)
  })

  test('everything stops at once; three seconds later the lights go out', async () => {
    const { w } = await frozen()
    expect(shown(w)).toEqual([BEATS[0].text])
    expect(BEATS[1].pause_ms).toBe(3000)
    await tick(beatDelay(BEATS[0], BEATS[1]) - 1)
    expect(shown(w)).toHaveLength(1)
    await tick(1)
    expect(shown(w)).toEqual([BEATS[0].text, BEATS[1].text])
  })

  test('the beats play in order, each after its pause and the time to read the one before', async () => {
    const { w } = await frozen()
    for (let i = 1; i < BEATS.length; i++) await tick(beatDelay(BEATS[i - 1], BEATS[i]))
    expect(shown(w)).toEqual(BEATS.map((b) => (b.kind === 'willis' ? `${TEXT.death.willis}: ${b.text}` : b.text)))
    expect(byId(w, 'doom-beat').map((x) => x.attributes('data-kind'))).toEqual(BEATS.map((b) => b.kind))
  })

  test('Willis is cut off: the thing takes him a quarter of a second after his last word', async () => {
    const i = BEATS.findIndex((b) => b.kind === 'snatch')
    expect(BEATS[i - 1].kind).toBe('willis')
    expect(BEATS[i].pause_ms).toBe(250)
    expect(beatDelay(BEATS[i - 1], BEATS[i])).toBe(250 + Math.min(20000, 35 * BEATS[i - 1].text.length))
  })

  test('a click shows the next beat now; at the end it lets the moment go', async () => {
    const { store, w } = await frozen()
    for (let i = 1; i < BEATS.length; i++) await one(w, 'doom-next').trigger('click')
    expect(shown(w)).toHaveLength(BEATS.length)
    expect(store.doom).not.toBe(null)
    await one(w, 'doom-next').trigger('click')
    expect(store.doom).toBe(null)
  })

  test('a new run clears it', async () => {
    const { store, sock } = await frozen()
    sock.emit(fixture('run_loaded'))
    expect(store.doom).toBe(null)
  })

  test('UI-CLARITY-01/-02/-03: plain words, no ids, no name for the Voice', async () => {
    const { w } = await frozen()
    for (let i = 1; i < BEATS.length; i++) await one(w, 'doom-next').trigger('click')
    const text = readable(w)
    const banned = new RegExp(`\\b(${BANNED_WORDS.join('|')})s?\\b`, 'i')
    expect(text.match(banned)).toBe(null)
    expect(text).not.toMatch(ID_PATTERN)
    expect(text).not.toMatch(/\bcodex\b/i)
    expect(one(w, 'doom-next').text()).toBe(TEXT.doom.next)
  })
})
