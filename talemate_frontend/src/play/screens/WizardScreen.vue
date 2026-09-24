<template>
  <div data-testid="wizard-screen" class="wizard">
    <ol class="wizard-steps">
      <li v-for="(title, i) in TEXT.wizardSteps" :key="i" :data-testid="`wizard-step-${i + 1}`"
          :data-state="i + 1 < d.step ? 'done' : i + 1 === d.step ? 'current' : 'todo'">{{ title }}</li>
    </ol>

    <section v-if="d.step === 1">
      <PCCard v-for="c in cards" :key="c.ref" :card="c" :selected="c.ref === d.pcRef" @select="(ref) => (d.pcRef = ref)" />
    </section>

    <section v-else-if="d.step === 2">
      <h3>{{ TEXT.difficulty }}</h3>
      <button v-for="t in TIERS" :key="t" type="button" :data-testid="`difficulty-option-${t}`"
              :aria-pressed="d.difficulty === t ? 'true' : 'false'" @click="d.difficulty = t">
        <strong>{{ DIFFICULTY_TEXT[t] }}</strong> {{ DIFFICULTY_HELP[t] }}
      </button>
      <h3>{{ TEXT.era }}</h3>
      <div v-for="e in ERAS" :key="e">
        <button type="button" :data-testid="`era-option-${e}`" :disabled="!fits(e)"
                :aria-pressed="d.era === e ? 'true' : 'false'" @click="d.era = e">
          <strong>{{ ERA_TEXT[e].label }}</strong> {{ ERA_TEXT[e].help }}
        </button>
        <span v-if="!fits(e)" :data-testid="`era-reason-${e}`">{{ chosen?.world_age_note }}</span>
      </div>
      <h3>{{ TEXT.detail }}</h3>
      <button v-for="x in DETAILS" :key="x" type="button" :data-testid="`detail-option-${x}`"
              :aria-pressed="d.detail === x ? 'true' : 'false'" @click="d.detail = x">
        <strong>{{ DETAIL_TEXT[x].label }}</strong> {{ TEXT.buildTime(DETAIL_TEXT[x].minutes) }}
      </button>
      <label>{{ TEXT.days }} <input v-model="d.days" data-testid="days-input" type="text" inputmode="numeric"
                                    :aria-label="TEXT.days"></label>
      <span data-testid="days-hint">{{ TEXT.daysHint(range[0], range[1]) }}</span>
      <span v-if="daysError" data-testid="days-error">{{ TEXT.daysRange(range[0], range[1]) }}</span>
      <label>{{ TEXT.seed }} <input v-model="d.seed" data-testid="seed-input" type="text" inputmode="numeric"
                                    :aria-label="TEXT.seed"></label>
      <span v-if="seedError" data-testid="seed-error">{{ TEXT.seedHelp }}</span>
    </section>

    <section v-else-if="d.step === 3" data-testid="house-rules">
      <div v-for="f in rows" :key="f" data-testid="wizard-setting" :data-field="f">
        <strong>{{ SETTINGS_TEXT[f].label }}</strong> <span>{{ SETTINGS_TEXT[f].help }}</span>
        <template v-if="f === 'autosave_ring'">
          <input v-model.number="d.rules.autosave_ring" data-testid="wizard-setting-autosave_ring" type="number" min="1"
                 max="50" :aria-label="SETTINGS_TEXT.autosave_ring.label">
        </template>
        <template v-else>
          <button v-for="(words, v) in SETTINGS_TEXT[f].choices" :key="v" type="button"
                  :data-testid="`wizard-setting-${f}-${v}`" :aria-pressed="String(d.rules[f]) === v ? 'true' : 'false'"
                  @click="pick(f, v)">{{ words }}</button>
        </template>
      </div>
      <button v-if="!d.more" type="button" data-testid="more-options-toggle" @click="d.more = true">{{ TEXT.moreOptions }}</button>
    </section>

    <section v-else data-testid="wizard-summary">
      <p>{{ TEXT.summary.who }}: {{ chosen?.display_name }}</p>
      <p>{{ TEXT.summary.difficulty }}: {{ DIFFICULTY_TEXT[d.difficulty] }}</p>
      <p>{{ TEXT.summary.era }}: {{ ERA_TEXT[d.era]?.label }}</p>
      <p>{{ TEXT.summary.detail }}: {{ DETAIL_TEXT[d.detail].label }}</p>
      <p v-if="String(d.days).trim() !== ''">{{ TEXT.summary.days }}: {{ String(d.days).trim() }}</p>
      <p v-if="String(d.seed).trim() !== ''">{{ TEXT.summary.seed }}: {{ String(d.seed).trim() }}</p>
      <p>{{ TEXT.summary.save }}: {{ SETTINGS_TEXT.save_mode.choices[d.rules.save_mode] }}</p>
    </section>

    <nav>
      <button type="button" data-testid="wizard-back" @click="back">{{ TEXT.wizardBack }}</button>
      <button v-if="d.step < 4" type="button" data-testid="wizard-next" :disabled="!canNext" @click="next">{{ TEXT.wizardNext }}</button>
      <button v-else type="button" data-testid="wizard-start" @click="start">{{ TEXT.wizardStart }}</button>
    </nav>
  </div>
