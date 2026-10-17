"""Alpha Bot: farm the best camp, bank gems at altars, fight in range, never die needlessly."""
import cambc
import survival
from abilities import Kit
from camps import CampPlanner

Team, Item = cambc.Team, cambc.ItemType
ENEMY_SCAN = 4   # spell range: enemies this close are fought before farming


def around(position, radius):
    tiles = cambc.Bitboard()
    tiles.draw_chebyshev(position, radius)
    return tiles


def blocked_tiles():
    blocked = (cambc.game_map.walls() | cambc.game_map.holes() | cambc.game_map.altars()
               | cambc.game_map.spawn_region(Team.ENEMY) | cambc.vision.champion_tiles()
               | cambc.vision.camp_tiles() | cambc.vision.teleport_tiles())
    blocked.set(cambc.me().position(), False)
    return blocked


def move_towards_closest(goals, kit=None, avoid=None):
    """Step (dashing first when that gets closer) towards the nearest goal tile,
    never entering avoid tiles."""
    me = cambc.me()
    origin = me.position()
    if not me.can_move() or goals.is_set(origin):
        return False
    blocked = blocked_tiles()
    if avoid is not None:
        blocked |= avoid
        blocked.set(origin, False)
    goals &= ~blocked | cambc.vision.camp_tiles()
    if goals.is_empty():
        return False
    field = cambc.DistanceField()
    field.compute_to(blocked & ~goals, goals, around(origin, 0), cambc.Bitboard())
    dashed = kit is not None and kit.dash_to(me, field, blocked)
    if dashed:
        origin = me.position()
        if goals.is_set(origin) or not me.can_move():
            return True
        blocked = blocked_tiles()   # the dash changed our vision; units may have appeared
        if avoid is not None:
            blocked |= avoid
            blocked.set(origin, False)
    step = min([origin, *blocked.reachable_tiles(origin, 1).positions()], key=field.get)
    return (step != origin and me.move_absolute(step)) or dashed


def basic_attack(me, foes):
    """Attack the highest-priority living foe inside our attack range."""
    if not foes or not me.can_attack():
        return False
    tiles = me.attack_tiles()
    for unit, position, _, _, _ in foes:
        if not tiles.is_set(position):
            continue
        try:
            if not unit.is_visible() or unit.health() <= 0:
                continue
            me.attack(unit)
            return True
        except cambc.Error:
            continue
    return False


def fight(me, kit, foes, goals, avoid=None):
    """Spells before moving, basic attack (twice with a reset), otherwise approach."""
    in_reach = any(me.attack_tiles().is_set(f[1]) for f in foes)
    will_move = goals is not None and not in_reach and not goals.is_set(me.position())
    cast = kit.offensive(me, foes, will_move)
    if basic_attack(me, foes):
        if kit.reset_attack(me):
            basic_attack(me, foes)
        return True
    if cast:
        return True
    if goals is not None and move_towards_closest(goals, kit, avoid):
        kit.offensive(me, foes, will_move=True)
        if basic_attack(me, foes) and kit.reset_attack(me):
            basic_attack(me, foes)
        return True
    return False


def enemy_foes(me):
    """Visible enemy champions within spell range, lowest health first."""
    out = []
    tiles = cambc.vision.champion_tiles(Team.ENEMY) & around(me.position(), ENEMY_SCAN)
    for p in tiles.positions():
        try:
            enemy = cambc.vision.champion_at(p)
            if enemy.is_alive():
                out.append((enemy, p, enemy.strength(), enemy.health(), True))
        except cambc.Error:
            continue
    out.sort(key=lambda f: f[3])
    return out


class Bot:
    def __init__(self):
        self.chosen_stat = None
        self.planner = CampPlanner()
        self.retreating = False
        self.kit = None
        self.altars = None

    def buy_items(self):
        me = cambc.me()
        if self.chosen_stat is None:
            self.chosen_stat = 0
        item = (Item.POWER_SHARD_OF_STRENGTH, Item.POWER_SHARD_OF_FOCUS,
                Item.POWER_SHARD_OF_HEALTH)[self.chosen_stat]
        count = me.gold_count() // item.cost()
        if count and me.can_buy(item, count):
            me.buy(item, count)

    def tribute(self, me):
        """Bank gems at the nearest altar; a locked altar is still usable as a last resort
        because tributing against a lock attacks it (three hits clear it)."""
        if self.altars is None:
            r = cambc.constants.SUBMIT_GEMS_RANGE
            self.altars = [(a, around(a, r)) for a in cambc.game_map.altars().positions()]
        origin = me.position()
        open_goals, locked_goals = cambc.Bitboard(), cambc.Bitboard()
        for altar, ring in self.altars:
            locked = cambc.vision.has_altar_lock(altar)
            if ring.is_set(origin) and not locked:
                me.submit_gems(altar)
                return
            if locked:
                locked_goals |= ring
            else:
                open_goals |= ring
        if open_goals.is_empty():
            for altar, ring in self.altars:
                if ring.is_set(origin):
                    try:
                        me.submit_gems(altar)
                    except cambc.Error:
                        pass
                    return
            open_goals = locked_goals
        move_towards_closest(open_goals, self.kit)

    def play_turn(self):
        me = cambc.me()
        if not me.is_alive():
            self.buy_items()   # dead champions may shop
            return
        if self.kit is None:
            self.kit = Kit(me)
        kit = self.kit
        kit.cast_this_turn = False
        self.planner.observe()
        if (me.is_recalling() or me.is_submitting_gems() or me.is_teleporting()
                or (not me.can_move() and not me.can_attack())):
            return
        me.set_priority(100)
        at_spawn = cambc.game_map.spawn_region(Team.ALLY).is_set(me.position())
        found = []
        if at_spawn:
            self.buy_items()
            if me.health() < me.max_health():
                # Spawn heals fully at turn end; stepping off now would forfeit it.
                self.retreating = False
                return
        else:
            found = survival.threats(me)
            if survival.should_retreat(me, found):
                self.retreating = True
            if self.retreating:
                # Damage cancels a recall, so leave every threat's range first.
                kit.support(me, True)
                if not survival.safe_now(me, found):
                    survival.retreat_step(me, found, blocked_tiles(), kit)
                if survival.safe_now(me, found) and survival.try_recall(me):
                    self.retreating = False
                return
            if not found and me.health() < me.max_health() * survival.RECALL_SAFE:
                survival.try_recall(me)
                return
        kit.support(me, bool(found))
        enemies = enemy_foes(me)
        if enemies and fight(me, kit, enemies, None):
            return
        if me.gem_count() > 0:
            self.tribute(me)
            return
        target = self.planner.choose_target(kit.kite_dps(me))
        if target is None:
            return
        fight(me, kit, self.planner.foes(target), self.planner.goals(target), self.planner.avoid(target))
