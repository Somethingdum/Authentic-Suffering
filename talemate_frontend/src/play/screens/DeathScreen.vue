<template>
  <div data-testid="death-screen" class="death-screen">
    <template v-if="d">
      <h1 data-testid="death-title">{{ TEXT.death.title(d.pc_name) }}</h1>
      <p data-testid="death-when">{{ TEXT.death.when(d.day, d.time_text) }}</p>
      <p data-testid="death-cause">{{ d.cause_text }}</p>

      <section data-testid="death-willis" class="willis">
        <h2>{{ TEXT.death.willis }}</h2>
        <p v-if="d.willis_pending" data-testid="death-willis-pending">{{ TEXT.death.willisArriving }}</p>
        <p v-for="(line, i) in d.willis" :key="'w' + i" data-testid="death-willis-line">{{ line }}</p>
      </section>

      <section v-if="d.last_turns.length">
        <h2>{{ TEXT.death.lastMoments }}</h2>
        <p v-for="(t, i) in d.last_turns" :key="'t' + i" data-testid="death-last-turns">{{ t }}</p>
      </section>

      <section v-if="d.contributing.length">
        <h2>{{ TEXT.death.choices }}</h2>
        <ul>
          <li v-for="(c, i) in d.contributing" :key="'c' + i" data-testid="death-contributing">{{ c }}</li>
        </ul>
      </section>

      <section>
        <button v-if="!d.truth_reveal.length && !warning" type="button" data-testid="death-reveal-button"
                @click="warning = true">{{ TEXT.death.reveal }}</button>
        <div v-if="warning && !d.truth_reveal.length" data-testid="death-reveal-warning">
          <p>{{ TEXT.death.revealWarning }}</p>
          <button type="button" data-testid="death-reveal-confirm" @click="reveal">{{ TEXT.death.revealConfirm }}</button>
          <button type="button" data-testid="death-reveal-cancel" @click="warning = false">{{ TEXT.death.revealCancel }}</button>
        </div>
        <ul v-if="d.truth_reveal.length" data-testid="death-reveal">
          <li v-for="(r, i) in d.truth_reveal" :key="'r' + i" data-testid="death-reveal-line">{{ r }}</li>
        </ul>
      </section>

      <p v-if="!d.can_load" data-testid="death-ironman">{{ TEXT.death.ironman }}</p>
      <button v-if="d.can_load" type="button" data-testid="death-load" @click="store.go('home')">{{ TEXT.death.load }}</button>
      <button type="button" data-testid="death-new-world" @click="store.go('wizard')">{{ TEXT.death.newWorld }}</button>
    </template>
  </div>
</template>

<script setup>
import { computed, inject, ref } from 'vue'
import { TEXT } from '../words.js'

const store = inject('playStore')
const d = computed(() => store.death)
const warning = ref(false)

function reveal () {
  warning.value = false
  store.revealDeath()
}
</script>
