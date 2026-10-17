"""Camp targeting: remember respawn timers and pick camps by gems per turn of effort.

Verified facts this relies on: camps do not regain health after falling asleep, group
state is only readable while a spawn tile is in vision, and unreachable DistanceField
tiles read 65535.
"""
import cambc
from cambc import game_map

Team = cambc.Team

UNREACHABLE = 65535
GOLD_WEIGHT = 0.1          # one gold is worth this many gems when scoring camps
HELPER_FACTOR = 1.5        # assume some allied damage when estimating clear time
TRIP_TURNS = 40            # rough cost of retreating, recalling and walking back
RESCORE_INTERVAL = 10      # rounds between re-evaluating a committed target
SWITCH_MARGIN = 1.3        # a new target must score this much better to switch


class GroupInfo:
    """Static data for one camp group, cached once per match."""

    def __init__(self, group):
        self.group = group
        self.key = int(group)
        self.tiles = group.spawn_tiles()
        self.spawns = self.tiles.positions()
        self.camps = [(int(c), c.base_stats().base_health, c.base_stats().base_strength)
                      for c in group.camps()]
        self.handles = {h for h, _, _ in self.camps}
        self.value = group.gem_value() + GOLD_WEIGHT * group.gold_value()


class CampPlanner:
    def __init__(self):
        self.groups = None
        self.by_key = {}
        self.respawn_round = {}   # group key -> round it should be alive again
        self.camp_hp = {}         # camp handle -> last seen health (camps never heal)
        self.target = None        # committed GroupInfo
        self.target_respawn = 0
        self.last_scored = -RESCORE_INTERVAL
        self.terrain = None

    def init(self):
        if self.groups is None:
            self.groups = [GroupInfo(g) for g in game_map.camp_groups()]
            self.by_key = {g.key: g for g in self.groups}
            self.owner = {}
            self.all_spawns = cambc.Bitboard()
            for info in self.groups:
                self.all_spawns |= info.tiles
                for p in info.spawns:
                    self.owner[(p.x, p.y)] = info
            self.terrain = (game_map.walls() | game_map.holes() | game_map.altars()
                            | game_map.spawn_region(Team.ENEMY))

    def observe(self):
        """Update respawn timers and camp health from current vision.

        vision.camp_groups()/camps() cost ~600k fuel per call, so test only our cached
        spawn tiles against the visible mask instead.
        """
        self.init()
        now = cambc.round_number()
        visible = cambc.vision.visible_tiles()
        seen = {}
        for p in (visible & self.all_spawns).positions():
            info = self.owner[(p.x, p.y)]
            seen.setdefault(info.key, (info, []))[1].append(p)
        for info, tiles in seen.values():
            try:
                state = info.group.state()
            except cambc.Error:
                continue
            if isinstance(state, game_map.CampGroupRespawning):
                self.respawn_round[info.key] = now + max(1, state.timer)
                for handle in info.handles:
                    self.camp_hp.pop(handle, None)
                continue
            self.respawn_round.pop(info.key, None)
            if isinstance(state, game_map.CampGroupRewardAvailable):
                for handle in info.handles:
                    self.camp_hp[handle] = 0
                continue
            for p in tiles:
                if cambc.vision.has_camp(p):
                    try:
                        camp = cambc.vision.camp_at(p)
                        self.camp_hp[int(camp)] = camp.health()
                    except cambc.Error:
                        pass

    def remaining(self, info):
        hp = sum(self.camp_hp.get(h, base_hp) for h, base_hp, _ in info.camps)
        dps = sum(s for h, _, s in info.camps if self.camp_hp.get(h, 1) > 0)
        return hp, dps

    def score(self, info, dist, now, strength, max_health, capture):
        if dist >= UNREACHABLE:
            return 0.0
        hp, dps = self.remaining(info)
        clear = hp / (strength * HELPER_FACTOR)
        danger = dps * clear / max_health * TRIP_TURNS
        travel = max(dist, self.respawn_round.get(info.key, 0) - now)
        return info.value / (travel + clear + capture + danger + 1)

    def choose_target(self):
        """Commit to the best-scoring group; rescore occasionally with hysteresis."""
        now = cambc.round_number()
        target = self.target
        if target is not None and self.respawn_round.get(target.key, 0) != self.target_respawn:
            target = None   # new information about the committed group
        if target is not None and now - self.last_scored < RESCORE_INTERVAL:
            return target
        self.last_scored = now
        me = cambc.me()
        field = cambc.DistanceField()
        roots = cambc.Bitboard()
        roots.set(me.position())
        field.compute(self.terrain, roots, cambc.Bitboard())
        strength, max_health = max(1.0, me.strength()), max(1.0, me.max_health())
        capture = cambc.constants.CAPTURE_TIME
        best, best_score, current_score = None, 0.0, 0.0
        for info in self.groups:
            dist = min(field.get(p) for p in info.spawns)
            s = self.score(info, dist, now, strength, max_health, capture)
            if target is not None and info.key == target.key:
                current_score = s
            if s > best_score:
                best, best_score = info, s
        if target is not None and current_score > 0 and best_score < current_score * SWITCH_MARGIN:
            best = target
        self.target = best
        self.target_respawn = self.respawn_round.get(best.key, 0) if best is not None else 0
        return best

    def goals(self, info):
        """Spawn tiles to stand on, or a ring around them while the group respawns.

        Standing on a spawn tile delays the whole group's respawn, so wait beside it.
        """
        if self.respawn_round.get(info.key, 0) > cambc.round_number():
            ring = cambc.Bitboard()
            for p in info.spawns:
                ring.draw_chebyshev(p, 2)
            return ring & ~info.tiles
        return info.tiles.copy()

    def attack_target(self, info):
        """Basic-attack a living camp of the target group: dangerous camps first, then low health."""
        me = cambc.me()
        if not me.can_attack():
            return False
        tiles = me.attack_tiles()
        best = None
        for p in info.spawns:
            if not tiles.is_set(p) or not cambc.vision.has_camp(p):
                continue
            try:
                camp = cambc.vision.camp_at(p)
                if int(camp) not in info.handles or camp.health() <= 0:
                    continue
                key = (camp.strength() <= 0, camp.health())
            except cambc.Error:
                continue
            if best is None or key < best[0]:
                best = (key, camp)
        if best is None:
            return False
        me.attack(best[1])
        return True