</template>

<script setup>
import { computed, inject, onMounted } from 'vue'
import PCCard from '../components/PCCard.vue'
import { DETAIL_TEXT, DIFFICULTY_HELP, DIFFICULTY_TEXT, ERA_TEXT, SETTINGS_TEXT, TEXT } from '../words.js'

const TIERS = ['bitch_mode', 'easy', 'normal', 'realism', 'actually_hell', 'fuck_you']
const ERAS = ['early', 'established', 'mature']
const DETAILS = ['gotta_go_to_work_soon', 'quick_look', 'standard', 'settle_in', 'not_using_my_laptop_today']
const COMMON = ['save_mode', 'turn_depth', 'narration_length', 'intensity', 'show_mechanics']
const MORE = ['narration_person', 'narration_tense', 'pc_voice', 'read_aloud', 'autosave_ring']

const store = inject('playStore')
const d = store.wizard
const cards = computed(() => store.pcs || [])
const chosen = computed(() => cards.value.find((c) => c.ref === d.pcRef) || null)
const rows = computed(() => (d.more ? [...COMMON, ...MORE] : COMMON))

onMounted(() => { if (!store.pcs || !store.pcs.length) store.listPcs() })

function fits(era, c = chosen.value) {
  if (!c || !c.world_age_days) return true
  const [lo, hi] = ERA_TEXT[era].days
  return Math.max(lo, c.world_age_days[0]) <= Math.min(hi, c.world_age_days[1])
}

function ensureEra() {
  if (!d.era || !fits(d.era)) d.era = fits('mature') ? 'mature' : (ERAS.find((e) => fits(e)) || 'mature')
}

const range = computed(() => {
  const [lo, hi] = ERA_TEXT[d.era || 'mature'].days
  const c = chosen.value
  if (!c || !c.world_age_days) return [lo, hi]
  return [Math.max(lo, c.world_age_days[0]), Math.min(hi, c.world_age_days[1])]
})
const daysError = computed(() => {
  const v = String(d.days).trim()
  if (v === '') return false
  if (!/^\d+$/.test(v)) return true
  const n = Number(v)
  return n < range.value[0] || n > range.value[1]
})
const seedError = computed(() => {
  const v = String(d.seed).trim()
  return v !== '' && !/^\d+$/.test(v)
})
const canNext = computed(() => (d.step === 1 ? !!d.pcRef : d.step === 2 ? !!d.era && !daysError.value && !seedError.value : true))

function pick(field, v) {
  d.rules[field] = v === 'true' ? true : v === 'false' ? false : v
}

function next() {
  if (!canNext.value) return
  d.step += 1
  if (d.step === 2) ensureEra()
}

function back() {
  if (d.step === 1) store.go('home')
  else d.step -= 1
}

function start() {
  const settings = { difficulty: d.difficulty, era: d.era, world_detail: d.detail, ...d.rules }
  if (String(d.days).trim() !== '') settings.days_since_fall = Number(String(d.days).trim())
  if (String(d.seed).trim() !== '') settings.seed = Number(String(d.seed).trim())
  store.newLife(d.pcRef, settings)
}
</script>
