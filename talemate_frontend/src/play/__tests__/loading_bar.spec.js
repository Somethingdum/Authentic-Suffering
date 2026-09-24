// The loading bar (10_UI §2.10 and §4; service/progress.py PROG-01..07): every long job's whole
// plan, where it is, live, and one rotating line about the step. PROTECTED.
import { afterEach, describe, expect, test, vi } from 'vitest'
import LoadingBar from '../components/LoadingBar.vue'
import { QUIP_MS, quipLines } from '../quips.js'
import PlayScreen from '../screens/PlayScreen.vue'
import { TEXT } from '../words.js'
import { byId, fixture, flush, has, mountWith, one, storeWith } from './helpers.js'

afterEach(() => vi.useRealTimers())

function mountBar(store, kinds = ['worldgen', 'turn', 'quiet_hours'], random = undefined) {
  return mountWith(LoadingBar, { store, props: random ? { kinds, random } : { kinds } })
}

describe('the bar in the store (§4)', () => {
  test('a plan, its steps, its end — and nobody else\'s', () => {
    const { store, sock } = storeWith()
    const plan = fixture('progress_plan_worldgen').data
    sock.emit(fixture('progress_plan_worldgen'))
    expect(store.bar).toMatchObject({ jobId: 'worldgen-1', kind: 'worldgen', title: plan.title, phase: null, phaseIndex: -1,
      sub: null, subLabel: null, done: null, total: null, pct: 0, elapsed: 0, eta: null, detail: null })
    expect(store.bar.phases).toEqual(plan.phases)
    expect(store.bar.quips).toEqual(plan.quips)
    const d = fixture('progress_worldgen_wg6').data
    sock.emit(fixture('progress_worldgen_wg6'))
    expect(store.bar).toMatchObject({ phase: 'WG6', phaseIndex: 6, sub: 'dossiers', subLabel: d.sub_label, done: 2, total: 3,
      pct: d.pct, elapsed: d.elapsed_s, eta: d.eta_s, detail: null })
    sock.emit(fixture('progress_turn_decide'))
    expect(store.bar.phase).toBe('WG6')
    sock.emit(fixture('progress_done_turn'))
    expect(store.bar).not.toBe(null)
    sock.emit(fixture('progress_done_worldgen'))
    expect(store.bar).toBe(null)
  })

  test('a reloaded page forgets a bar whose plan it never saw', () => {
    const { store, sock } = storeWith('progress_plan_turn')
    expect(store.bar.kind).toBe('turn')
    sock.emit(fixture('welcome_home'))
    expect(store.bar).toBe(null)
  })
})

describe('what the bar shows (§2.10)', () => {
  test('the whole plan in order, nothing lit before the first step', async () => {
    const { store } = storeWith('progress_plan_worldgen')
    const w = mountBar(store)
    await flush()
    const plan = fixture('progress_plan_worldgen').data
    expect(one(w, 'bar-title').text()).toBe(plan.title)
    const phases = byId(w, 'bar-phase')
    expect(phases.map((p) => p.text())).toEqual(plan.phases.map((p) => p.label))
    expect(phases.map((p) => p.attributes('data-phase'))).toEqual(plan.phases.map((p) => p.id))
    expect([...new Set(phases.map((p) => p.attributes('data-state')))]).toEqual(['todo'])
    expect(has(w, 'bar-step')).toBe(false)
    expect(one(w, 'bar-pct').text()).toBe('0%')
  })

  test('where it is: the lit phase, the step, how far, how many, how long', async () => {
    const { store, sock } = storeWith('progress_plan_worldgen')
    const w = mountBar(store)
    sock.emit(fixture('progress_worldgen_wg6'))
    await flush()
    const d = fixture('progress_worldgen_wg6').data
    expect(byId(w, 'bar-phase').map((p) => p.attributes('data-state'))).toEqual(
      [...Array(6).fill('done'), 'current', 'todo', 'todo', 'todo'])
    expect(byId(w, 'bar-phase')[6].attributes('aria-current')).toBe('step')
    expect(byId(w, 'bar-phase').filter((p) => p.attributes('aria-current')).length).toBe(1)
    expect(one(w, 'bar-step').text()).toBe(d.sub_label)
    const fill = one(w, 'bar-fill')
    expect(['role', 'aria-valuemin', 'aria-valuemax', 'aria-valuenow', 'aria-label'].map((a) => fill.attributes(a)))
      .toEqual(['progressbar', '0', '100', String(Math.round(d.pct)), TEXT.barProgress])
    expect(one(w, 'bar-pct').text()).toBe(`${Math.round(d.pct)}%`)
    expect(one(w, 'bar-count').text()).toBe(TEXT.barCount(2, 3))
    expect(one(w, 'bar-elapsed').text()).toBe(TEXT.barElapsed(d.elapsed_s))
    expect(one(w, 'bar-eta').text()).toBe(TEXT.barEta(d.eta_s))
    expect(has(w, 'bar-detail')).toBe(false)
  })

  test('a step without a sub-phase is named by its phase; no estimate, no estimate line', async () => {
    const { store, sock } = storeWith('progress_plan_worldgen')
    const w = mountBar(store)
    const early = fixture('progress_worldgen_wg2')
    early.data.eta_s = null
    sock.emit(early)
    await flush()
    const plan = fixture('progress_plan_worldgen').data
    expect(one(w, 'bar-step').text()).toBe(plan.phases.find((p) => p.id === 'WG2').label)
    expect(has(w, 'bar-eta')).toBe(false)
    expect(has(w, 'bar-count')).toBe(false)
  })

  test('a turn says where, never how many; the detail only in developer mode', async () => {
    let { store, sock } = storeWith('progress_plan_turn')
    let w = mountBar(store)
    sock.emit(fixture('progress_turn_decide'))
    await flush()
    expect(one(w, 'bar-step').text()).toBe('People decide')
    expect(has(w, 'bar-count')).toBe(false)
    expect(has(w, 'bar-detail')).toBe(false)
    ;({ store, sock } = storeWith('progress_plan_turn'))
    w = mountBar(store)
    sock.emit(fixture('progress_turn_dev'))
    await flush()
    expect(one(w, 'bar-detail').text()).toBe('Mara, June')
  })

  test('the quiet hours count what is left to think about', async () => {
    const { store, sock } = storeWith('progress_plan_quiet')
    const w = mountBar(store)
    sock.emit(fixture('progress_quiet'))
    await flush()
    expect(one(w, 'bar-title').text()).toBe(fixture('progress_plan_quiet').data.title)
    expect(one(w, 'bar-count').text()).toBe(TEXT.barCount(1, 3))
  })

  test('only the kinds it is given', async () => {
    const { store } = storeWith('progress_plan_worldgen')
    expect(has(mountBar(store, ['turn', 'quiet_hours']), 'loading-bar')).toBe(false)
    expect(has(mountBar(store, ['worldgen']), 'loading-bar')).toBe(true)
    const none = storeWith()
    expect(has(mountBar(none.store), 'loading-bar')).toBe(false)
  })

  test('the words for time and counts', () => {
    expect(TEXT.barEta(40)).toBe('About 40 s left')
    expect(TEXT.barEta(59)).toBe('About 59 s left')
    expect(TEXT.barEta(60)).toBe('About 1 min left')
    expect(TEXT.barEta(185)).toBe('About 3 min left')
    expect(TEXT.barElapsed(12.4)).toBe('12 s so far')
    expect(TEXT.barElapsed(130)).toBe('2 min so far')
    expect(TEXT.barCount(2, 7)).toBe('2 of 7')
  })
})

