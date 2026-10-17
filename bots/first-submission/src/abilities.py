"""Generic ability use, driven by each slot's kind rather than by champion name.

Rules this follows: one successful cast per turn across both slots; abilities with
exclusive_with_movement cannot share a turn with a walk; unit casts need a visible target
inside valid_tiles(); use() returns False for a newly revealed obstruction and raises
cambc.Error for a known-invalid cast.
"""
import cambc

Team = cambc.Team

DAMAGE, CC, AOE, RESET, DASH, HEAL, SHIELD = range(7)
_KINDS = ((cambc.AbilityDamage, DAMAGE), (cambc.AbilityCc, CC), (cambc.AbilityAoeDamage, AOE),
          (cambc.AbilityAttackReset, RESET), (cambc.AbilityDash, DASH),
          (cambc.AbilityHeal, HEAL), (cambc.AbilityShield, SHIELD))
HEAL_BELOW = 0.6


class Slot:
    def __init__(self, index, info):
        self.index = index
        self.kind = next((k for cls, k in _KINDS if isinstance(info, cls)), None)
        self.exclusive = bool(info.exclusive_with_movement)
        self.modifier = getattr(info, 'modifier', 0.0)
        self.radius = getattr(info, 'radius', 0.0)


class Kit:
    """A champion's two ability slots, with the static data read once."""

    def __init__(self, me):
        self.slots = []
        for ability in me.abilities():
            info = ability.info()
            if info is not None:
                self.slots.append(Slot(ability.slot(), info))
        self.kinds = {s.kind for s in self.slots}
        self.cast_this_turn = False

    def ready(self, me, kinds):
        """Ready (slot, ability) pairs of the given kinds; empty when we cannot cast."""
        if self.cast_this_turn or not me.can_cast():
            return []
        out = []
        abilities = None
        for slot in self.slots:
            if slot.kind in kinds:
                if abilities is None:
                    abilities = me.abilities()
                ability = abilities[slot.index]
                if ability.is_ready():
                    out.append((slot, ability))
        return out

    def _use(self, ability, target=None):
        try:
            ok = ability.use(target) if target is not None else ability.use()
        except cambc.Error:
            return False
        if ok:
            self.cast_this_turn = True
        return ok

    def support(self, me, threatened):
        """Heal a hurt ally or shield ourselves. Neither excludes walking."""
        if not self.kinds & {HEAL, SHIELD}:
            return False
        for slot, ability in self.ready(me, (HEAL, SHIELD)):
            if slot.kind == SHIELD and threatened:
                return self._use(ability)
            if slot.kind == HEAL:
                tiles = ability.valid_tiles()
                best = None
                for ally in cambc.vision.champions(Team.ALLY):
                    try:
                        if ally == me or not ally.is_alive() or not tiles.is_set(ally.position()):
                            continue
                        ratio = ally.health() / max(1.0, ally.max_health())
                    except cambc.Error:
                        continue
                    if ratio < HEAL_BELOW and (best is None or ratio < best[0]):
                        best = (ratio, ally)
                if best is not None:
                    return self._use(ability, best[1])
        return False

    def offensive(self, me, foes, will_move):
        """Cast damage, stun or area damage on foes.

        foes: list of (unit, position, strength, health, is_champion), most important first.
        Spells that exclude walking are only cast when we are not going to move.
        """
        if not foes or not self.kinds & {DAMAGE, CC, AOE}:
            return False
        for slot, ability in self.ready(me, (DAMAGE, CC, AOE)):
            if slot.exclusive and will_move:
                continue
            tiles = ability.valid_tiles()
            in_range = [f for f in foes if tiles.is_set(f[1])]
            if not in_range:
                continue
            if slot.kind == AOE:
                best, best_hits = None, 0
                for _, centre, _, _, _ in in_range:
                    hits = sum(1 for f in foes if f[1].chebyshev_distance(centre) <= slot.radius)
                    if hits > best_hits:
                        best, best_hits = centre, hits
                if best is not None and self._use(ability, best):
                    return True
                continue
            if slot.kind == CC and slot.modifier <= 0:
                # A pure stun is wasted on something that does not hit back.
                in_range = [f for f in in_range if f[2] > 0]
                if not in_range:
                    continue
            if self._use(ability, in_range[0][0]):
                return True
        return False

    def reset_attack(self, me):
        """After a basic attack, refresh it so we can attack again this turn."""
        if RESET not in self.kinds:
            return False
        for slot, ability in self.ready(me, (RESET,)):
            return self._use(ability)
        return False

    def dash_to(self, me, field, blocked):
        """Dash up to two tiles to the tile with the lowest field value, if that beats walking."""
        if DASH not in self.kinds:
            return False
        ready = self.ready(me, (DASH,))
        if not ready:
            return False
        origin = me.position()
        walk = min([origin, *blocked.reachable_tiles(origin, 1).positions()], key=field.get)
        best = min(blocked.reachable_tiles(origin, 2).positions(), key=field.get, default=origin)
        if field.get(best) >= field.get(walk):
            return False
        return self._use(ready[0][1], best)
