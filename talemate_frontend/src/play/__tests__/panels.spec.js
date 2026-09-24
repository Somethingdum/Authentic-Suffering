// The right-hand panels: Your pack, Your body, People, Journal, Map (10_UI §2.5). Each takes the
// PlayView as its one prop and emits `compose` (text for the Do box) — never a state change. PROTECTED.
import { describe, expect, test } from 'vitest'
import BodyPanel from '../panels/BodyPanel.vue'
import JournalPanel from '../panels/JournalPanel.vue'
import MapPanel from '../panels/MapPanel.vue'
import PackPanel from '../panels/PackPanel.vue'
import PeoplePanel from '../panels/PeoplePanel.vue'
import { PANEL_TITLES, TEXT } from '../words.js'
import { byId, fixture, mountWith, one } from './helpers.js'

const view = () => fixture('view_rich').data.view
const panel = (C) => mountWith(C, { props: { view: view() } })

describe('Your pack', () => {
  test('hands, worn, containers with bulk in words, nested contents, the load', async () => {
    const w = panel(PackPanel)
    expect(one(w, 'panel-title').text()).toBe(PANEL_TITLES.pack)
    expect(byId(w, 'pack-hands-item').map((i) => i.text())).toEqual([expect.stringContaining('crowbar')])
    expect(byId(w, 'pack-hands-item')[0].text()).toContain('worn')
    expect(byId(w, 'pack-worn-item')[0].text()).toContain('rain jacket')
    const packs = byId(w, 'pack-container')
    expect(packs.length).toBe(2)
    expect(packs[0].text()).toContain('daypack')
    expect(packs[0].text()).toContain('18/25')
    const inside = byId(w, 'pack-container-item').map((i) => i.text())
    expect(inside.some((t) => t.includes('water bottle') && t.includes('2'))).toBe(true)
    expect(inside.some((t) => t.includes('bandage') && t.includes('3'))).toBe(true)
    expect(one(w, 'pack-load').text()).toContain('moderate')
    expect(one(w, 'pack-load').text()).toContain('9.4 kg')
  })

  test('actions of a nested item compose "<action> the <name>"', async () => {
    const w = panel(PackPanel)
    const bandage = byId(w, 'pack-container-item').find((i) => i.text().includes('bandage'))
    await bandage.trigger('click')
    const actions = byId(w, 'item-action')
    expect(actions.map((a) => a.text())).toEqual(['Take out', 'Use'])
    await actions[1].trigger('click')
    expect(w.emitted('compose')).toEqual([['Use the bandage']])
    expect(w.emitted('send')).toBeUndefined()
  })
})

describe('Your body', () => {
  test('wounds, needs as bars with words, impairment, resolve with its explanation, status', () => {
    const w = panel(BodyPanel)
    expect(one(w, 'panel-title').text()).toBe(PANEL_TITLES.body)
    const wound = one(w, 'body-wound').text()
    for (const bit of ['left forearm', 'cut wound', 'serious', 'bleeding', TEXT.notTreated]) expect(wound).toContain(bit)
    const needs = byId(w, 'body-need')
    expect(needs.map((n) => n.text())).toEqual([expect.stringContaining('Thirst'), expect.stringContaining('Hunger'),
      expect.stringContaining('Tiredness'), expect.stringContaining('Pain')])
    expect(needs[2].text()).toContain('bad')
    expect(needs[2].get('[aria-label]').attributes('aria-label')).toBe('Tiredness: bad')
    expect(one(w, 'body-impairment').text()).toContain('slowed')
    expect(one(w, 'body-resolve').text()).toContain('Resolve 4/6 — shaken')
    expect(one(w, 'body-resolve').attributes('title')).toBe(TEXT.resolveHelp)
    expect(one(w, 'body-status').text()).toContain('crouched')
  })
})

describe('People', () => {
  test("one card per person the character knows, in the character's own words", () => {
    const w = panel(PeoplePanel)
    expect(one(w, 'panel-title').text()).toBe(PANEL_TITLES.people)
    const cards = byId(w, 'person-card').map((c) => c.text())
    expect(cards.length).toBe(2)
    for (const bit of ['Tomas', 'you trust them', 'you owe them', 'here now', 'Tomas keeps the pump running.',
      'Bring Tomas a filter from the depot.', 'alive']) expect(cards[0]).toContain(bit)
    for (const bit of ['the woman with the red scarf', 'last seen day 209, 18:40, Depot road', TEXT.aliveKnown.unknown]) {
      expect(cards[1]).toContain(bit)
    }
  })
})

describe('Journal', () => {
  test('every section, with a plain line when it is empty', () => {
    const w = panel(JournalPanel)
    expect(one(w, 'panel-title').text()).toBe(PANEL_TITLES.journal)
    expect(one(w, 'journal-promises-made').text()).toContain('Bring Tomas a filter from the depot.')
    expect(one(w, 'journal-promises-owed').text()).toContain('Rhea owes you two cans of beans.')
    expect(one(w, 'journal-goals').text()).toContain('Find a water filter.')
    expect(one(w, 'journal-rumours').text()).toContain('Infected nest in the culvert by the mill.')
    expect(one(w, 'journal-lessons').text()).toContain('Rain covers footsteps.')
    expect(one(w, 'journal-dead').text()).toContain(TEXT.nothingYet)
    expect(one(w, 'journal-reputation').text()).toContain(TEXT.nothingYet)
  })
})

describe('Map', () => {
  test('the places the character knows; where they are; the exits they know; travel time', () => {
    const w = panel(MapPanel)
    expect(one(w, 'panel-title').text()).toBe(PANEL_TITLES.map)
    const places = byId(w, 'map-place').map((p) => p.text())
    expect(places[0]).toContain('Pump house')
    expect(places[0]).toContain(TEXT.youAreHere)
    expect(places[1]).not.toContain(TEXT.youAreHere)
    for (const bit of ['Yard', 'Gate', "a minute's walk"]) expect(places[1]).toContain(bit)
  })
})
