"""Survival: step out of danger before recalling, since damage cancels a recall.

Camps (range 3) attack the nearest champion and never chase, so leaving their range is
always enough to stop camp damage. Enemy champions are treated as able to step once
before attacking.
"""
import cambc
from cambc import game_map

Team = cambc.Team

CAMP_RANGE = 3
SCAN_RADIUS = 5
LOW_HEALTH = 0.25        # retreat under fire below this fraction regardless of estimates
RECALL_SAFE = 0.4        # recall when out of danger below this fraction
RECALL_AFTER_RETREAT = 0.5


def around(position, radius):
    tiles = cambc.Bitboard()
    tiles.draw_chebyshev(position, radius)
    return tiles


def threats(me):
    """Return [(position, reach, damage)] for units that can hit this champion next round."""
    origin = me.position()
    found = []
    near = around(origin, SCAN_RADIUS)
    camp_tiles = cambc.vision.camp_tiles() & around(origin, CAMP_RANGE)
    if not camp_tiles.is_empty():
        allies = cambc.vision.champion_tiles(Team.ALLY)
        allies.set(origin, False)
        for p in camp_tiles.positions():
            try:
                camp = cambc.vision.camp_at(p)
                if not camp.is_awake() or camp.strength() <= 0:
                    continue
                damage = camp.strength()
            except cambc.Error:
                continue
            d = origin.chebyshev_distance(p)
            # The camp hits its nearest champion; an ally strictly closer shields us.
            if d > 1 and not (allies & around(p, d - 1)).is_empty():
                continue
            found.append((p, CAMP_RANGE, damage))
    enemy_tiles = cambc.vision.champion_tiles(Team.ENEMY) & near
    for p in enemy_tiles.positions():
        try:
            enemy = cambc.vision.champion_at(p)
            found.append((p, enemy.attack_range() + 1, enemy.strength()))
        except cambc.Error:
            continue
    return found


def escape_turns(origin, found):
    return max(reach + 1 - origin.chebyshev_distance(p) for p, reach, _ in found)


def should_retreat(me, found):
    if not found:
        return False
    incoming = sum(damage for _, _, damage in found)
    hp = me.health()
    return hp < me.max_health() * LOW_HEALTH or hp <= incoming * (escape_turns(me.position(), found) + 1)


def retreat_step(me, found, blocked, kit=None):
    """Move to the neighbour farthest from every threat, breaking ties towards our spawn.
    Dash first when two tiles gets us meaningfully farther than one."""
    origin = me.position()
    home = game_map.spawn_region(Team.ALLY).positions()[0]

    def key(tile):
        return (min(tile.chebyshev_distance(p) - reach for p, reach, _ in found),
                -tile.chebyshev_distance(home))

    options = [origin, *blocked.reachable_tiles(origin, 1).positions()]
    best = max(options, key=key)
    if kit is not None and survival_dash(me, kit, blocked, key, key(best)):
        origin = me.position()
        if safe_now(me, found) or not me.can_move():
            return True
        blocked = (game_map.walls() | game_map.holes() | game_map.altars()
                   | game_map.spawn_region(Team.ENEMY) | cambc.vision.champion_tiles()
                   | cambc.vision.camp_tiles() | cambc.vision.teleport_tiles())
        blocked.set(origin, False)
        best = max([origin, *blocked.reachable_tiles(origin, 1).positions()], key=key)
    if best != origin and me.can_move():
        return me.move_absolute(best)
    return False


def survival_dash(me, kit, blocked, key, walk_value):
    from abilities import DASH
    ready = kit.ready(me, (DASH,))
    if not ready:
        return False
    options = blocked.reachable_tiles(me.position(), 2).positions()
    if not options:
        return False
    best = max(options, key=key)
    return key(best) > walk_value and kit._use(ready[0][1], best)


def safe_now(me, found):
    origin = me.position()
    return all(origin.chebyshev_distance(p) > reach for p, reach, _ in found)


def try_recall(me):
    try:
        me.recall()
        return True
    except cambc.Error:
        return False
