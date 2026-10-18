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
    """Visible enemy champions within spell range, lowest health first, ignoring enemies on their spawn."""
    out = []
    enemy_spawn = cambc.game_map.spawn_region(Team.ENEMY)
    tiles = cambc.vision.champion_tiles(Team.ENEMY) & around(me.position(), ENEMY_SCAN)
    for p in tiles.positions():
        if enemy_spawn.is_set(p):
            continue  # Enemy on spawn heals fully every turn; fighting them is a fatal distraction
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
        self.monster_shards_bought = 0
        self.planner = CampPlanner()
        self.retreating = False
        self.kit = None
        self.altars = None

    def buy_items(self):
        me = cambc.me()
        gold = me.gold_count()
        # Buy an altar lock if we don't have one and can afford it (10g)
        try:
            has_lock = any(c.kind() == cambc.ConsumableType.ALTAR_LOCK and c.count() > 0 for c in me.consumables())
            if not has_lock and gold >= 10 and me.can_buy(cambc.ConsumableType.ALTAR_LOCK, 1):
                me.buy(cambc.ConsumableType.ALTAR_LOCK, 1)
                gold = me.gold_count()
        except Exception:
            pass
        # Buy 5 Monster Shards of Strength first (combines into Monster Emblem: +10% camp damage)
        if self.monster_shards_bought < 5:
            item = Item.MONSTER_SHARD_OF_STRENGTH
            cost = item.cost()
            count = min(gold // cost, 5 - self.monster_shards_bought)
            if count and me.can_buy(item, count):
                try:
                    me.buy(item, count)
                    self.monster_shards_bought += count
                    gold = me.gold_count()
                except cambc.Error:
                    pass
        # Then buy Power Shards of Strength
        item = Item.POWER_SHARD_OF_STRENGTH
        cost = item.cost()
        count = gold // cost
        if count and me.can_buy(item, count):
            try:
                me.buy(item, count)
            except cambc.Error:
                pass

    def tribute(self, me):
        """Bank gems at an altar; if adjacent to ANY altar, submit gems or attack enemy lock."""
        if self.altars is None:
            r = cambc.constants.SUBMIT_GEMS_RANGE
            self.altars = [(a, around(a, r)) for a in cambc.game_map.altars().positions()]
        origin = me.position()
        try:
            for c in me.consumables():
                if c.kind() == cambc.ConsumableType.ALTAR_LOCK and c.count() > 0:
                    for altar, _ in self.altars:
                        if origin.chebyshev_distance(altar) <= 2 and not cambc.vision.has_altar_lock(altar):
                            c.use(altar)
                            break
        except Exception:
            pass
        # 1. If already adjacent to an altar, ALWAYS submit/attack!
        for altar, ring in self.altars:
            if ring.is_set(origin):
                try:
                    me.submit_gems(altar)
                    return
                except cambc.Error:
                    pass
        # 2. Otherwise path to the closest altar, preferring ones without enemy locks
        open_goals, locked_goals = cambc.Bitboard(), cambc.Bitboard()
        for altar, ring in self.altars:
            if cambc.vision.has_altar_lock(altar):
                try:
                    lock = cambc.vision.altar_lock_at(altar)
                    if lock.is_ally():
                        open_goals |= ring
                    else:
                        locked_goals |= ring
                except cambc.Error:
                    locked_goals |= ring
            else:
                open_goals |= ring
        goals = open_goals if not open_goals.is_empty() else locked_goals
        move_towards_closest(goals, self.kit)

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
        # Buy items: at spawn, or anywhere in the field for Tavi
        self.buy_items()
        if at_spawn:
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
        if enemies:
            # Close the gap on enemy champions: approach within attack range
            enemy_pos = enemies[0][1]
            enemy_goals = around(enemy_pos, me.attack_range())
            if fight(me, kit, enemies, enemy_goals):
                return
        gems = me.gem_count()
        if gems > 0:
            if self.altars is None:
                r = cambc.constants.SUBMIT_GEMS_RANGE
                self.altars = [(a, around(a, r)) for a in cambc.game_map.altars().positions()]
            origin = me.position()
            close_to_altar = any(origin.chebyshev_distance(a) <= 8 for a, _ in self.altars)
            winning = cambc.global_submitted_gems(Team.ALLY) + gems >= 1000
            # Bank if carrying a good batch, already near an altar, or about to win
            if gems >= 25 or close_to_altar or winning:
                self.tribute(me)
                return
        target = self.planner.choose_target(kit.kite_dps(me))
        if target is None:
            if gems > 0:
                self.tribute(me)
            return
        fight(me, kit, self.planner.foes(target), self.planner.goals(target), self.planner.avoid(target))
