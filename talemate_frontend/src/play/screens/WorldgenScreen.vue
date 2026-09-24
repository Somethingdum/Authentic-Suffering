<template>
  <div data-testid="worldgen-screen">
    <LoadingBar :kinds="['worldgen']" />
    <p data-testid="worldgen-label">{{ wg?.label }}</p>
    <span data-testid="worldgen-progress">{{ Math.round(wg?.pct ?? 0) }}%</span>
    <span v-if="wg && wg.eta_s != null" data-testid="worldgen-eta">{{ TEXT.barEta(wg.eta_s) }}</span>
    <button type="button" data-testid="worldgen-cancel" @click="store.cancelWorldgen()">{{ TEXT.worldgenCancel }}</button>
  </div>
</template>

<script setup>
import { computed, inject } from 'vue'
import LoadingBar from '../components/LoadingBar.vue'
import { TEXT } from '../words.js'

const store = inject('playStore')
const wg = computed(() => store.worldgen)
</script>
