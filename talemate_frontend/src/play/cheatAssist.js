// The Cheat field's autocomplete and dictionary (P12, D-115, CHEAT-20/21; 10_UI §2.6 Input). The owner:
// "There needs to be an auto complete that shows all of the options, and a dictionary on that same menu so I
// don't get confused." `commands` is store.cheatCommands (the server's cheat_dictionary): [{name, usage,
// meaning, example, slots: {slot: [options]}}], in the server's order. Pure: no store, no socket.

// A word that says the next blank is not the command's first one: /give <item> to <person>, /forget <person>
// about <who or where>, /infect <person> with <strain>, /horde <n> at <place>.
export const SLOT_WORDS = ['to', 'about', 'with', 'at']

const TOKEN = /"[^"]*"?|\S+/g

// A command takes nothing when it has no blanks and its usage is the bare command (/help, /census).
export const argless = (c) => Object.keys(c.slots || {}).length === 0 && c.usage === `/${c.name}`

// How an option goes into the line: as it is when it is one word, in quotes when it has a space.
export const quoted = (o) => (/\s/.test(o) && !o.includes('"') ? `"${o}"` : o)

function parts (text) {
  const lead = text.length - text.trimStart().length
  const slash = text.slice(lead).startsWith('/')
  const start = lead + (slash ? 1 : 0)
  return { slash, start, body: text.slice(start) }
}

// The command the line begins with (with or without its '/'), or null.
export function currentCommand (text, commands) {
  const { body } = parts(text || '')
  const m = body.match(/^(\S+)(\s|$)/)
  if (!m) return null
  return commands.find((c) => c.name === m[1].toLowerCase()) || null
}

// What the line could go on with: [{kind: 'command' | 'option', label, insert, slot, hint}] — all of them
// unless `max` says fewer (the list scrolls). `insert` is the whole line once that suggestion is taken.
//  - While the first word is being typed: every command whose name starts with it, in the server's order
//    (an empty line: all of them), each inserting its name (keeping a '/' the Boss typed) and a space when it
//    takes something; hint: what it does.
//  - After a known command: the options of its blanks that start with what is being typed — the longest run of
//    the last words that one starts with ("bandage ro" -> "bandage roll"; a '"' just opened is not counted),
//    each in its blank's order unless the word before says a later blank (SLOT_WORDS), without repeats;
//    inserting replaces that run with the option (quoted when it has a space) and a space.
//  - Anything else (plain words, CHEAT-16): nothing.
export function suggest (text, commands, max = Infinity) {
  text = text || ''
  if (!commands || !commands.length) return []
  const { slash, start, body } = parts(text)
  if (!/\s/.test(body)) {
    const word = body.toLowerCase()
    return commands.filter((c) => c.name.startsWith(word)).slice(0, max).map((c) => ({
      kind: 'command', label: c.name, slot: null, hint: c.meaning,
      insert: text.slice(0, start) + c.name + (argless(c) ? '' : ' '),
    }))
  }
  const cmd = currentCommand(text, commands)
  if (!cmd) return []
  const slots = Object.keys(cmd.slots || {})
  if (!slots.length) return []
  const restAt = start + body.match(/^\S+/)[0].length
  const toks = [...text.slice(restAt).matchAll(TOKEN)].map((m) => ({ t: m[0], at: restAt + m.index }))
  const fresh = /\s$/.test(text)
  const done = fresh ? toks : toks.slice(0, -1)
  const before = done.length ? done[done.length - 1].t.toLowerCase() : null
  const order = before && SLOT_WORDS.includes(before) && slots.length > 1 ? [...slots.slice(1), slots[0]] : slots
  // the runs of last words that might be the start of one option, longest first
  const runs = []
  if (fresh) runs.push({ typed: '', at: text.length })
  else {
    for (let k = 0; k < toks.length; k++) {
      const tail = toks.slice(k)
      if (tail.slice(0, -1).some((x) => x.t.startsWith('"')) || SLOT_WORDS.includes(tail[0].t.toLowerCase()) && tail.length > 1) continue
      runs.push({ typed: text.slice(tail[0].at).replace(/^"/, '').replace(/\s+/g, ' ').toLowerCase(), at: tail[0].at })
    }
  }
  const out = []
  const seen = new Set()
  for (const slot of order) {
    for (const o of cmd.slots[slot]) {
      if (seen.has(o.toLowerCase())) continue
      const run = runs.find((r) => o.toLowerCase().startsWith(r.typed))
      if (!run) continue
      seen.add(o.toLowerCase())
      out.push({ kind: 'option', label: o, slot, hint: null, insert: text.slice(0, run.at) + quoted(o) + ' ' })
      if (out.length >= max) return out
    }
  }
  return out
}

// The dictionary panel's rows: every command whose name, usage or meaning holds `filter` (any case), in the
// server's order, each marked `current` when the line begins with it.
export function dictionaryRows (commands, filter = '', text = '') {
  const f = (filter || '').trim().toLowerCase()
  const cur = currentCommand(text, commands || [])
  return (commands || []).filter((c) => !f || [c.name, c.usage, c.meaning].some((x) => x.toLowerCase().includes(f)))
    .map((c) => ({ name: c.name, usage: c.usage, meaning: c.meaning, example: c.example, current: cur === c }))
}