describe('the line under the bar (PROG-07)', () => {
  test('a new line every QUIP_MS, drawn with the given random, never one of the last three', async () => {
    vi.useFakeTimers()
    const { store, sock } = storeWith('progress_plan_turn')
    const w = mountBar(store, ['turn'], () => 0)
    sock.emit(fixture('progress_turn_decide'))
    await flush()
    const lines = quipLines(store.bar.quips, 'turn', 'minds', 'decide')
    expect(lines.length).toBeGreaterThan(4)
    const seen = [one(w, 'bar-quip').text()]
    for (let i = 0; i < 6; i++) {
      vi.advanceTimersByTime(QUIP_MS)
      await flush()
      seen.push(one(w, 'bar-quip').text())
    }
    // random() = 0 takes the first line not among the last three shown
    expect(seen).toEqual([lines[0], lines[1], lines[2], lines[3], lines[0], lines[1], lines[2]])
    expect(one(w, 'bar-step').text()).toBe('People decide')
  })

  test('before QUIP_MS nothing changes; a new step brings a line of its own at once', async () => {
    vi.useFakeTimers()
    const { store, sock } = storeWith('progress_plan_worldgen')
    const w = mountBar(store, ['worldgen'], () => 0)
    sock.emit(fixture('progress_worldgen_wg2'))
    await flush()
    const plan = fixture('progress_plan_worldgen').data
    const wg2 = quipLines(plan.quips, 'worldgen', 'WG2', null)
    expect(one(w, 'bar-quip').text()).toBe(wg2[0])
    vi.advanceTimersByTime(QUIP_MS - 100)
    await flush()
    expect(one(w, 'bar-quip').text()).toBe(wg2[0])
    sock.emit(fixture('progress_worldgen_wg6'))
    await flush()
    expect(one(w, 'bar-quip').text()).toBe(quipLines(plan.quips, 'worldgen', 'WG6', 'dossiers')[0])
  })

  test('the line is always the step\'s, never alone', async () => {
    const { store, sock } = storeWith('progress_plan_turn')
    const w = mountBar(store, ['turn'], () => 0.5)
    sock.emit(fixture('progress_turn_decide'))
    await flush()
    expect(quipLines(store.bar.quips, 'turn', 'minds', 'decide')).toContain(one(w, 'bar-quip').text())
    expect(has(w, 'bar-step')).toBe(true)
  })
})

describe('the Play screen during a move', () => {
  test('the quiet hours, then the turn: each bar in its turn, gone at its end', async () => {
    const { store, sock } = storeWith('run_loaded', 'view_rich')
    const w = mountWith(PlayScreen, { store })
    sock.emit({ type: 'as_game', action: 'state', data: { screen: 'play', run_id: 'addison_flores_5c2', busy: true } })
    sock.emit(fixture('progress_plan_quiet'))
    sock.emit(fixture('progress_quiet'))
    await flush()
    expect(one(w, 'loading-bar').get('[data-testid="bar-count"]').text()).toBe(TEXT.barCount(1, 3))
    sock.emit({ type: 'as_game', action: 'progress_done', data: { job_id: 'quiet_hours-42', kind: 'quiet_hours', ok: true,
      elapsed_s: 4.0 } })
    sock.emit(fixture('turn_progress_6'))
    sock.emit(fixture('progress_plan_turn'))
    sock.emit(fixture('progress_turn_decide'))
    await flush()
    expect(has(w, 'turn-progress')).toBe(true)
    expect(one(w, 'loading-bar').get('[data-testid="bar-step"]').text()).toBe('People decide')
    sock.emit(fixture('progress_done_turn'))
    await flush()
    expect(has(w, 'loading-bar')).toBe(false)
  })
})
