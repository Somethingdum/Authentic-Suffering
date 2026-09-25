<template>
  <div class="play-app">
    <component :is="current" />
    <div v-if="store.error && store.error.code !== 'other_tab'" data-testid="error-toast">
      {{ store.error.message }}
      <button type="button" data-testid="error-dismiss" @click="store.clearError()">{{ TEXT.dismiss }}</button>
    </div>
    <SettingsDialog v-if="store.settingsOpen" />
  </div>
</template>

<script setup>
import { computed, provide } from 'vue'
import SettingsDialog from './components/SettingsDialog.vue'
import ConnectScreen from './screens/ConnectScreen.vue'
import ContentScreen from './screens/ContentScreen.vue'
import DeathScreen from './screens/DeathScreen.vue'
import HomeScreen from './screens/HomeScreen.vue'
import LaterScreen from './screens/LaterScreen.vue'
import PlayScreen from './screens/PlayScreen.vue'
import WizardScreen from './screens/WizardScreen.vue'
import WorldgenScreen from './screens/WorldgenScreen.vue'
import { TEXT } from './words.js'

const props = defineProps({ store: { type: Object, required: true } })
const store = props.store
provide('playStore', store)
const SCREENS = { connect: ConnectScreen, home: HomeScreen, content: ContentScreen, play: PlayScreen,
  wizard: WizardScreen, worldgen: WorldgenScreen, dead: DeathScreen }
const current = computed(() => SCREENS[store.screen] || LaterScreen)
</script>
