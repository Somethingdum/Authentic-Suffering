// The Play screen: top bar, Where you are, the story, the input box and the turn in progress
// (10_UI §2.5). PROTECTED.
import { describe, expect, test } from 'vitest'
import PlayScreen from '../screens/PlayScreen.vue'
import { PANEL_TITLES, TEXT } from '../words.js'
import { byId, field, fixture, flush, has, mountWith, one, storeWith } from './helpers.js'

async function play(...names) {
  const { store, sock } = storeWith('run_loaded', ...names)
  const w = mountWith(PlayScreen, { store })
  await flush()
  sock.sent.length = 0
  return { store, sock, w }
}

describe('top bar', () => {
  test('who, when, the models in words, save and settings', async () => {
    const { w, sock, store } = await play('view_rich')
    expect(one(w, 'topbar-pc-name').text()).toBe('Addison Flores')
    expect(one(w, 'topbar-day').text()).toContain('212')
    const clock = one(w, 'topbar-clock').text()
    for (const bit of ['06:05', 'dawn', 'Raining']) expect(clock).toContain(bit)
    expect(has(w, 'sandbox-badge')).toBe(false)
    expect(one(w, 'lane-dot-A').attributes('aria-label')).toBe('Main model: working')
    expect(one(w, 'lane-dot-B').attributes('aria-label')).toBe('Second model: not answering')
    expect(has(w, 'topbar-save')).toBe(false)             // run_loaded fixture is an Ironman run
    await one(w, 'topbar-settings').trigger('click')
    expect(store.settingsOpen).toBe(true)
    await one(w, 'topbar-quit').trigger('click')
    expect(sock.sent).toEqual([{ action: 'run_close' }])
  })

  test('a Sandbox run says so; a free run can be saved under a name', async () => {
    const { store, sock } = storeWith('view_dead_sandbox')
    const w = mountWith(PlayScreen, { store })
    await flush()
    expect(one(w, 'sandbox-badge').text()).toBe('Sandbox')
    await one(w, 'topbar-save').trigger('click')
    await field(w, 'save-name').setValue('Before the depot')
    sock.sent.length = 0
    await one(w, 'save-confirm').trigger('click')
    expect(sock.sent).toEqual([{ action: 'run_save', slot_name: 'Before the depot' }])
    sock.emit(fixture('saved'))
    await flush()
    expect(one(w, 'saved-notice').text()).toContain('Before the depot')
  })
})

describe('Where you are', () => {
  test('everything the character perceives, in words; built by code (narration/location.py)', async () => {
    const { w, sock } = await play('view_rich')
    const where = one(w, 'where-panel')
    expect(where.get('[data-testid="panel-title"]').text()).toBe(PANEL_TITLES.where)
    expect(one(w, 'loc-place-name').text()).toBe('Pump house')
    expect(one(w, 'loc-area-name').text()).toBe('Mill Creek settlement')
    expect(byId(w, 'loc-description-line').map((l) => l.text())).toEqual(fixture('view_rich').data.view.location.description_lines)
    expect(byId(w, 'loc-seen-item').map((l) => l.text())).toEqual(['hand pump — rusted', 'jerrycan'])
    const people = byId(w, 'loc-person').map((l) => l.text())
    expect(people[0]).toContain('Tomas')
    expect(people[0]).toContain('hurt')
    expect(people[1]).toContain('a figure')
    const exits = byId(w, 'loc-exit').map((l) => l.text())
    for (const bit of ['Steel door', 'closed', 'locked', 'Yard']) expect(exits[0]).toContain(bit)
    expect(exits[1]).toContain('Window')
    expect(exits[1]).not.toContain('unknown')
    expect(byId(w, 'loc-danger').map((l) => l.text())).toEqual(['Infected in the culvert (a rumour)'])
    expect(one(w, 'loc-noise').text()).toContain('some noise')
    await one(w, 'loc-look-closer').trigger('click')
    expect(sock.sent).toEqual([{ action: 'turn_submit', mode: 'do', text: TEXT.lookCloser, suggestion_ref: null,
      addressee_refs: [] }])
  })
})

