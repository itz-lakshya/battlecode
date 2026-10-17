# CAMBC 2026 — Project Brief and Claude Code Instructions

## Mission
Build a competitive bot for Cambridge Battlecode 2026a (CAMBC). The objective is to win by tributing gems at altars, not merely killing monsters, collecting gold, or carrying gems. Work iteratively: understand code/rules, identify measurable weaknesses, make small changes, build, run multiple matches/maps, inspect replays, and retain only evidence-backed improvements.

The user is a strong competitive programmer (around Codeforces 1700) but is new to this game API and bot workflow. Explain important decisions clearly and provide exact commands when useful.

## Workspace and preservation rules
Workspace: `$HOME/Downloads/CAMBC`

- `bots/starter-python/`: CAMBC Python starter
- `bots/starter-cpp/`: CAMBC C++ starter
- `bots/first-submission/`: user's imported Python submission
- `maps/`: local maps
- `cambc.toml`, `sdk/`, `cmake/`: workspace support/configuration

Original ZIP: `$HOME/Downloads/First submission.zip`. **Never delete or overwrite it.** It contained `alpha-bot/src/{bot.py,draft.py,main.py,randomness.py}`. Those four files were copied into `bots/first-submission/src/`, retaining the CAMBC scaffold.

A baseline match was run:
`cambc run first-submission starter-python --view`
Team A was `first-submission`; Team B was `starter-python`. In one observed match, Team B reached 1,000 tributed gems around round 1415 while Team A had 716. Team A's replay log said it did not print output. This is only one result; do not overgeneralize or assume the missing print itself caused the loss.

## Sources of truth
1. Actual workspace code and local `GameRules.md`, if present.
2. Official CAMBC API: https://2026a.battlecode.co.uk/game/api
3. First bot guide: https://2026a.battlecode.co.uk/game/docs/first-bot
4. VS Code guide: https://2026a.battlecode.co.uk/game/docs/vscode

Verify API names, parameters, return values, and action legality in the installed SDK/starter/docs before using them. **Do not invent API functions or game mechanics.** Read the complete rules before major strategic changes and distinguish verified facts from hypotheses.

## Core game rules
### Victory
- First team to tribute **1,000 gems** wins immediately.
- At the round limit, compare tributed gems, then lifetime gold earned, then champion kills.
- If all those tie, Team B wins the tiebreak.
- Carried gems do not count as victory score until tributed. Death can cause carried gems to be lost/stolen.
- Gold funds upgrades, but gems tributed are the main objective.

### Camps and capture
- Defeat every monster in a connected camp group, then occupy at least one of its spawn tiles uncontested to capture its reward.
- Capture requires a five-round timer. Leaving the region empty or allowing an enemy to contest it resets progress. More allies do not speed capture; rewards are split among allies present when it finishes.
- Rewards can include gems and gold. Groups respawn after their cooldown. Occupying a spawn tile delays the entire group from respawning.
- Monsters awaken when hit and attack the nearest champion each turn until they die or have not taken damage for two turns. They have range 3 and vision 8, see through bushes, and do not chase.
- Killing monsters is not enough: the strategy must secure the camp's capture reward.

### Gem tribute and altars
- To tribute, a champion must be within Chebyshev distance 1 of an unlocked altar and start a tribute.
- Duration is `max(1, ceil(carried_gems / 10))` champion-turn ends. The starting turn counts; completion occurs at the champion's next turn start after the timer reaches zero.
- Damage does not interrupt tribute; stun, death, or an altar lock does.
- An altar lock blocks the opposing team and cancels existing tribute channels there; it can be cleared by three basic attacks. Attempts to tribute against an enemy lock become attacks against the lock.
- Evaluate when to bank gems versus carrying more, accounting for death risk, travel distance, altar locks, and channel time.

### Champion actions and recall
- Each champion has its own bot instance and its own turns.
- A champion can move one tile in any of eight directions, make a basic attack, and use abilities subject to their cooldown/action rules.
- Melee champions can generally move and basic-attack in one turn. Ranged champions generally cannot move and basic-attack in the same turn; damaging ranged abilities may have similar restrictions. Verify each ability's exact rules.
- Both ability slots share a one-cast-per-turn limit. Cooldowns and walking compatibility depend on the ability.
- Every champion has a ward with persistent vision over range 6; it can be placed within 2 tiles and relocated each turn.
- Recall channels for five owner-turn ends (three with Home); the starting turn counts. Arrival happens at the next turn start after the timer reaches zero. Damage or stun cancels recall. A champion keeps carried gems during recall and should remain on spawn through the end of its arrival turn to heal fully.
- Champions can buy upgrades/items on spawn tiles. Choose upgrades based on actual champion stats, passives, role, and test results.

### Draft and memory
- The full map is visible during draft, and draft has extra compute. Use map/camp layout to make informed champion choices.
- Teams select 3–5 champions depending on map. Picks are unique within a team; opponents may pick the same champion. Cassi & Issac count as one draft selection.
- Draft memory is 1,024 bytes, writable during draft and read-only during gameplay. It can encode an opening plan.
- Team shared memory is 8 bytes for the whole match. Each champion has its own bot instance; per-instance state is not automatically team-global.
- If draft code fails to pick, remaining picks are randomized. Treat draft failures as serious bugs.

### Fuel
The supplied rules file says C++/Rust receive 100k fuel per turn, OCaml 5x, Python 25x the C++ limit. Verify against current official docs if this matters. Draft gets extra first-turn fuel and gameplay gets extra first-turn fuel for initialization/precomputation. Fuel is deterministic; unused fuel is not carried forward. Python is the sensible initial language because the existing bot is Python and its fuel budget is generous.

