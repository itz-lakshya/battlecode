"""Draft: take the first champion in our preference order that we have not picked yet.

Picks are unique within a team only, so the opponent never blocks us. If anything goes
wrong we still pick a legal champion: a missed pick is randomised by the game.
"""
import cambc

D = cambc.ChampionDraft
# Best tested order (docs/EXPERIMENTS.md, variant d4); later entries are only fallbacks.
PREFERENCE = [D.VENDETTA, D.VARG, D.TAVI, D.MARCELLA, D.STELLAR,
              D.REN, D.VESPER_VALE, D.RYTH, D.CASSI_AND_ISSAC, D.WILLOW, D.PRISM]
MEMORY = b"ALPHA_V2"


def play():
    chosen = []
    try:
        chosen = [int(c) for c in cambc.draft.current_draft(cambc.Team.ALLY)]
        cambc.draft_memory.submit(MEMORY)
    except Exception:
        pass
    for champion in PREFERENCE + list(range(11)):
        if int(champion) in chosen:
            continue
        try:
            cambc.draft.pick(champion)
            return
        except Exception:
            continue
