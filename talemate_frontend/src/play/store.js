// Play UI store. P10 parts are complete; of P8 only what the P10 screens use exists — P8 builds the rest (10_UI.md §4, the __tests__ specs).
import { reactive } from 'vue'
import { TEXT } from './words.js'

export const CLIENT_VERSION = '0.1.0'

export const HOUSE_RULES = {
  save_mode: 'free', turn_depth: 'balanced', narration_length: 'medium', intensity: 'full', show_mechanics: 'summary',
  narration_person: 'third_limited', narration_tense: 'past', pc_voice: 'exact', read_aloud: false, autosave_ring: 5,
}

export function freshDraft() {
  return { step: 1, pcRef: null, difficulty: 'normal', era: null, detail: 'standard', days: '', seed: '',
    rules: { ...HOUSE_RULES }, more: false }
}

const CLIENT_ONLY = ['content', 'worlds', 'wizard']

export function createPlayStore(socket, { download } = {}) {
  const s = reactive({
    screen: 'connect', connected: false, busy: false, serverVersion: null, modelsOk: false, hasRuns: false, runId: null,
    lanes: null, models: {}, laneTests: {}, config: null, runs: [], pcs: [], packs: [], contentReport: null, view: null,
    story: [], progress: null, rejection: null, settings: null, changeable: [], ironman: false, sandbox: false,
    notices: [], death: null, worldgen: null, worlds: [], devData: {}, cheatShimmer: false, error: null, saved: null,
    composeText: '', mode: 'do', settingsOpen: false, bar: null, wizard: freshDraft(),
  })
  const send = (action, fields = {}) => socket.send({ action, ...fields })
  const on = (action, fn) => socket.on(action, (data) => fn(data || {}))

  s.hello = () => send('hello', { client_version: CLIENT_VERSION })
  s.getState = () => send('get_state')
  s.go = (screen) => { s.screen = screen }
  s.openSettings = () => { s.settingsOpen = true }
  s.closeSettings = () => { s.settingsOpen = false }
  s.clearError = () => { s.error = null }
  s.listPcs = () => send('pcs_list')
  s.newLife = (pcRef, settings, worldId = null) => {
    send('run_new', worldId ? { pc_ref: pcRef, settings, world_id: worldId } : { pc_ref: pcRef, settings })
    s.screen = 'worldgen'
  }
  s.cancelWorldgen = () => send('worldgen_cancel')
  s.closeRun = () => send('run_close')

  socket.onStatus((st) => {
    s.connected = st === 'open'
    if (st === 'open') s.hello()
    if (st === 'other_tab') { s.error = { code: 'other_tab', message: TEXT.otherTab }; s.screen = 'connect' }
  })
  if (socket.status === 'open') { s.connected = true; s.hello() }

  on('welcome', (d) => {
    s.serverVersion = d.server_version; s.modelsOk = d.models_ok; s.hasRuns = d.has_runs; s.screen = d.screen; s.bar = null
  })
  on('state', (d) => {
    if (!(d.screen === 'home' && CLIENT_ONLY.includes(s.screen))) s.screen = d.screen
    s.runId = d.run_id; s.busy = d.busy
    if (!d.busy) s.progress = null
  })
  on('run_loaded', (d) => {
    s.runId = d.run_id; s.ironman = d.ironman; s.sandbox = d.sandbox; s.settings = d.settings; s.notices = d.notices
    s.screen = 'play'; s.story = []; s.rejection = null; s.death = null; s.progress = null; s.wizard = freshDraft()
    send('settings_get')
  })
  on('view', (d) => { s.view = d.view; s.lanes = d.view?.lanes ?? s.lanes })
  on('story', (d) => { s.story = d.entries })
  on('pcs', (d) => { s.pcs = d.cards })
  on('turn_progress', (d) => {
    s.busy = true
    s.progress = { turnIndex: d.turn_index, stage: d.stage, label: d.label, pct: d.pct, elapsed: d.elapsed_s }
  })
  on('worldgen_progress', (d) => { s.worldgen = d; s.screen = 'worldgen' })
  on('error', (d) => { s.error = { code: d.code, message: d.message } })
  on('progress_plan', (d) => {
    s.bar = { jobId: d.job_id, kind: d.kind, title: d.title, phases: d.phases, quips: d.quips || {}, phase: null,
      phaseIndex: -1, sub: null, subLabel: null, done: null, total: null, pct: 0, elapsed: 0, eta: null, detail: null }
  })
  on('progress', (d) => {
    if (!s.bar || s.bar.jobId !== d.job_id) return
    Object.assign(s.bar, { phase: d.phase, phaseIndex: d.phase_index, sub: d.sub, subLabel: d.sub_label, done: d.done,
      total: d.total, pct: d.pct, elapsed: d.elapsed_s, eta: d.eta_s, detail: d.detail })
  })
  on('progress_done', (d) => { if (s.bar && s.bar.jobId === d.job_id) s.bar = null })
  void download
  return s
}
