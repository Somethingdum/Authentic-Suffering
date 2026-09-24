<template>
  <section v-if="bar && kinds.includes(bar.kind)" data-testid="loading-bar" class="loading-bar">
    <h3 data-testid="bar-title">{{ bar.title }}</h3>
    <ol class="bar-phases">
      <li v-for="(p, i) in bar.phases" :key="p.id" data-testid="bar-phase" :data-phase="p.id" :data-state="stateOf(i)"
          :aria-current="i === bar.phaseIndex ? 'step' : undefined">{{ p.label }}</li>
    </ol>
    <p v-if="bar.phaseIndex >= 0" data-testid="bar-step">{{ stepLabel }}</p>
    <div data-testid="bar-fill" role="progressbar" aria-valuemin="0" aria-valuemax="100"
         :aria-valuenow="String(Math.round(bar.pct))" :aria-label="TEXT.barProgress">
      <div class="bar-fill-inner" :style="{ width: `${bar.pct}%` }"></div>
    </div>
    <span data-testid="bar-pct">{{ Math.round(bar.pct) }}%</span>
    <span v-if="bar.done != null && bar.total != null" data-testid="bar-count">{{ TEXT.barCount(bar.done, bar.total) }}</span>
    <span data-testid="bar-elapsed">{{ TEXT.barElapsed(bar.elapsed) }}</span>
    <span v-if="bar.eta != null" data-testid="bar-eta">{{ TEXT.barEta(bar.eta) }}</span>
    <p v-if="quip" data-testid="bar-quip" class="bar-quip">{{ quip }}</p>
    <p v-if="bar.detail" data-testid="bar-detail">{{ bar.detail }}</p>
  </section>
</template>

<script setup>
import { computed, inject, onBeforeUnmount, ref, watch } from 'vue'
import { QUIP_MS, nextQuip, quipLines } from '../quips.js'
import { TEXT } from '../words.js'

const props = defineProps({
  kinds: { type: Array, default: () => ['worldgen', 'turn', 'quiet_hours'] },
  random: { type: Function, default: () => Math.random() },
})
const store = inject('playStore')
const bar = computed(() => store.bar)
const quip = ref(null)
let recent = []
let timer = null
let job = null

const stepLabel = computed(() => {
  const b = store.bar
  if (!b || b.phaseIndex < 0) return ''
  return b.subLabel || b.phases[b.phaseIndex]?.label || ''
})

function stateOf(i) {
  const at = store.bar.phaseIndex
  if (at < 0) return 'todo'
  return i < at ? 'done' : i === at ? 'current' : 'todo'
}

function lines() {
  const b = store.bar
  return b && b.phaseIndex >= 0 ? quipLines(b.quips, b.kind, b.phase, b.sub) : []
}

function show() {
  const q = nextQuip(lines(), recent, props.random)
  quip.value = q
  if (q != null) recent.push(q)
}

function stop() {
  if (timer) clearInterval(timer)
  timer = null
}

watch(() => (store.bar ? [store.bar.jobId, store.bar.phase, store.bar.sub] : null), (key) => {
  stop()
  if (!key) {
    quip.value = null
    recent = []
    job = null
    return
  }
  if (key[0] !== job) {
    job = key[0]
    recent = []
  }
  if (lines().length) {
    show()
    timer = setInterval(show, QUIP_MS)
  } else {
    quip.value = null
  }
}, { immediate: true })

onBeforeUnmount(stop)
</script>
