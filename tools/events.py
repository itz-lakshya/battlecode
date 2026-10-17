"""Per-match event breakdown for one team.

Usage: python3 tools/events.py MATCH.json teamA|teamB
"""
import collections
import json
import sys

d = json.load(open(sys.argv[1]))
team = sys.argv[2]
names = {c['id']: (c['team'], c['name']) for c in d['roster']['champions']}
by = collections.defaultdict(list)
for e in d['events']:
    owner = names.get(e['owner'].get('id'), ('?', '?'))
    if owner[0] != team:
        continue
    for x in e['entries']:
        by[e['kind']].append((owner[1], x))

print('captures by tile:', collections.Counter((x['x'], x['y']) for _, x in by['gemCollection']).most_common(12))
print('clears (group, x, y):', collections.Counter((x['target'].get('id'), x['x'], x['y']) for _, x in by['campClear']).most_common(12))
print('death causes:', collections.Counter(x['context'] for _, x in by['death']))
print('deaths (name, round, x, y):', [(n[:4], x['timestamp']['round'], x['x'], x['y']) for n, x in by['death']][:40])
print('tributes:', len(by['gemSubmission']), 'gems', sum(int(x['value']) for _, x in by['gemSubmission']))
for kind in ('botFault', 'fuelExhausted'):
    if by[kind]:
        print(kind, by[kind][:5])
