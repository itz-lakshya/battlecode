"""Small deterministic pseudo-random helper compatible with the starter bot."""
_state = 2463534242

def below(limit):
    global _state
    if limit <= 1:
        return 0
    _state ^= (_state << 13) & 0xFFFFFFFF
    _state ^= (_state >> 17)
    _state ^= (_state << 5) & 0xFFFFFFFF
    _state &= 0xFFFFFFFF
    return _state % limit