describe('the story', () => {
  test('entries by kind; player entries carry their mode; guide answers are side notes', async () => {
    const { w } = await play('view_anchor', 'story_anchor')
    const entries = byId(w, 'story-entry')
    const story = fixture('story_anchor').data.entries
    expect(entries.length).toBe(story.length)
    expect(entries.map((e) => e.attributes('data-kind'))).toEqual(story.map((e) => e.kind))
    const player = entries.find((e) => e.attributes('data-kind') === 'player')
    expect(player.text()).toContain(TEXT.modeLabel.do)
    expect(player.text()).toContain('I watch the front window and keep quiet.')
    const guide = entries.find((e) => e.attributes('data-kind') === 'guide')
    expect(guide.text()).toContain(TEXT.guideLabel)
    expect(entries.find((e) => e.attributes('data-kind') === 'narration').text()).toBe(story.find((e) => e.kind === 'narration').text)
  })

  test('the receipt appears only when the view carries one (Show dice not off)', async () => {
    let { w } = await play('view_rich')
    expect(one(w, 'mechanics-receipt').text()).toContain('Force the steel door: failure')
    ;({ w } = await play('view_anchor'))
    const m = fixture('view_anchor').data.view.mechanics
    expect(has(w, 'mechanics-receipt')).toBe(m !== null && m.lines.length > 0)
  })
})

describe('a turn in progress', () => {
  test('friendly label, seconds, and Stop until the world moves', async () => {
    const { w, sock } = await play('view_rich')
    expect(has(w, 'turn-progress')).toBe(false)
    sock.emit({ type: 'as_game', action: 'state', data: { screen: 'play', run_id: 'addison_flores_5c2', busy: true } })
    sock.emit(fixture('turn_progress_6'))
    await flush()
    expect(one(w, 'turn-progress-label').text()).toBe('People decide…')
    expect(one(w, 'turn-elapsed').text()).toContain('12')
    expect(has(w, 'turn-stop')).toBe(true)
    await one(w, 'turn-stop').trigger('click')
    expect(sock.sent).toEqual([{ action: 'turn_cancel' }])
    sock.emit(fixture('turn_progress_12'))
    await flush()
    expect(one(w, 'turn-progress-label').text()).toBe('Locking it in…')
    expect(has(w, 'turn-stop')).toBe(false)
    expect(one(w, 'input-send').attributes('disabled')).toBeDefined()
  })

  test('a rejection banner with the reason and the question', async () => {
    const { w, sock } = await play('view_rich')
    sock.emit(fixture('turn_rejected'))
    await flush()
    const banner = one(w, 'rejection-banner').text()
    expect(banner).toContain("It isn't clear what you want to do.")
    expect(banner).toContain('Do you want to force the door or pick the lock?')
  })

  test('notices from loading are shown until dismissed', async () => {
    const { w } = await play('view_rich')
    expect(one(w, 'load-notice').text()).toContain('Your content changed')
    await one(w, 'load-notice-dismiss').trigger('click')
    await flush()
    expect(has(w, 'load-notice')).toBe(false)
  })
})

