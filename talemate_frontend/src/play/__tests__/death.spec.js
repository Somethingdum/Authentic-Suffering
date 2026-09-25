// The death screen, and Willis at every death (10_UI §2.6; P12, D-105: "When you die, regardless of
// Wildcard activation, you see Willis. He mocks and roasts you joyously over your mistakes."). He came
// in the frozen moment (D-106, doom.spec.js); the screen keeps his lines and the Voice's words. PROTECTED.
import { describe, expect, test } from 'vitest'
import DeathScreen from '../screens/DeathScreen.vue'
import { BANNED_WORDS, ID_PATTERN, TEXT } from '../words.js'
import { byId, fixture, flush, has, mountWith, one, readable, storeWith } from './helpers.js'

async function dead(...names) {
  const { store, sock } = storeWith('run_loaded', ...names)
  const w = mountWith(DeathScreen, { store })
  await flush()
  sock.sent.length = 0
  return { store, sock, w }
}

const lines = (w, id) => byId(w, id).map((x) => x.text())

describe('the death screen', () => {
  test("Willis's lines and the Voice's words are there at once; its last word follows", async () => {
    const { store, sock, w } = await dead('death_voice_pending')
    const first = fixture('death_voice_pending').data.death
    expect(store.screen).toBe('dead')
    expect(one(w, 'death-willis').text()).toContain(TEXT.death.willis)
    expect(has(w, 'death-willis-pending')).toBe(false)
    expect(lines(w, 'death-willis-line')).toEqual(first.willis)
    expect(one(w, 'death-voice').text()).toContain(TEXT.death.voice)
    expect(lines(w, 'death-voice-line')).toEqual(first.voice)
    expect(one(w, 'death-voice-pending').text()).toBe(TEXT.death.voicePending)
    sock.emit(fixture('death_willis'))
    await flush()
    const d = fixture('death_willis').data.death
    expect(has(w, 'death-voice-pending')).toBe(false)
    expect(lines(w, 'death-voice-line')).toEqual(d.voice)
    expect(d.voice.slice(0, first.voice.length)).toEqual(first.voice)
  })

  test('a server that still sends Willis late: he is on his way', async () => {
    const late = fixture('death_voice_pending')
    Object.assign(late.data.death, { willis: [], willis_pending: true, voice: [], voice_pending: false })
    const { w } = await dead(late)
    expect(one(w, 'death-willis-pending').text()).toBe(TEXT.death.willisArriving)
    expect(byId(w, 'death-willis-line')).toEqual([])
    expect(has(w, 'death-voice')).toBe(false)
  })

  test("the dead person's own story: who, when, how, the last moments, their own choices", async () => {
    const { w } = await dead('death_willis')
    const d = fixture('death_willis').data.death
    expect(one(w, 'death-title').text()).toBe(TEXT.death.title('Owen Marsh'))
    expect(one(w, 'death-when').text()).toBe(TEXT.death.when(212, '06:05'))
    expect(one(w, 'death-cause').text()).toBe(d.cause_text)
    expect(lines(w, 'death-last-turns')).toEqual(d.last_turns)
    expect(lines(w, 'death-contributing')).toEqual(d.contributing)
  })

  test('the truth only when asked, after a warning (DEATH-10)', async () => {
    const { sock, w } = await dead('death_willis')
    expect(has(w, 'death-reveal')).toBe(false)
    await one(w, 'death-reveal-button').trigger('click')
    expect(one(w, 'death-reveal-warning').text()).toContain(TEXT.death.revealWarning)
    expect(sock.sent).toEqual([])
    await one(w, 'death-reveal-cancel').trigger('click')
    expect(has(w, 'death-reveal-warning')).toBe(false)
    await one(w, 'death-reveal-button').trigger('click')
    await one(w, 'death-reveal-confirm').trigger('click')
    expect(sock.sent).toEqual([{ action: 'death_reveal' }])
    sock.emit(fixture('death_revealed'))
    await flush()
    expect(lines(w, 'death-reveal-line')).toEqual(fixture('death_revealed').data.death.truth_reveal)
    expect(has(w, 'death-reveal-button')).toBe(false)
  })

  test('Ironman: the life is over, there is no loading back', async () => {
    const { store, w } = await dead('death_ironman')
    expect(one(w, 'death-ironman').text()).toBe(TEXT.death.ironman)
    expect(has(w, 'death-load')).toBe(false)
    await one(w, 'death-new-world').trigger('click')
    expect(store.screen).toBe('wizard')
  })

  test('otherwise a save can be loaded', async () => {
    const { store, w } = await dead('death_willis')
    expect(has(w, 'death-ironman')).toBe(false)
    await one(w, 'death-load').trigger('click')
    expect(store.screen).toBe('home')
  })

  test('UI-CLARITY-01/-02/-03: plain words, no ids, every control says what it does', async () => {
    const { w } = await dead('death_revealed')
    const text = readable(w)
    const banned = new RegExp(`\\b(${BANNED_WORDS.join('|')})s?\\b`, 'i')
    expect(text.match(banned)).toBe(null)
    expect(text).not.toMatch(ID_PATTERN)
    for (const b of w.findAll('button')) expect(b.text().trim().length).toBeGreaterThan(1)
  })
})
