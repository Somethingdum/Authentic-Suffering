// quips.js — which line the loading bar shows (10_UI §2.10; service/progress.py PROG-07). PROTECTED.
import { describe, expect, test } from 'vitest'
import { QUIP_MS, nextQuip, quipLines } from '../quips.js'
import { fixture } from './helpers.js'

describe('quipLines: the most specific list that has lines', () => {
  const q = { turn: ['a', 'b', 'c'], 'turn.minds': ['m1', 'm2', 'm3'], 'turn.minds.decide': ['d1', 'd2', 'd3', 'd4'],
    'turn.world.act': [] }

  test('the sub-phase, then the phase, then the plan', () => {
    expect(quipLines(q, 'turn', 'minds', 'decide')).toEqual(['d1', 'd2', 'd3', 'd4'])
    expect(quipLines(q, 'turn', 'minds', 'other')).toEqual(['m1', 'm2', 'm3'])
    expect(quipLines(q, 'turn', 'minds', null)).toEqual(['m1', 'm2', 'm3'])
    expect(quipLines(q, 'turn', 'world', 'act')).toEqual(['a', 'b', 'c'])      // an empty list does not count
    expect(quipLines(q, 'worldgen', 'WG0', null)).toEqual([])
    expect(quipLines({}, 'turn', null, null)).toEqual([])
  })

  test('the core lines cover every step of a turn and of a world', () => {
    for (const name of ['progress_plan_turn', 'progress_plan_worldgen', 'progress_plan_quiet']) {
      const plan = fixture(name).data
      for (const p of plan.phases) {
        expect(quipLines(plan.quips, plan.kind, p.id, null).length, `${plan.kind}.${p.id}`).toBeGreaterThanOrEqual(3)
        for (const s of p.subs) expect(quipLines(plan.quips, plan.kind, p.id, s.id).length).toBeGreaterThanOrEqual(3)
      }
    }
  })
})

describe('nextQuip: drawn at random, never one of the last three shown', () => {
  test('the draw is over the lines not shown lately, in their order', () => {
    const lines = ['a', 'b', 'c', 'd', 'e']
    expect(nextQuip(lines, [], () => 0)).toBe('a')
    expect(nextQuip(lines, [], () => 0.99)).toBe('e')
    expect(nextQuip(lines, ['a', 'b', 'c'], () => 0)).toBe('d')
    expect(nextQuip(lines, ['a', 'b', 'c'], () => 0.99)).toBe('e')
    expect(nextQuip(lines, ['d', 'a', 'b', 'c'], () => 0)).toBe('d')     // only the last three are barred
  })

  test('short lists still give a line', () => {
    expect(nextQuip([], [], () => 0)).toBe(null)
    expect(nextQuip(['a'], ['a', 'a'], () => 0.5)).toBe('a')
    expect(nextQuip(['a', 'b'], ['a'], () => 0)).toBe('b')
    expect(nextQuip(['a', 'b', 'c'], ['c', 'a'], () => 0)).toBe('b')
  })

  test('a long run never shows one of the last three again, and shows them all', () => {
    let seed = 7
    const random = () => { seed = (seed * 16807) % 2147483647; return (seed - 1) / 2147483646 }
    const lines = ['a', 'b', 'c', 'd', 'e', 'f']
    const shown = []
    for (let i = 0; i < 200; i++) {
      const q = nextQuip(lines, shown, random)
      expect(shown.slice(-3)).not.toContain(q)
      shown.push(q)
    }
    expect(new Set(shown).size).toBe(6)
  })

  test('a new line every two and a half seconds', () => expect(QUIP_MS).toBe(2500))
})
