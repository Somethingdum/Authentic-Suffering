---
schema: as.lore.v1
id: false_death
title: Dead is not dead
kind: infected
truth: Catastrophic shock can switch a baseline infected off for hours; if the brainstem and upper spinal junction survive, it reboots — usually six to fourteen hours later, longer for a Runner after extreme exertion. Only destroying that junction, or fully denaturing the core tissue with fire, acid or total pulping, ends it. Lurkers are alive and die like any animal.
beliefs:
  - {held_by: common, text: "If it's not the head, it's not dead.", confidence: 3, cues: [knows_headshot_rule, knows_false_death]}
  - {held_by: "cohort:fall_child", text: "They play dead. They wait for you to turn your back.", confidence: 2, cues: [knows_false_death]}
  - {held_by: "cohort:pre_fall_adult", text: "Shoot them enough and they stay down.", confidence: 1}
tags: [lore_v1_2_3, infected]
entities: ["core:infected/ZOMBIE_ARCHETYPE_SHAMBLER01", "core:infected/ZOMBIE_VARIANT_ID_RUNNER01"]
---
"They play dead and wait" is a belief, not truth — false death is shutdown, not strategy. It gives
the same practical advice for the wrong reason.
