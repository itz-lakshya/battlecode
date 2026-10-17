#!/bin/zsh
# Run BOT vs OPP on every map in maps/, both sides, then print aggregate results.
# Usage: tools/suite.sh BOT OPP [OUTDIR] [JOBS]   (BOT and OPP are names under bots/)
set -e
W=${0:A:h:h}
BOT=$1; OPP=$2; OUT=${3:-/tmp/cambc_runs/$BOT-vs-$OPP}; JOBS=${4:-6}
mkdir -p $OUT
find $OUT -name '*.repl26a' -delete
find $OUT -name '*.json' -delete
: > $OUT/manifest.txt
for m in $W/maps/*.map26a; do
  n=${m:t:r}
  echo "$W/bots/$BOT $W/bots/$OPP $m $OUT/A_$n.repl26a --statistics $OUT/A_$n.json --json" >> $OUT/manifest.txt
  echo "$W/bots/$OPP $W/bots/$BOT $m $OUT/B_$n.repl26a --statistics $OUT/B_$n.json --json" >> $OUT/manifest.txt
done
cd $W
cambc run-batch $OUT/manifest.txt --jobs $JOBS --log-limit 0 --color never > $OUT/batch.log 2>&1 || { tail -5 $OUT/batch.log; exit 1; }
python3 -I $W/tools/agg.py $OUT $BOT
