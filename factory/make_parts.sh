#!/bin/bash
# One chapter through the factory: every part -> Gemini script + scene plan -> checks -> voice words -> source -> EN render
# now, TE render queued for the Kaggle GPU (te-queue.yml takes one at a time). Status per part in private storage
# jobs/factory/<subject>/<part>.md (READY / BLOCKED + coverage). Usage: make_parts.sh <subject> <chapter> <app_prefix> [only_ids]
set -u
SUBJ=$1; CH=$2; PFX=$3; ONLY=${4:-}
F=$GITHUB_WORKSPACE/factory; R2="python3 $GITHUB_WORKSPACE/r2.py"
mkdir -p parts out
python3 $F/split.py w/notes "$SUBJ" "$CH" parts | tee parts.txt
for J in $(ls parts/*.json | sort -V); do
  ID=$(basename $J .json); P=$(jq -r .part $J)
  if [ -n "$ONLY" ] && ! echo ",$ONLY," | grep -q ",$ID,"; then continue; fi
  echo "::group::$ID"
  python3 $F/gen_spec.py $J w out/$ID.json out/$ID.md; RC=$?
  $R2 put out/$ID.md "jobs/factory/$SUBJ/$ID.md"; [ -f out/$ID.json ] && $R2 put out/$ID.json "jobs/factory/$SUBJ/$ID.json"
  if [ $RC != 0 ]; then echo "::warning title=$ID::BLOCKED — $(sed -n 5,6p out/$ID.md | tr '\n' ' ')"; echo "::endgroup::"; continue; fi
  ( cd w && python3 tools/auto_lesson.py $ID ../out/$ID.json )
  [ -s out/$ID-lex.json ] && cp out/$ID-lex.json w/tools/lexicon/auto-$ID.json     # spellings Gemini gave with the plan
  C="$(echo ${ID:0:1} | tr a-z A-Z)${ID:1}"
  # English voice words: anything not ordinary English and not in the lists gets its Telugu spelling from the Telugu notes
  ( cd w && node tools/export_sentences.mjs src/lessons/auto/auto-$ID.ts auto${C}Spec en ../out/$ID-en.json >/dev/null )
  MISS=$(cd w && python3 -I tools/missing_terms.py ../out/$ID-en.json | sed 's/^missing: //; s/^none$//')
  if [ -n "$MISS" ]; then
    python3 $F/lex_fill.py $J "$MISS" out/$ID-lex2.json && jq -s 'add' w/tools/lexicon/auto-$ID.json out/$ID-lex2.json > l.json 2>/dev/null || cp out/$ID-lex2.json l.json
    mv l.json w/tools/lexicon/auto-$ID.json
    LEFT=$(cd w && python3 -I tools/missing_terms.py ../out/$ID-en.json | sed 's/^missing: //; s/^none$//')
    if [ -n "$LEFT" ]; then
      echo "- voice words with no spelling yet (blocking): $LEFT" >> out/$ID.md; $R2 put out/$ID.md "jobs/factory/$SUBJ/$ID.md"
      echo "::warning title=$ID::BLOCKED — new words: $LEFT"; echo "::endgroup::"; continue
    fi
  fi
  tar -czf out/$ID-src.tgz --exclude=node_modules --exclude=.git -C w .
  $R2 put out/$ID-src.tgz "work/factory/src/$ID.tgz"
  SECS=$(jq -r '[.sections[] | sub("^[0-9.]+ "; "")] | join(", ")' $J | cut -c1-150)
  for L in en te; do
    jq -nc --arg id "$PFX-$L-ch$CH-p$P" --arg ch "$PFX-$L-ch$CH" --arg lesson "src/lessons/auto/auto-$ID.ts" \
      --arg spec "auto${C}Spec" --arg comp "Auto${C}$(echo $L | tr a-z A-Z)" --arg lang $L --arg t "Ch $CH · Part $P · $SECS" --argjson p $P \
      '{video_id: $id, chapter_id: $ch, src: "work/factory/src/'$ID'.tgz", lesson: $lesson, spec: $spec, comp: $comp, lang: $lang,
        chunks: 16, part: $p, title: $t} + (if $lang == "te" then {te_shards: 16} else {} end)' > out/$ID-$L.req
  done
  if [ "${RENDER:-yes}" = "yes" ]; then
    gh api -X POST "repos/$GITHUB_REPOSITORY/actions/workflows/render.yml/dispatches" -f ref=main -f "inputs[req]=$(cat out/$ID-en.req)" && echo "EN render started: $PFX-en-ch$CH-p$P"
    $R2 put out/$ID-te.req "work/factory/te-queue/$(printf '%s-%02d-%02d' "$SUBJ" "$CH" "$P").json" && echo "TE queued"
  fi
  echo "::notice title=$ID::READY — EN render started, TE queued"
  echo "::endgroup::"
done
