"""Society band (P9): population, households, routines, work, settlements, groups.
docs/as/06_WORLD.md §2. The coupling matrix (Rebuild Plan §8.10.1) is the P9 test plan: a single
injured worker must demonstrably reach morale (ECON-01), relationships drift with the PC absent
(SOC-02), and a single rumour must demonstrably reach trade (SOC-03).

How it runs: nothing here ticks by itself. A settlement's clocks are event_queue rows —
SETTLEMENT_DAY (society.settlement.day), PRODUCTION_CYCLE (society.work.cycle), GROUP_DAY
(society.group.day), ROUTINE_STEP (society.routine.step) — started by turn.timers.seed_society and
fired by turn.timers like every other timer, inside the turn pipeline's windows or the off-screen
step (turn.timers.run_offscreen). Consequences between them are declarative cascade content
(as_content/packs/core/cascade/economy.yaml, people.yaml) applied by action.cascade. A world with
no settlements (every P7 scenario) runs exactly as before.

Owners: society.population (cohorts), society.household (households, household_members),
society.routine (routines), society.work (workplaces, work_assignments), society.settlement
(settlements, laws_active), society.group (groups, group_members, group_standing, tension).
Rule families: DEMO, HH, ROUT, WORK, STL, GRP, STAND (mind.mind), INFO (world.rumours), ECON, SOC.
"""
