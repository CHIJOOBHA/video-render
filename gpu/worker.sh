#!/bin/bash
# Telugu voice job for a RENTED GPU machine (RunPod / Vast.ai). Started by gpu/voice.py; the machine gets only two
# 2-hour links: one to download this job's sentences + voice sample, one to upload the finished wavs. No keys.
# Env: PAYLOAD_URL RESULT_URL [ONLY TE_REF TE_FLOW]. On any error it uploads FAILED + the log, so voice.py stops waiting.
set -eo pipefail
J=/job; mkdir -p $J; LOG=$J/worker.log; exec > >(tee -a $LOG) 2>&1
fail() { echo "FAILED at line $1"; tail -c 4000 $LOG > $J/FAILED; tar -czf $J/r.tgz -C $J FAILED
         curl -sS --retry 4 -X PUT --upload-file $J/r.tgz "$RESULT_URL"; exit 1; }
trap 'fail $LINENO' ERR
(apt-get -qq update && apt-get -qq install -y git curl ffmpeg libsndfile1) >/dev/null 2>&1 || true
cd $J && curl -sSL --fail --retry 4 -o p.tgz "$PAYLOAD_URL" && tar -xzf p.tgz
pip install -q torchdiffeq x_transformers vocos ema_pytorch pydub jieba pypinyin cached_path soundfile librosa \
    safetensors accelerate datasets wandb pyyaml "numpy<=1.26.4" "transformers<4.50"
git clone -q --depth 1 https://github.com/AI4Bharat/IndicF5 /opt/IndicF5-src && pip install -q --no-deps -e /opt/IndicF5-src
M=/opt/indicf5; mkdir -p $M/checkpoints
for f in config.json checkpoints/vocab.txt model.safetensors; do
  curl -sSL --fail --retry 4 -o $M/$f https://huggingface.co/Aditya02/IndicF5/resolve/main/$f; done
sha256sum $M/model.safetensors | grep -q '^ba7f3671180fb778'      # same weights as Kaggle and the CPU machines
[ -z "$TE_REF" ] || export TE_REF=$J/$TE_REF
INDICF5_DIR=$M python tools/voice_te.py sentences.json $J/out
tar -czf r.tgz -C $J/out .
curl -sS --fail --retry 4 -X PUT --upload-file r.tgz "$RESULT_URL"
echo DONE
