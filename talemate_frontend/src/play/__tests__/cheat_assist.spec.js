// The Cheat field's autocomplete and dictionary (P12, D-115; CHEAT-20, CHEAT-21; 10_UI §2.6 Input). The owner:
// "There needs to be an auto complete that shows all of the options, and a dictionary on that same menu so I
// don't get confused. I should also just be able to say 'Spawn Fredrick' in the cheats thing." PROTECTED.
import { describe, expect, test } from 'vitest'
import { SLOT_WORDS, argless, currentCommand, dictionaryRows, quoted, suggest } from '../cheatAssist.js'
import { BANNED_WORDS, TEXT } from '../words.js'
import { fixture, storeWith } from './helpers.js'

const COMMANDS = fixture('cheat_dictionary').data.commands
const names = (xs) => xs.map((x) => x.label)
const inserts = (xs) => xs.map((x) => x.insert)

describe('the command word', () => {
  test('an empty field offers every command, in the server order', () => {
    const all = suggest('', COMMANDS)
    expect(names(all)).toEqual(COMMANDS.map((c) => c.name))
    expect(all.every((s) => s.kind === 'command' && s.hint === COMMANDS.find((c) => c.name === s.label).meaning)).toBe(true)
  })

  test('typing narrows it; a command that takes something leaves a space for it', () => {
    expect(inserts(suggest('sp', COMMANDS))).toEqual(['spawn '])
    expect(inserts(suggest('Sp', COMMANDS))).toEqual(['spawn '])
    expect(inserts(suggest('/he', COMMANDS))).toEqual(['/help', '/heal '])
    expect(inserts(suggest('cen', COMMANDS))).toEqual(['census'])
    expect(suggest('zz', COMMANDS)).toEqual([])
    expect(suggest('sp', [])).toEqual([])
  })

  test('a command takes nothing only when it has no blanks and its usage is the bare word', () => {
    expect(COMMANDS.filter(argless).map((c) => c.name)).toEqual(['help', 'off', 'reveal', 'mega', 'census'])
    expect(currentCommand('Spawn Fredrick', COMMANDS).name).toBe('spawn')
    expect(currentCommand('/give', COMMANDS).name).toBe('give')
    expect(currentCommand('Make that infected jig joyously', COMMANDS)).toBe(null)
  })
})

describe('the blanks', () => {
  test('what can fill the blank, from what is being typed', () => {
    expect(inserts(suggest('Spawn fr', COMMANDS))).toEqual(['Spawn fredrick '])
    const s = suggest('spawn ', COMMANDS)
    expect(names(s)).toEqual(COMMANDS.find((c) => c.name === 'spawn').slots.what)
    expect(s.every((x) => x.kind === 'option' && x.slot === 'what')).toBe(true)
    expect(names(suggest('tp s', COMMANDS))).toEqual(['Sales floor', 'Stockroom'])
  })

  test('an option with a space goes in quoted; a run of typed words finds it', () => {
    expect(quoted('Glock 19')).toBe('"Glock 19"')
    expect(quoted('crowbar')).toBe('crowbar')
    expect(inserts(suggest('give band', COMMANDS))).toEqual(['give "bandage roll" ', 'give bandana '])
    expect(inserts(suggest('give bandage ro', COMMANDS))).toEqual(['give "bandage roll" '])
    expect(inserts(suggest('give "bandage ro', COMMANDS))).toEqual(['give "bandage roll" '])
    expect(inserts(suggest('/give gl', COMMANDS))).toEqual(['/give "Glock 19" '])
  })

  test('the word before says which blank comes first', () => {
    expect(SLOT_WORDS).toEqual(['to', 'about', 'with', 'at'])
    const to = suggest('give "Glock 19" to ', COMMANDS)
    expect(to[0]).toEqual({ kind: 'option', label: 'me', slot: 'person', hint: null, insert: 'give "Glock 19" to me ' })
    expect(names(suggest('give "Glock 19" to Ma', COMMANDS))).toEqual(['Mara'])
    expect(suggest('infect June with ', COMMANDS)[0].slot).toBe('strain')
    expect(suggest('infect ', COMMANDS)[0].slot).toBe('person')
    expect(suggest('forget June about ', COMMANDS)[0].slot).toBe('place')
  })

  test('plain words and commands without blanks get nothing', () => {
    expect(suggest('Make that infected jig joyously', COMMANDS)).toEqual([])
    expect(suggest('census ', COMMANDS)).toEqual([])
    expect(suggest('time +', COMMANDS)).toEqual([])
    expect(suggest('kill zzz', COMMANDS)).toEqual([])
  })

  test('every option offered can be counted on: no repeats, and at most what was asked', () => {
    const s = suggest('give ', COMMANDS)
    expect(new Set(names(s).map((x) => x.toLowerCase())).size).toBe(s.length)
    expect(suggest('give ', COMMANDS, 3)).toHaveLength(3)
  })
})

describe('the dictionary', () => {
  test('every command with what it does and an example; a filter; the one being typed is marked', () => {
    const rows = dictionaryRows(COMMANDS)
    expect(rows.map((r) => r.name)).toEqual(COMMANDS.map((c) => c.name))
    expect(rows.every((r) => r.usage && r.meaning && r.example.startsWith(`/${r.name}`))).toBe(true)
    expect(rows.filter((r) => r.current)).toEqual([])
    const dead = dictionaryRows(COMMANDS, 'DEAD').map((r) => r.name)
    expect(dead).toEqual(expect.arrayContaining(['spawn', 'horde', 'census']))
    expect(dead).not.toContain('give')
    expect(dictionaryRows(COMMANDS, '', 'Spawn fr').filter((r) => r.current).map((r) => r.name)).toEqual(['spawn'])
    expect(dictionaryRows(COMMANDS, 'nothing like this')).toEqual([])
  })

  test('its words are plain', () => {
    const banned = new RegExp(`\\b(${BANNED_WORDS.join('|')})s?\\b`, 'i')
    const strings = [TEXT.cheat.dictionary, TEXT.cheat.filter, TEXT.cheat.none, TEXT.cheat.example,
      ...Object.values(TEXT.cheat.slot), ...COMMANDS.flatMap((c) => [c.meaning, c.usage])]
    for (const s of strings) expect(s, s).not.toMatch(banned)
    for (const c of COMMANDS) for (const slot of Object.keys(c.slots)) expect(TEXT.cheat.slot[slot], slot).toBeTruthy()
  })
})

describe('the store', () => {
  test('the words arrive, and leave with the console or the run', () => {
    const { store, sock } = storeWith('run_loaded')
    expect(store.cheatCommands).toEqual([])
    sock.sent.length = 0
    store.getCheatDictionary()
    expect(sock.sent).toEqual([{ action: 'cheat_dictionary_get' }])
    sock.emit(fixture('cheat_dictionary'))
    expect(store.cheatCommands).toEqual(COMMANDS)
    const open = fixture('view_rich')
    open.data.view.console = true
    sock.emit(open)
    expect(store.cheatCommands).toEqual(COMMANDS)
    const closed = fixture('view_rich')
    closed.data.view.console = false
    sock.emit(closed)
    expect(store.cheatCommands).toEqual([])
    sock.emit(fixture('cheat_dictionary'))
    sock.emit(fixture('run_loaded'))
    expect(store.cheatCommands).toEqual([])
  })
})
