---
schema: as.lore.v1
id: shamblers
title: Shamblers
kind: infected
truth: The common dead are effectively blind and hear too well — they steer by sharp sounds and close movement, grip with uninhibited, joint-breaking strength, loop through broken errands when nothing draws them, and slow toward dormancy when starved. Darkness does not help or hurt them; silence does.
beliefs:
  - {held_by: common, text: "Noise brings them. Always.", confidence: 3, cues: [knows_noise_draws_dead]}
  - {held_by: common, text: "Don't let one get both hands on you. You won't get loose.", confidence: 3}
  - {held_by: common, text: "They can smell you if the wind's wrong.", confidence: 1}
  - {held_by: "cohort:post_fall_born", text: "Walkers are sleepwalking people. Wake them up and they get angry.", confidence: 1}
tags: [lore_v1_4, infected]
entities: ["core:infected/ZOMBIE_ARCHETYPE_SHAMBLER01"]
---
The smell belief is false (they are sound-led); it makes survivors waste effort on scent and not on
noise discipline.
