<!-- Partial: only what the P10 specs touch. P8 builds the rest (docs/as/10_UI.md and the __tests__ specs). -->
<template>
  <div data-testid="play-screen">
    <div v-if="store.progress" data-testid="turn-progress">
      <span data-testid="turn-progress-label">{{ store.progress.label }}</span>
    </div>
    <LoadingBar :kinds="['turn', 'quiet_hours']" />
  </div>
</template>
<script setup>
import { inject } from 'vue'
import LoadingBar from '../components/LoadingBar.vue'
const store = inject('playStore')
</script>
