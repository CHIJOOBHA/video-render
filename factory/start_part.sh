#!/bin/bash
# Start the renders of ONE factory part (4 Nov 2026): English at once; Telugu after its lines are written into the same scenes
# (te_fill.py). Used by part.yml (a chapter remade by hand, e.g. the Chapter 1 proof) — the queues are not touched.
# Usage: start_part.sh <subject> <part_id e.g. ce1p2> <src key work/factory/src/<part>-<run>.tgz> <app prefix> <en|te|both> [TE voice run to reuse]
set -eu
SUBJ=$1; PID=$2; SRC=$3; PFX=$4; WHICH=${5:-both}; TEREUSE=${6:-}
R2="python3 $GITHUB_WORKSPACE/r2.py"; F=$GITHUB_WORKSPACE/factory
CH=$(echo $PID | sed -E 's/^[a-z]+([0-9]+)p[0-9]+$/\1/'); P=$(echo $PID | sed -E 's/^.*p([0-9]+)$/\1/'); C2=$(printf %02d $CH)
mkdir -p w parts && $R2 get "$SRC" s.tgz && tar -xzf s.tgz -C w
python3 $F/split.py w/notes "$SUBJ" "$CH" parts --prefix "$PFX" > /dev/null
SECS=$(jq -r '[.sections[] | sub("^[0-9.]+[a-z]? "; "")] | join(", ")' parts/$PID.json | cut -c1-150)
C="$(echo ${PID:0:1} | tr a-z A-Z)${PID:1}"
req() {   # $1 lang, $2 src
  jq -nc --arg id "$PFX-$1-ch$C2-p$P" --arg ch "$PFX-$1-ch$C2" --arg lesson "src/lessons/auto/auto-$PID.ts" --arg spec "auto${C}Spec" \
    --arg comp "Auto${C}$(echo $1 | tr a-z A-Z)" --arg lang $1 --arg t "Ch $CH · Part $P · $SECS" --argjson p $P --arg src "$2" \
    '{video_id: $id, chapter_id: $ch, src: $src, lesson: $lesson, spec: $spec, comp: $comp, lang: $lang, chunks: 16, part: $p, title: $t}
     + (if $lang == "te" then {te_shards: 16} else {en_voice: "chijobha", te_shards: 16} end)'
}
go() { gh api -X POST "repos/$GITHUB_REPOSITORY/actions/workflows/render.yml/dispatches" -f ref=main -f "inputs[req]=$1" && echo "started $(echo "$1" | jq -r .video_id)"; }
if [ "$WHICH" != te ]; then go "$(req en "$SRC")"; fi
if [ "$WHICH" != en ]; then
  J=w/src/lessons/auto/$PID.json
  if [ "$(jq -r '.te_pending // false' $J)" = "true" ]; then
    $R2 get "jobs/factory/$SUBJ/$PID.md" rep.md 2>/dev/null || touch rep.md
    python3 $F/te_fill.py $J parts/$PID.json w rep.md || { $R2 put rep.md "jobs/factory/$SUBJ/$PID.md"; echo "::error::$PID Telugu lines not complete"; exit 1; }
    $R2 put rep.md "jobs/factory/$SUBJ/$PID.md"; $R2 put $J "jobs/factory/$SUBJ/$PID.json"
  fi
  TESRC="${SRC%.tgz}-te.tgz"
  tar -czf te.tgz --exclude=node_modules -C w . && $R2 put te.tgz "$TESRC"
  if [ -n "$TEREUSE" ]; then go "$(req te "$TESRC" | jq -c --arg r "$TEREUSE" '. + {reuse: $r}')"; else go "$(req te "$TESRC")"; fi
fi
