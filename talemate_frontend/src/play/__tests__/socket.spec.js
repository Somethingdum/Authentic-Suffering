// socket.js — the one websocket (10_UI §3). PROTECTED.
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest'
import { createSocket, socketUrl } from '../socket.js'

class FakeWS {
  static made = []
  constructor(url) {
    this.url = url
    this.sent = []
    this.closed = false
    FakeWS.made.push(this)
  }
  send(text) { this.sent.push(JSON.parse(text)) }
  close() { this.closed = true }
  // test side
  open() { this.onopen?.({}) }
  drop() { this.onclose?.({}) }
  receive(obj) { this.onmessage?.({ data: JSON.stringify(obj) }) }
}

beforeEach(() => { FakeWS.made = []; vi.useFakeTimers() })
afterEach(() => vi.useRealTimers())

describe('socketUrl', () => {
  test("Talemate's rule: a valid ws:// env URL, else port 5050 on the page's host", () => {
    expect(socketUrl(undefined, 'http://localhost:8082/')).toBe('ws://localhost:5050/ws')
    expect(socketUrl('${VITE_TALEMATE_BACKEND_WEBSOCKET_URL}', 'http://192.168.1.5:8082/')).toBe('ws://192.168.1.5:5050/ws')
    expect(socketUrl('wss://game.example:5050/ws', 'http://x:8082/')).toBe('wss://game.example:5050/ws')
    expect(socketUrl('ws://0.0.0.0:5050/ws', 'http://192.168.1.5:8082/?ui=play')).toBe('ws://192.168.1.5:5050/ws')
  })
})

describe('createSocket', () => {
  test('connects at once, wraps every send in type as_game, and queues sends until open', () => {
    const statuses = []
    const s = createSocket('ws://h:5050/ws', { WebSocketImpl: FakeWS })
    s.onStatus((st) => statuses.push(st))
    expect(FakeWS.made.length).toBe(1)
    expect(FakeWS.made[0].url).toBe('ws://h:5050/ws')
    expect(s.status).toBe('connecting')
    s.send({ action: 'hello', client_version: '1' })
    s.send({ action: 'get_state' })
    expect(FakeWS.made[0].sent).toEqual([])
    FakeWS.made[0].open()
    expect(s.status).toBe('open')
    expect(statuses).toEqual(['open'])
    expect(FakeWS.made[0].sent).toEqual([{ type: 'as_game', action: 'hello', client_version: '1' },
      { type: 'as_game', action: 'get_state' }])
    s.send({ action: 'view_get' })
    expect(FakeWS.made[0].sent.at(-1)).toEqual({ type: 'as_game', action: 'view_get' })
  })

  test('dispatches as_game messages by action and ignores every other type', () => {
    const s = createSocket('ws://h:5050/ws', { WebSocketImpl: FakeWS })
    const got = []
    const all = []
    const onView = (data, msg) => got.push([data, msg.action])
    s.on('view', onView)
    s.on('*', (data, msg) => all.push(msg.action))
    FakeWS.made[0].open()
    FakeWS.made[0].receive({ type: 'as_game', action: 'view', data: { view: 1 } })
    FakeWS.made[0].receive({ type: 'as_game', action: 'story', data: { entries: [] } })
    FakeWS.made[0].receive({ type: 'client_status', status: 'idle' })
    FakeWS.made[0].receive({ type: 'system', status: 'success', message: 'ok' })
    expect(got).toEqual([[{ view: 1 }, 'view']])
    expect(all).toEqual(['view', 'story'])
    s.off('view', onView)
    FakeWS.made[0].receive({ type: 'as_game', action: 'view', data: { view: 2 } })
    expect(got.length).toBe(1)
  })

  test('reconnects with backoff 1 s, 2 s, 4 s, 8 s, then every 10 s; an open resets it', () => {
    const s = createSocket('ws://h:5050/ws', { WebSocketImpl: FakeWS })
    const statuses = []
    s.onStatus((st) => statuses.push(st))
    const expectNextAfter = (ms) => {
      const n = FakeWS.made.length
      vi.advanceTimersByTime(ms - 1)
      expect(FakeWS.made.length).toBe(n)
      vi.advanceTimersByTime(1)
      expect(FakeWS.made.length).toBe(n + 1)
    }
    FakeWS.made.at(-1).drop()
    expect(s.status).toBe('closed')
    expectNextAfter(1000)
    FakeWS.made.at(-1).drop()
    expectNextAfter(2000)
    FakeWS.made.at(-1).drop()
    expectNextAfter(4000)
    FakeWS.made.at(-1).drop()
    expectNextAfter(8000)
    FakeWS.made.at(-1).drop()
    expectNextAfter(10000)
    FakeWS.made.at(-1).drop()
    expectNextAfter(10000)
    FakeWS.made.at(-1).open()
    FakeWS.made.at(-1).drop()
    expectNextAfter(1000)
    expect(statuses[0]).toBe('closed')
    expect(statuses).toContain('open')
  })

  test('a second tab: Talemate refuses it, and the socket stops for good', () => {
    const s = createSocket('ws://h:5050/ws', { WebSocketImpl: FakeWS })
    const statuses = []
    s.onStatus((st) => statuses.push(st))
    FakeWS.made[0].open()
    FakeWS.made[0].receive({ type: 'system', status: 'error',
      message: 'Another Talemate frontend is already connected. Only one connection is allowed.' })
    FakeWS.made[0].drop()
    expect(s.status).toBe('other_tab')
    expect(statuses).toEqual(['open', 'other_tab'])
    vi.advanceTimersByTime(60000)
    expect(FakeWS.made.length).toBe(1)
  })

  test('close() stops reconnecting', () => {
    const s = createSocket('ws://h:5050/ws', { WebSocketImpl: FakeWS })
    FakeWS.made[0].open()
    s.close()
    expect(FakeWS.made[0].closed).toBe(true)
    FakeWS.made[0].drop()
    vi.advanceTimersByTime(60000)
    expect(FakeWS.made.length).toBe(1)
  })
})
