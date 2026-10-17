"""Draft phase policy."""
import cambc
from randomness import below


def play():
    chosen = cambc.draft.current_draft(cambc.Team.ALLY)
    available = [pick for pick in range(11) if pick not in chosen]
    cambc.draft_memory.submit(b"ALPHA_V1")
    if available:
        cambc.draft.pick(available[below(len(available))])
