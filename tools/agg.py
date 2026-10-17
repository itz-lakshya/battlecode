"""Aggregate a suite directory of statistics JSONs.

Usage: python3 tools/agg.py DIR BOTNAME
Files are named A_<map>.json (BOTNAME was team A) or B_<map>.json (team B).
"""
import collections
import glob
import json
import os
import sys

D, me = sys.argv[1], sys.argv[2]
rows = []
tot = collections.Counter()
for f in sorted(glob.glob(os.path.join(D, '*.json'))):
    tag = os.path.basename(f)[:-5]
    side, mapn = tag[0], tag[2:]
    d = json.load(open(f))
    mine = 'teamA' if side == 'A' else 'teamB'
    opp = 'teamB' if mine == 'teamA' else 'teamA'
    gems = {t['team']: int(t['submittedGems']) for t in d['teams']}
    champs = d['champions']
    names = {c['id']: c['team'] for c in d['roster']['champions']}

    def total(team, key):
        return sum(int(float(c['metrics'][key])) for c in champs if c['team'] == team)

    camp_deaths = sum(1 for e in d['events'] if e['kind'] == 'death'
                      and names.get(e['owner'].get('id')) == mine
                      for x in e['entries'] if x['context'] == 'camp')
    win = d['match']['outcome'] == mine
    draft = ','.join(c['name'][:4] for c in champs if c['team'] == mine)
    odraft = ','.join(c['name'][:4] for c in champs if c['team'] == opp)
    faults = d['diagnostics']['botFaults'][mine]
    rows.append((mapn, side, 'W' if win else 'L', gems[mine], gems[opp], d['match']['roundsStarted'],
                 total(mine, 'deaths'), camp_deaths, total(opp, 'deaths'), total(mine, 'kills'),
                 total(mine, 'collectedGems'), total(mine, 'earnedGold'), faults, draft, odraft))
    tot['games'] += 1
    tot['wins'] += win
    tot['gems'] += gems[mine]
    tot['ogems'] += gems[opp]
    tot['deaths'] += total(mine, 'deaths')
    tot['campdeaths'] += camp_deaths
    tot['odeaths'] += total(opp, 'deaths')
    tot['faults'] += faults

print('%-12s %s %s %5s %5s %5s %4s %4s %4s %3s %5s %5s %3s  %s | %s' % (
    'map', 'S', 'R', 'mine', 'opp', 'rnds', 'dth', 'cdth', 'odth', 'k', 'coll', 'gold', 'flt', 'draft', 'opp draft'))
for r in rows:
    print('%-12s %s %s %5d %5d %5d %4d %4d %4d %3d %5d %5d %3d  %s | %s' % r)
n = tot['games']
if n:
    print('games=%d wins=%d (%.0f%%) avg gems %.0f vs %.0f, avg deaths %.1f (camp %.1f) vs %.1f, faults %d' % (
        n, tot['wins'], 100 * tot['wins'] / n, tot['gems'] / n, tot['ogems'] / n,
        tot['deaths'] / n, tot['campdeaths'] / n, tot['odeaths'] / n, tot['faults']))
