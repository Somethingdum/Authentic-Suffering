<!-- Partial: only what the P10 specs touch. P8 builds the rest (docs/as/10_UI.md and the __tests__ specs). -->
<template>
  <div data-testid="connect-screen">Connect
    <p v-if="store.error && store.error.code === 'other_tab'" data-testid="other-tab-notice">{{ store.error.message }}</p>
  </div>
</template>
<script setup>
import { inject } from 'vue'
const store = inject('playStore')
</script>
