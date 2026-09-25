<template>
  <div data-testid="doom-overlay" class="doom-overlay" @click="next">
    <p v-for="(b, i) in shown" :key="i" data-testid="doom-beat" :data-kind="b.kind" :class="['doom-beat', 'doom-' + b.kind]">
      <span v-if="b.kind === 'willis'" class="doom-speaker">{{ TEXT.death.willis }}: </span>{{ b.text }}
    </p>
    <button type="button" data-testid="doom-next" class="doom-next" @click.stop="next">{{ TEXT.doom.next }}</button>
  </div>
</template>

<script setup>
// P12, D-106: the frozen moment when the PC's death becomes certain. The beats come from the server
// (service/voice.py VOICE-01); the story keeps them too. The Voice has no name on any screen.
import { computed, inject, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { beatDelay } from '../doom.js'
import { TEXT } from '../words.js'

const store = inject('playStore')
const beats = computed(() => store.doom?.beats || [])
const count = ref(0)
const shown = computed(() => beats.value.slice(0, count.value))
let timer = null

function schedule () {
  clearTimeout(timer)
  timer = null
  while (count.value < beats.value.length) {
    const i = count.value
    const ms = beatDelay(beats.value[i - 1], beats.value[i])
    if (ms > 0) {
      timer = setTimeout(() => { count.value = i + 1; schedule() }, ms)
      return
    }
    count.value = i + 1
  }
}

function next () {
  if (count.value < beats.value.length) {
    count.value += 1
    schedule()
  } else {
    store.dismissDoom()
  }
}

watch(() => store.doom, () => { count.value = 0; schedule() })
onMounted(schedule)
onBeforeUnmount(() => clearTimeout(timer))
</script>

<style scoped>
.doom-overlay {
  position: fixed; inset: 0; z-index: 2000; overflow-y: auto; padding: 10vh 12vw;
  background: radial-gradient(ellipse at center, #0b0b0d 0%, #000 70%); color: #b9b6ae; cursor: pointer;
}
.doom-beat { max-width: 44rem; margin: 0 auto 1.2em; line-height: 1.6; }
.doom-willis { color: #d8c9a3; }
.doom-speaker { font-weight: 600; }
.doom-snatch { color: #fff; font-weight: 600; }
.doom-voice { color: #efe9dc; font-size: 1.15em; font-family: Georgia, 'Times New Roman', serif; }
.doom-next { display: block; margin: 2em auto 0; color: #777; background: none; border: 1px solid #333; padding: 0.4em 1.4em; }
</style>
