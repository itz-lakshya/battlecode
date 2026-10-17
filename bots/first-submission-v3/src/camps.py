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


_KIND_STATS = {}


def kind_stats(camp):
    """(base health, base strength) per camp type; each API call costs fuel, so cache."""
    kind = int(camp.kind())
    if kind not in _KIND_STATS:
        stats = camp.base_stats()
        _KIND_STATS[kind] = (stats.base_health, stats.base_strength)
    return _KIND_STATS[kind]


class GroupInfo:
    """Static data for one camp group, cached once per match."""

    def __init__(self, group):
        self.group = group
        self.key = int(group)
        self.tiles = group.spawn_tiles()
        self.spawns = self.tiles.positions()
        self.anchor = self.spawns[0]   # groups are compact: one tile is enough for distance
        self.camps = [(int(c), *kind_stats(c)) for c in group.camps()]
        self.handles = {h for h, _, _ in self.camps}
        self.value = group.gem_value() + GOLD_WEIGHT * group.gold_value()
        self.hp = sum(hp for _, hp, _ in self.camps)        # remaining, maintained by observe
        self.dps = sum(st for _, _, st in self.camps)

    def refresh(self, camp_hp):
        self.hp = sum(camp_hp.get(h, hp) for h, hp, _ in self.camps)
        self.dps = sum(st for h, _, st in self.camps if camp_hp.get(h, 1) > 0)


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
                info.refresh(self.camp_hp)
                continue
            self.respawn_round.pop(info.key, None)
            if isinstance(state, game_map.CampGroupRewardAvailable):
                for handle in info.handles:
                    self.camp_hp[handle] = 0
                info.refresh(self.camp_hp)
                continue
            if info is not self.target:
                continue   # reading camp health costs fuel; only track the group we fight
            for p in tiles:
                if cambc.vision.has_camp(p):
                    try:
                        camp = cambc.vision.camp_at(p)
                        self.camp_hp[int(camp)] = camp.health()
                    except cambc.Error:
                        pass
            info.refresh(self.camp_hp)

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
        # score = value / (travel + clear + capture + danger); danger = expected damage
        # taken as a fraction of max health, times the turns one retreat-and-return costs.
        # Inlined: each Python operation costs hundreds of fuel units.
        inv_dps = 1.0 / (max(1.0, me.strength()) * HELPER_FACTOR)
        danger_k = TRIP_TURNS / max(1.0, me.max_health())
        fixed = cambc.constants.CAPTURE_TIME + 1
        respawn = self.respawn_round
        get = field.get
        best, best_score, current_score = None, 0.0, 0.0
        for info in self.groups:
            dist = get(info.anchor)
            if dist >= UNREACHABLE:
                continue
            wait = respawn.get(info.key, 0) - now
            clear = info.hp * inv_dps
            s = info.value / ((wait if wait > dist else dist) + clear * (1.0 + info.dps * danger_k) + fixed)
            if s > best_score:
                best, best_score = info, s
            if info is target:
                current_score = s
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

    def foes(self, info):
        """Visible living camps of the group: (camp, position, strength, health, False),
        dangerous camps first, then lowest health, so kills reduce incoming damage soonest."""
        out = []
        for p in info.spawns:
            if not cambc.vision.has_camp(p):
                continue
            try:
                camp = cambc.vision.camp_at(p)
                if int(camp) not in info.handles:
                    continue
                hp = camp.health()
                if hp <= 0:
                    continue
                out.append((camp, p, camp.strength(), hp, False))
            except cambc.Error:
                continue
        out.sort(key=lambda f: (f[2] <= 0, f[3]))
        return out
