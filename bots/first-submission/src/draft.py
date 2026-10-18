"""Draft: take the first champion in our preference order that we have not picked yet.

Picks are unique within a team only, so the opponent never blocks us. If anything goes
wrong we still pick a legal champion: a missed pick is randomised by the game.
"""
import cambc

D = cambc.ChampionDraft
# Best tested order (docs/EXPERIMENTS.md, variant d4); later entries are only fallbacks.
PREFERENCE_STANDARD = [D.VENDETTA, D.VARG, D.TAVI, D.MARCELLA, D.STELLAR,
                       D.REN, D.VESPER_VALE, D.RYTH, D.CASSI_AND_ISSAC, D.WILLOW, D.PRISM]
PREFERENCE_LARGE = [D.VENDETTA, D.VARG, D.TAVI, D.VESPER_VALE, D.REN,
                    D.MARCELLA, D.STELLAR, D.RYTH, D.CASSI_AND_ISSAC, D.WILLOW, D.PRISM]
MEMORY = b"ALPHA_V3"


def get_preference():
    try:
        w, h = cambc.game_map.width(), cambc.game_map.height()
        if max(w, h) >= 60:
            return PREFERENCE_LARGE
    except Exception:
        pass
    return PREFERENCE_STANDARD


def play():
    chosen = []
    try:
        chosen = [int(c) for c in cambc.draft.current_draft(cambc.Team.ALLY)]
        cambc.draft_memory.submit(MEMORY)
    except Exception:
        pass
    for champion in get_preference() + list(range(11)):
        if int(champion) in chosen:
            continue
        try:
            cambc.draft.pick(champion)
            return
        except Exception:
            continue
