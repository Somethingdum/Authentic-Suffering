<template>
  <div data-testid="later-screen">{{ TEXT.notBuilt }}
    <button type="button" data-testid="later-back" @click="store.go('home')">{{ TEXT.back }}</button>
  </div>
</template>
<script setup>
import { inject } from 'vue'
import { TEXT } from '../words.js'
const store = inject('playStore')
</script>