## Champion roster
Roster includes Cassi & Issac, Ryth, Vesper Vale, Prism, Stellar, Vendetta, Marcella, Tavi, Willow, Ren, and Varg. Read the full rules/API for exact stats, passives, abilities, ranges, costs, cooldowns, and action compatibility before implementing champion-specific logic.

Cassi & Issac are one draft choice but two separately acting bodies with separate positions, bags, abilities, and bot instances. If either dies, both die; both lose carried gems and together grant one kill reward. Treat them as a linked-risk pair.

## Current bot architecture
### `bots/first-submission/src/main.py`
Creates a `Bot`, loops, calls `draft.play()` during draft or `bot.play_turn()` otherwise, catches exceptions, then calls `cambc.end_turn()`.

### `draft.py`
Reads allied picks, builds a list of champion IDs not already selected, submits `ALPHA_V1` to draft memory, and randomly picks an available champion. It is a placeholder, not strategic drafting.

### `bot.py`
Has helpers for tiles, movement/pathfinding, attacks, and camp farming. The `Bot` buys Strength Shards, recalls below 25% health away from spawn, attacks an enemy champion if in range, submits carried gems at an unlocked altar, otherwise farms camps, then sets a fixed priority. Camp goals are recomputed each turn. This is a basic baseline.

### `randomness.py`
Provides `below(limit)` using deterministic pseudo-randomness with a fixed initial state and xorshift-like operations. It is a helper, not the strategy.

### Difference from CAMBC starter
The starter has similar overall architecture. Its gameplay code caches camp layout, randomly chooses Strength/Focus/Health and sticks to that stat, recalls below 35% health away from spawn, prints draft-memory/shared-round diagnostics, and uses randomized rather than fixed priority. Its draft code still picks randomly but submits `hello world` as draft memory. These differences do not prove the starter is always strategically superior.

## Development priorities
1. **Reliability:** no exceptions, invalid actions, missed draft picks, or fuel exhaustion. Safely handle dead/recalling/submitting/stunned/action-limited states.
2. **Baseline instrumentation:** track winner, rounds to victory, tributed gems, gold earned, kills/deaths, camp captures, and errors if available. Inspect replays for wasted movement, uncaptured camps, dangerous gem carrying, and altar timing.
3. **Resource economy:** target camps by expected rewards, clear time, damage risk, travel, respawn, and capture feasibility. Ensure someone stays on a spawn tile until capture completes. Avoid unnecessary champion overlap. Make risk-aware bank-vs-carry decisions.
4. **Movement:** respect terrain/occupants per API. Avoid oscillation, unreachable goals, redundant paths, and respawning camps. Use verified pathfinding APIs.
5. **Combat/survival:** use champion-specific abilities, cooldowns, ranges, status effects, and action constraints. Prioritize targets by threat, kill potential, carried gems, escape risk, and scoring tempo. Avoid low-value chases. Recall based on health, carried gems, damage risk, travel, and time cost.
6. **Draft:** choose complementary champions based on map, camps, synergies, survival, and scoring tempo. Use draft memory for coordination if supported. Account for Cassi & Issac's linked death.
7. **Upgrades:** test shard choices against actual stat growth/passives; do not use a universal choice without evidence.
8. **Scientific testing:** keep starter as baseline; run multiple matches/maps and both sides when possible. Compare win rate, average tributed gems, rounds to victory, gold, kills/deaths, errors. Change one major factor at a time. Preserve good versions with Git commits/branches. One match is not proof.

## Commands
Run from the workspace root:
```bash
cd "$HOME/Downloads/CAMBC"
```
Build:
```bash
cambc build first-submission
cambc build starter-python
cambc build starter-cpp
```
Visual match:
```bash
cambc run first-submission starter-python --view
```
Refresh maps:
```bash
cambc maps pull
```
Check exact local CLI syntax before batch runs:
```bash
cambc --help
cambc run --help
cambc run-batch --help
```
Do not invent a batch match-list format; check installed CLI help or official docs.

## Instructions to Claude Code
Act as a careful competitive-game AI engineer. Do not blindly rewrite everything.

Before changing code:
1. Inspect the repository tree and `cambc.toml`.
2. Read the complete local game rules.
3. Read all four files in `bots/first-submission/src/` and corresponding starter files.
4. Verify relevant APIs against current official docs/SDK.
5. Establish a reproducible baseline and identify likely strategic bottlenecks.

When changing code:
- Explain the bug/weakness, the evidence, and expected measurable effect.
- Prefer small, reviewable changes.
- Preserve scaffold/config files and both starter bots.
- Use `first-submission` for experiments unless there's a clear reason not to.
- Never delete/modify the original ZIP.
- Do not add dependencies unless necessary and compatible.
- Keep choices deterministic when practical; consider fuel and cache only when safe.
- Keep champion-local state distinct from team shared memory.
- Ensure draft always makes a legal pick and handles edge cases.
- Avoid noisy prints in normal matches; gate or remove debug logs.
- Do not claim a strategy is better without multi-match testing.
- After edits, build and run appropriate tests, then report exact commands and results.
- Diagnose actual errors before unrelated edits.
- Ask before broad rewrites or destructive operations. Never reset/delete/overwrite baselines without permission.

## First task
Start with a **read-only audit**; do not edit code yet.
1. Confirm workspace and bot files.
2. Read the full rules and current API docs.
3. Explain current control flow and likely reasons the bot lost to starter.
4. List the top 3–5 potential improvements. For each, give code/rule evidence, expected scoring effect, complexity/risk, and a test plan.
5. Recommend the first small improvement and wait for user approval before implementing it.

The goal is not sophisticated-looking code; it is a reliable bot that scores more tributed gems and wins more matches.
