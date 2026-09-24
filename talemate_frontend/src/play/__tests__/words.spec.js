// words.js — every player-facing string in one place, and the word tables of 10_UI §5, which must
// agree with the engine's (service/view.py, narration/location.py). PROTECTED.
import { describe, expect, test } from 'vitest'
import * as W from '../words.js'

describe('word tables agree with the engine (10_UI §5)', () => {
  test.each([
    [100, 'pristine'], [90, 'pristine'], [89, 'good'], [70, 'good'], [69, 'worn'], [45, 'worn'], [44, 'damaged'],
    [25, 'damaged'], [24, 'failing'], [1, 'failing'], [0, 'broken'],
  ])('condition %i -> %s', (n, w) => expect(W.conditionWord(n)).toBe(w))

  test.each([
    [6, 6, 'steady'], [5, 6, 'steady'], [4, 5, 'steady'], [3, 5, 'shaken'], [4, 6, 'shaken'], [2, 5, 'fraying'],
    [1, 5, 'breaking'], [0, 5, 'broken'],
  ])('resolve %i/%i -> %s', (cur, max, w) => expect(W.resolveWord(cur, max)).toBe(w))

  test.each([[0, 'clear-headed'], [1, 'slowed'], [2, 'impaired'], [3, 'impaired'], [4, 'badly impaired'],
    [5, 'badly impaired'], [6, 'barely functioning'], [9, 'barely functioning']])(
    'impairment %i -> %s', (n, w) => expect(W.impairmentWord(n)).toBe(w))

  test.each([[0, 'none'], [0.05, 'oozing'], [0.1, 'bleeding'], [1.49, 'bleeding'], [1.5, 'bleeding badly'],
    [5.9, 'bleeding badly'], [6, 'pouring'], [12, 'pouring']])(
    'bleeding %f %%/min -> %s', (p, w) => expect(W.bleedingWord(p)).toBe(w))

  test.each([['minor', 'minor'], ['significant', 'serious'], ['severe', 'severe'], ['catastrophic', 'critical']])(
    'severity %s -> %s', (s, w) => expect(W.severityWord(s)).toBe(w))

  test.each([[0, 'light'], [0.2, 'light'], [0.21, 'moderate'], [0.35, 'moderate'], [0.36, 'heavy'], [0.5, 'heavy'],
    [0.51, 'overloaded']])('load %f of body mass -> %s', (r, w) => expect(W.loadWord(r)).toBe(w))

  test.each([[20, 'quiet'], [44, 'quiet'], [45, 'some noise'], [69, 'some noise'], [70, 'noisy'], [94, 'noisy'],
    [95, 'deafening']])('noise %i dB -> %s', (db, w) => expect(W.noiseWord(db)).toBe(w))

  test.each([[0, 'fine'], [1, 'fine'], [2, 'noticeable'], [3, 'bad'], [4, 'severe'], [5, 'critical'], [6, 'critical']])(
    'need stage %i -> %s', (n, w) => expect(W.needWord(n)).toBe(w))
})

describe('the fixed strings of 10_UI', () => {
  test('panel titles (UI-CLARITY-05)', () => {
    expect(W.PANEL_TITLES).toEqual({ where: 'Where you are', pack: 'Your pack', body: 'Your body', people: 'People',
      journal: 'Journal', map: 'Map' })
  })

  test('input placeholders and the one-tab message', () => {
    expect(W.TEXT.placeholder).toEqual({ do: 'What do you do?', say: 'What do you say?',
      ask: "Ask the guide anything — it won't cost a turn" })
    expect(W.TEXT.otherTab).toBe('The game is already open in another tab or window. Close that one, then reload this page.')
  })

  test('the banned vocabulary and the id pattern (UI-CLARITY-01, -02)', () => {
    expect(W.BANNED_WORDS).toEqual(['packet', 'affordance', 'percept', 'LOD', 'claim', 'intent', 'handle', 'lane',
      'schema', 'token', 'stage', 'event', 'actor', 'dossier'])
    expect(W.ID_PATTERN.test('act_000123')).toBe(true)
    expect(W.ID_PATTERN.test('pct_000001 and more')).toBe(true)
    expect(W.ID_PATTERN.test('act_12')).toBe(false)
  })

  test('no player-facing string uses engine vocabulary', () => {
    const strings = []
    const walk = (v) => {
      if (typeof v === 'string') strings.push(v)
      else if (v && typeof v === 'object') Object.values(v).forEach(walk)
    }
    walk(W.TEXT)
    walk(W.SETTINGS_TEXT)
    expect(strings.length).toBeGreaterThan(40)
    const banned = new RegExp(`\\b(${W.BANNED_WORDS.join('|')})s?\\b`, 'i')
    for (const s of strings) expect(s, s).not.toMatch(banned)
  })

  test('every run setting a player may change has a label and words for each choice (11_SETTINGS §1.2)', () => {
    const fields = ['turn_depth', 'narration_length', 'narration_person', 'narration_tense', 'pc_voice', 'intensity',
      'show_mechanics', 'read_aloud', 'dev_mode', 'autosave_ring']
    for (const f of fields) {
      const t = W.SETTINGS_TEXT[f]
      expect(t, f).toBeTruthy()
      expect(t.label.length).toBeGreaterThan(2)
      expect(t.help.length).toBeGreaterThan(10)
    }
    expect(Object.keys(W.SETTINGS_TEXT.turn_depth.choices)).toEqual(['quick', 'balanced', 'deep'])
    expect(Object.keys(W.SETTINGS_TEXT.narration_length.choices)).toEqual(['short', 'medium', 'long'])
    expect(Object.keys(W.SETTINGS_TEXT.show_mechanics.choices)).toEqual(['off', 'summary', 'full'])
    expect(Object.keys(W.SETTINGS_TEXT.dev_mode.choices)).toEqual(['false', 'true'])
    expect(W.SETTINGS_TEXT.autosave_ring.choices).toBeUndefined()
  })
})
