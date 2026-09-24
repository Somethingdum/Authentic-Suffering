// Your lives: every session ever played, and one easy delete that leaves nothing (10_UI §2.2.1, §4;
// RUN-12). PROTECTED.
import { describe, expect, test } from 'vitest'
import SessionsScreen from '../screens/SessionsScreen.vue'
import { byId, fixture, flush, has, mountWith, one, storeWith } from './helpers.js'

describe('Your lives', () => {
  test('asks for the list and shows every life as a card, ended ones too', async () => {
    const { store, sock } = storeWith('welcome_home')
    sock.sent.length = 0
    const w = mountWith(SessionsScreen, { store })
    await flush()
    expect(sock.sent).toEqual([{ action: 'runs_list' }])
    sock.emit(fixture('runs'))
    await flush()
    const cards = byId(w, 'run-card')
    expect(cards.length).toBe(2)
    for (const word of ['Owen Marsh', 'day 18', 'alive', 'Normal', '2026-09-22 21:14']) {
      expect(cards[0].text()).toContain(word)
    }
    for (const word of ['Addison Flores', 'day 212', 'dead', 'Realism', 'Sandbox', 'Ironman', 'ended', '2026-09-20 19:02']) {
      expect(cards[1].text()).toContain(word)
    }
    expect(cards[0].text()).not.toContain('Sandbox')
    expect(cards[0].text()).not.toContain('ended')
  })

  test('an ended life can be deleted, not played on', async () => {
    const { store, sock } = storeWith('welcome_home', 'runs')
    const w = mountWith(SessionsScreen, { store })
    await flush()
    const cards = byId(w, 'run-card')
    expect(cards[1].find('[data-testid="run-card-load"]').exists()).toBe(false)
    expect(cards[1].find('[data-testid="run-card-delete"]').exists()).toBe(true)
    sock.sent.length = 0
    await cards[0].get('[data-testid="run-card-load"]').trigger('click')
    expect(sock.sent).toEqual([{ action: 'run_load', run_id: 'owen_marsh_71a', save_slot: null }])
  })

  test('delete asks once, in plain words; Keep it changes nothing', async () => {
    const { store, sock } = storeWith('welcome_home', 'runs')
    const w = mountWith(SessionsScreen, { store })
    await flush()
    sock.sent.length = 0
    expect(has(w, 'run-card-delete-question')).toBe(false)
    await byId(w, 'run-card')[0].get('[data-testid="run-card-delete"]').trigger('click')
    expect(sock.sent).toEqual([])
    const card = byId(w, 'run-card')[0]
    expect(card.get('[data-testid="run-card-delete-question"]').text()).toBe("Delete Owen Marsh's story? This can't be undone.")
    expect(card.get('[data-testid="run-card-delete-confirm"]').text()).toContain('Delete')
    expect(card.get('[data-testid="run-card-delete-cancel"]').text()).toContain('Keep it')
    await card.get('[data-testid="run-card-delete-cancel"]').trigger('click')
    expect(has(w, 'run-card-delete-question')).toBe(false)
    expect(sock.sent).toEqual([])
    await byId(w, 'run-card')[0].get('[data-testid="run-card-delete"]').trigger('click')
    await byId(w, 'run-card')[0].get('[data-testid="run-card-delete-confirm"]').trigger('click')
    expect(sock.sent).toEqual([{ action: 'run_delete', run_id: 'owen_marsh_71a' }])
  })

  test('a deleted life leaves the list at once, and the client keeps nothing of it', async () => {
    const { store, sock } = storeWith('welcome_home', 'runs', 'run_loaded', 'view_anchor', 'story_anchor')
    expect(store.runId).toBe('addison_flores_5c2')
    store.compose('I check the back door.')
    store.go('sessions')
    const w = mountWith(SessionsScreen, { store })
    await flush()
    sock.emit({ type: 'as_game', action: 'run_deleted', data: { run_id: 'addison_flores_5c2' } })
    await flush()
    const cards = byId(w, 'run-card')
    expect(cards.length).toBe(1)
    expect(cards[0].text()).toContain('Owen Marsh')
    expect(store.runId).toBe(null)
    expect(store.view).toBe(null)
    expect(store.story).toEqual([])
    expect(store.composeText).toBe('')
  })

  test('no lives yet', async () => {
    const { store, sock } = storeWith('welcome_home')
    sock.emit({ type: 'as_game', action: 'runs', data: { runs: [] } })
    const w = mountWith(SessionsScreen, { store })
    await flush()
    expect(has(w, 'run-card')).toBe(false)
    expect(one(w, 'sessions-empty').text()).toContain('New life')
  })

  test('the list is a place of its own; Back returns home', async () => {
    const { store, sock } = storeWith('welcome_home', 'runs')
    store.go('sessions')
    sock.emit({ type: 'as_game', action: 'state', data: { screen: 'home', run_id: null, busy: false } })
    expect(store.screen).toBe('sessions')
    const w = mountWith(SessionsScreen, { store })
    await one(w, 'sessions-back').trigger('click')
    expect(store.screen).toBe('home')
  })
})