describe('the input box', () => {
  test('three modes with their placeholders; Enter sends, Shift+Enter does not', async () => {
    const { w, sock } = await play('view_rich')
    const text = () => field(w, 'input-text')
    expect(text().attributes('placeholder')).toBe('What do you do?')
    await one(w, 'mode-say').trigger('click')
    expect(text().attributes('placeholder')).toBe('What do you say?')
    await one(w, 'mode-ask').trigger('click')
    expect(text().attributes('placeholder')).toBe("Ask the guide anything — it won't cost a turn")
    await one(w, 'mode-do').trigger('click')
    await text().setValue('I force the steel door.')
    await text().trigger('keydown', { key: 'Enter', shiftKey: true })
    expect(sock.sent).toEqual([])
    await text().trigger('keydown', { key: 'Enter' })
    expect(sock.sent).toEqual([{ action: 'turn_submit', mode: 'do', text: 'I force the steel door.', suggestion_ref: null,
      addressee_refs: [] }])
    expect(text().element.value).toBe('')
  })

  test('Ctrl+1/2/3 switch modes; Say goes to the chosen person', async () => {
    const { w, sock } = await play('view_rich')
    const text = () => field(w, 'input-text')
    await text().trigger('keydown', { key: '2', ctrlKey: true })
    expect(text().attributes('placeholder')).toBe('What do you say?')
    const chips = byId(w, 'say-to-chip')
    expect(chips.map((c) => c.text())).toEqual(['Anyone who can hear', 'Tomas', 'a figure'])
    await chips[1].trigger('click')
    await text().setValue('Tomas, the filter.')
    await one(w, 'input-send').trigger('click')
    expect(sock.sent).toEqual([{ action: 'turn_submit', mode: 'say', text: 'Tomas, the filter.', suggestion_ref: null,
      addressee_refs: ['p1'] }])
    await text().trigger('keydown', { key: '3', ctrlKey: true })
    expect(text().attributes('placeholder')).toBe("Ask the guide anything — it won't cost a turn")
    await text().trigger('keydown', { key: '1', ctrlKey: true })
    expect(text().attributes('placeholder')).toBe('What do you do?')
  })

  test("suggestions are the character's own options: a do chip is sent at once, a say chip waits for words", async () => {
    const { w, sock } = await play('view_rich')
    const chips = byId(w, 'suggestion-chip')
    expect(chips.map((c) => c.text())).toEqual(fixture('view_rich').data.view.suggestions.map((s) => s.label))
    await chips[3].trigger('click')
    expect(sock.sent).toEqual([{ action: 'turn_submit', mode: 'do', text: '', suggestion_ref: 's4', addressee_refs: [] }])
    sock.sent.length = 0
    await chips[1].trigger('click')
    expect(sock.sent).toEqual([])
    expect(field(w, 'input-text').attributes('placeholder')).toBe('What do you say?')
    await field(w, 'input-text').setValue('Is the pump holding?')
    await one(w, 'input-send').trigger('click')
    expect(sock.sent).toEqual([{ action: 'turn_submit', mode: 'say', text: 'Is the pump holding?', suggestion_ref: 's2',
      addressee_refs: [] }])
  })

  test('a dead character cannot act', async () => {
    const { store } = storeWith('view_dead_sandbox')
    const w = mountWith(PlayScreen, { store })
    await flush()
    expect(field(w, 'input-text').attributes('disabled')).toBeDefined()
    expect(one(w, 'input-dead').text()).toBe(TEXT.deadInput)
    expect(byId(w, 'suggestion-chip')).toEqual([])
  })
})

describe('the right-hand tabs', () => {
  test('five tabs with plain titles; Your pack first', async () => {
    const { w } = await play('view_rich')
    expect(['tab-pack', 'tab-body', 'tab-people', 'tab-journal', 'tab-map'].map((id) => one(w, id).text())).toEqual(
      [PANEL_TITLES.pack, PANEL_TITLES.body, PANEL_TITLES.people, PANEL_TITLES.journal, PANEL_TITLES.map])
    expect(has(w, 'pack-panel')).toBe(true)
    await one(w, 'tab-body').trigger('click')
    await flush()
    expect(has(w, 'body-panel')).toBe(true)
  })

  test('an item action fills the Do box and sends nothing', async () => {
    const { w, sock, store } = await play('view_rich')
    await byId(w, 'pack-hands-item')[0].trigger('click')
    const actions = byId(w, 'item-action')
    expect(actions.map((a) => a.text())).toEqual(['Drop', 'Put away'])
    await actions[1].trigger('click')
    await flush()
    expect(sock.sent).toEqual([])
    expect(store.composeText).toBe('Put away the crowbar')
    expect(field(w, 'input-text').element.value).toBe('Put away the crowbar')
    expect(field(w, 'input-text').attributes('placeholder')).toBe('What do you do?')
  })
})
