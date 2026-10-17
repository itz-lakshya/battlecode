# Experiment log

All suites: 17 maps x 2 sides = 34 games, `tools/suite.sh BOT OPP`. Engine is deterministic.

## Bot versions vs starter-python

| Version | Wins | Avg tributed gems | Deaths/game (camp) |
|---|---|---|---|
| v0 baseline | 25/34 | 809 | 19.8 (16.7) |
| v1 camp memory + gem targeting | 27/34 | 873 | 16.4 (12.0) |
| v2 retreat before recall | 33/34 | 906 | 1.8 (0.6) |
| v3 abilities, dash | 34/34 | 908 | 1.3 (0.6) |
| v4 kiting on gem-starved maps | 34/34 | 999 | 1.7 (0.9) |

Head-to-head: v2 beat v1 29/34 and v0 31/34; v3 beat v2 32/34.
Kiting allowed on every map lost 11/34 to v3; restricted to gem-starved maps it is
17/34 (mirror parity) vs v3 while fixing stampede (0 -> 1080) and contest B (0 -> 1000).

## Draft compositions vs the v4 draft (Tavi, Marcella, Vendetta, Ren, Vesper)

Preference order; 3/4-champion maps use the first 3/4.

| Variant | Order | Wins vs v4 draft | Avg gems (variant vs v4) | Rounds to 1000 vs starter |
|---|---|---|---|---|
| v4 draft | Tavi, Marcella, Vendetta, Ren, Vesper | - | - | 750 |
| d1 | Varg, Vendetta, C&I, Ryth, Tavi | 19/34 | 836 vs 854 | 647 |
| d2 | C&I, Varg, Vendetta, Marcella, Stellar | 18/34 | 837 vs 874 | - |
| d3 | Varg, Vendetta, Ryth, Marcella, Vesper | 13/34 | 845 vs 918 | - |
| **d4** | **Vendetta, Varg, Tavi, Marcella, Stellar** | **19/34** | **917 vs 847** | **681** |
| d5 | C&I, Vendetta, Varg, Tavi, Ren | 19/34 | 830 vs 880 | 668 |
| d6 | Varg, Ryth, Marcella, Vendetta, Stellar | 12/34 | 818 vs 874 | - |

d4 chosen: only variant that won head-to-head with more gems, 34/34 vs starter, 9% faster.
d1 farms fastest but died 8.6/game vs 3.3 head-to-head (Cassi & Issac linked deaths).

## Not tested (ideas only)
- Shop order Monster Strength emblem -> Jungle Health emblem -> Power Strength shards.
- Bank gems only at >= 30 carried or when an altar is within 8 tiles.
