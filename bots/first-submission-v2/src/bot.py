"""First playable Alpha Bot: farm camps, tribute gems, and fight in range."""
import cambc
import survival
from camps import CampPlanner

Team, Item = cambc.Team, cambc.ItemType


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


def move_towards_closest(goals):
    me = cambc.me()
    origin = me.position()
    if not me.can_move() or goals.is_set(origin):
        return False
    blocked = blocked_tiles()
    goals &= ~blocked | cambc.vision.camp_tiles()
    if goals.is_empty():
        return False
    if goals.count() == 1 and not blocked.is_set(goals.positions()[0]):
        return me.move_towards(goals.positions()[0])
    field = cambc.DistanceField()
    field.compute_to(blocked & ~goals, goals, around(origin, 0), cambc.Bitboard())
    reachable = blocked.reachable_tiles(origin, me.base_stats().base_move_speed)
    step = min([origin, *reachable.positions()], key=field.get)
    return step != origin and me.move_absolute(step)


def attack_if_in_range(target):
    me = cambc.me()
    if (me.can_attack() and target.is_visible() and target.health() > 0
            and me.attack_tiles().is_set(target.position())):
        me.attack(target)
        return True
    return False


def farm_camps(planner):
    target = planner.choose_target()
    if target is None:
        return
    if planner.attack_target(target):
        return
    if move_towards_closest(planner.goals(target)):
        planner.attack_target(target)


class Bot:
    def __init__(self):
        self.chosen_stat = None
        self.planner = CampPlanner()
        self.retreating = False

    def buy_items(self):
        me = cambc.me()
        if self.chosen_stat is None:
            self.chosen_stat = 0
        item = (Item.POWER_SHARD_OF_STRENGTH, Item.POWER_SHARD_OF_FOCUS,
                Item.POWER_SHARD_OF_HEALTH)[self.chosen_stat]
        count = me.gold_count() // item.cost()
        if count and me.can_buy(item, count):
            me.buy(item, count)

    def play_turn(self):
        me = cambc.me()
        if me.is_alive():
            self.planner.observe()
        if (not me.is_alive() or me.is_recalling() or me.is_submitting_gems() or me.is_teleporting()
                or (not me.can_move() and not me.can_attack())):
            return
        at_spawn = cambc.game_map.spawn_region(Team.ALLY).is_set(me.position())
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
                if not survival.safe_now(me, found):
                    survival.retreat_step(me, found, blocked_tiles())
                if survival.safe_now(me, found) and survival.try_recall(me):
                    self.retreating = False
                return
            if not found and me.health() < me.max_health() * survival.RECALL_SAFE:
                survival.try_recall(me)
                return
        for enemy in cambc.vision.champions(Team.ENEMY):
            if attack_if_in_range(enemy):
                return
        if me.gem_count() > 0:
            goals = cambc.Bitboard()
            for altar in cambc.game_map.altars().positions():
                if cambc.vision.has_altar_lock(altar):
                    continue
                if me.position().chebyshev_distance(altar) <= cambc.constants.SUBMIT_GEMS_RANGE:
                    me.submit_gems(altar)
                    return
                goals |= around(altar, cambc.constants.SUBMIT_GEMS_RANGE)
            if not goals.is_empty():
                move_towards_closest(goals)
            return
        farm_camps(self.planner)
        me.set_priority(100)
