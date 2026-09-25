// Play UI words. P10 parts are complete; of P8 only a subset exists — P8 completes it (10_UI.md §5, words.spec.js).
export const BANNED_WORDS = ['packet', 'affordance', 'percept', 'LOD', 'claim', 'intent', 'handle', 'lane',
  'schema', 'token', 'stage', 'event', 'actor', 'dossier']
export const ID_PATTERN = /\b(act|plc|anc|prt|itm|evt|clm|prp|pct)_\d{6}\b/
export const PANEL_TITLES = { where: 'Where you are', pack: 'Your pack', body: 'Your body', people: 'People',
  journal: 'Journal', map: 'Map' }

export const DIFFICULTY_TEXT = { bitch_mode: 'Bitch Mode', easy: 'Easy', normal: 'Normal', realism: 'Realism',
  actually_hell: 'Actually Hell', fuck_you: 'Fuck You' }
export const DIFFICULTY_HELP = {
  bitch_mode: 'The world is almost livable. Threats exist but rarely compound. For learning the system or narrative-first play.',
  easy: 'Real danger, real consequences. Mistakes cost something. You have breathing room.',
  normal: 'Survivable with consistent good decisions. Comfort is earned. Setbacks require active recovery.',
  realism: 'The world will not forgive much. Every decision carries weight. Intended experience. Losses cascade.',
  actually_hell: 'No mercy. Losses compound fast. You will die from things Normal makes manageable.',
  fuck_you: 'Slaughter mode. Not balanced. Not fair. Not intended for narrative play.',
}
export const ERA_TEXT = {
  early: { label: 'Early', help: 'Weeks to about a year after the Fall. Everything is still falling apart.', days: [14, 330] },
  established: { label: 'Established', help: 'One to four years on. The survivors have sorted themselves into groups.', days: [400, 1460] },
  mature: { label: 'Mature', help: 'Five years and more. Children born after the Fall are growing up.', days: [1830, 3650] },
}
export const DETAIL_TEXT = {
  gotta_go_to_work_soon: { label: 'Gotta go to work soon', minutes: 3 },
  quick_look: { label: 'Quick look', minutes: 7 },
  standard: { label: 'Standard', minutes: 15 },
  settle_in: { label: 'Settle in', minutes: 30 },
  not_using_my_laptop_today: { label: "I don't intend to use my laptop much today", minutes: 60 },
}

export const SETTINGS_TEXT = {
  save_mode: { label: 'Save mode', help: 'Free lets you save and load. Ironman keeps one life: only autosave, and death ends it.',
    choices: { free: 'Free', ironman: 'Ironman' } },
  turn_depth: { label: 'Turn depth', help: 'How many people think it through with full care each turn.',
    choices: { quick: 'Quick', balanced: 'Balanced', deep: 'Deep' } },
  narration_length: { label: 'Scene length', help: 'How long each piece of the story is.',
    choices: { short: 'Short', medium: 'Medium', long: 'Long' } },
  narration_person: { label: 'Point of view', help: 'Whether the story calls you by name or says you.',
    choices: { third_limited: 'Third person', second: 'Second person' } },
  narration_tense: { label: 'Tense', help: 'Whether the story is told as it happens or after.',
    choices: { past: 'Past', present: 'Present' } },
  pc_voice: { label: 'Say it my way', help: 'Off: your words are spoken exactly. On: your character says it their way.',
    choices: { exact: 'Off', my_way: 'On' } },
  intensity: { label: 'Intensity', help: 'Softer describes gore with less detail. Everything still happens.',
    choices: { full: 'Full', softer: 'Softer' } },
  show_mechanics: { label: 'Show dice', help: 'A small receipt under the scene with how a check went.',
    choices: { off: 'Off', summary: 'Summary', full: 'Full' } },
  read_aloud: { label: 'Read aloud', help: 'The story is read out by the voice you set up.',
    choices: { false: 'Off', true: 'On' } },
  dev_mode: { label: 'Developer mode', help: 'Shows what the game did behind the scenes. It changes nothing.',
    choices: { false: 'Off', true: 'On' } },
  autosave_ring: { label: 'Autosave slots', help: 'How many autosaves are kept, newest first.' },
  wild_card: { label: 'Wild Card', help: 'A grinning man in a tuxedo walks this world as a person of his own. Chosen now; it cannot change later.',
    choices: { false: 'Off', true: 'On' } },
}

const time = (s, tail) => (s < 60 ? `${Math.round(s)} s${tail}` : `${Math.round(s / 60)} min${tail}`)

export const TEXT = {
  notBuilt: 'That part of the game is not built yet. It arrives in a later build.',
  back: 'Back',
  otherTab: 'The game is already open in another tab or window. Close that one, then reload this page.',
  dismiss: 'Dismiss',
  wizardSteps: ['Who are you?', 'What kind of world?', 'House rules', 'Build the world'],
  wizardBack: 'Back', wizardNext: 'Next', wizardStart: 'Build the world',
  survivesBy: 'Survives by', startsAs: 'Starts as', note: 'Note',
  difficulty: 'Difficulty', era: 'Era', detail: 'World detail', days: 'Days since the Fall', seed: 'Seed',
  moreOptions: 'More options',
  codeLabel: 'Enter a code',
  codeEnter: 'Enter',
  codeAccepted: 'Accepted.',
  codeRejected: 'Nothing happens.',
  buildTime: (m) => `About ${m} minutes to build`,
  daysHint: (lo, hi) => `Leave it empty, or pick a day from ${lo} to ${hi}.`,
  daysRange: (lo, hi) => `That world has to be ${lo} to ${hi} days after the Fall.`,
  seedHelp: 'A seed is a whole number, 0 or more. Leave it empty for a random world.',
  summary: { who: 'You are', difficulty: 'Difficulty', era: 'Era', detail: 'World detail', days: 'Days since the Fall',
    seed: 'Seed', save: 'Saving' },
  worldgenCancel: 'Stop building',
  barProgress: 'How far along',
  barCount: (done, total) => `${done} of ${total}`,
  barElapsed: (s) => time(s, ' so far'),
  barEta: (s) => `About ${time(s, ' left')}`,
  // P12 (D-105): the death screen, and Willis at every death
  death: {
    title: (name) => `${name} is dead.`,
    when: (day, time) => `Day ${day}, ${time}`,
    willis: 'Willis',
    willisArriving: 'Somebody is laughing.',
    lastMoments: 'The last moments',
    choices: 'What led here',
    reveal: 'Show me everything',
    revealWarning: 'This shows what really happened: who was where, who chose what, and what you never saw. '
      + 'It can spoil this world if you live in it again.',
    revealConfirm: 'Show me',
    revealCancel: 'Not yet',
    ironman: 'This life is over. The world is still out there.',
    load: 'Load a save',
    newWorld: 'A new life in a new world',
  },
}
