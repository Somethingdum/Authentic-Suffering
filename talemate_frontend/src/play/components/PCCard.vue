<template>
  <button type="button" data-testid="pc-card" class="pc-card" :aria-pressed="selected ? 'true' : 'false'"
          @click="$emit('select', card.ref)">
    <span class="pc-card-head"><span data-testid="pc-card-name" class="pc-card-name">{{ card.display_name }}</span> —
      <span data-testid="pc-card-identity">{{ card.one_line_identity }}</span></span>
    <span data-testid="pc-card-survives" class="pc-card-row">{{ TEXT.survivesBy }} {{ card.survives_by }}</span>
    <span data-testid="pc-card-starts" class="pc-card-row">{{ TEXT.startsAs }} {{ card.starts_as }}</span>
    <span data-testid="pc-card-note" class="pc-card-row">{{ TEXT.note }} {{ card.note }}</span>
    <span v-if="card.world_age_note" data-testid="pc-card-age" class="pc-card-row">{{ card.world_age_note }}</span>
  </button>
</template>

<script setup>
import { TEXT } from '../words.js'

defineProps({ card: { type: Object, required: true }, selected: { type: Boolean, default: false } })
defineEmits(['select'])
</script>
