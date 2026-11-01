#!/usr/bin/env python3
"""Per-sentence voice check for a FINISHED Journal video (Telugu or English). Content-free: everything comes from the
private project and the finished video. Each sentence is cut out of the video at its own start/end (the Journal timeline
rule: LEAD 6, GAP 9, HOLD 10, TAIL 30 frames; sentence lengths = ceil(dur*30)), transcribed alone (faster-whisper
large-v3-turbo) and scored against the script sentence with the same letter-match score as tools/qa_final.py.
Usage: python3 check_te.py <video.mp4> <sentences.json> <durations.json> <lang> <report.json>  -> exit 1 if any < 0.6"""
import json, math, re, subprocess, sys, difflib
import numpy as np
vid, sj, dj, lang, out = sys.argv[1:6]
S = json.load(open(sj, encoding='utf-8')); D = json.load(open(dj))
LEAD, GAP, HOLD, TAIL = 6, 9, 10, 30
t, spans = 0, []
for k, (sc, ss) in enumerate(S.items()):
    t += LEAD
    for i, s in enumerate(ss):
        n = math.ceil(D[sc][i] * 30); spans.append((f'{sc}_{i}', s, t / 30, (t + n) / 30)); t += n + GAP
    t += TAIL if k == len(S) - 1 else HOLD
def norm(x):
    x = re.sub(r"[^\w\sఀ-౿]", " ", x.lower()); return re.sub(r"\s+", "", x)
pcm = subprocess.run(['ffmpeg', '-v', 'error', '-i', vid, '-vn', '-ac', '1', '-ar', '16000', '-f', 's16le', '-'], capture_output=True, check=True).stdout
a = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768
from faster_whisper import WhisperModel
m = WhisperModel('large-v3-turbo', device='cpu', compute_type='int8')
res = {}
for key, s, b, e in spans:
    seg = a[max(0, int((b - 0.15) * 16000)): int((e + 0.25) * 16000)]
    n = max(1, int(np.ceil(len(seg) / (12 * 16000)))); step = int(np.ceil(len(seg) / n))
    h = ' '.join(x.text for k in range(n) for x in m.transcribe(seg[k * step:(k + 1) * step], language=lang, beam_size=5)[0])
    tt = norm(s); sm = difflib.SequenceMatcher(None, tt, norm(h), autojunk=False)
    res[key] = {'score': round(sum(bl.size for bl in sm.get_matching_blocks()) / max(1, len(tt)), 2), 'heard': h.strip()}
json.dump(res, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
v = [x['score'] for x in res.values()]
print(f"per-sentence: mean {np.mean(v):.2f} · {sum(1 for x in v if x >= 0.6)}/{len(v)} >= 0.6")
print("lowest: " + " ".join(f"{k}={x['score']}" for k, x in sorted(res.items(), key=lambda kv: kv[1]['score'])[:12]))
sys.exit(1 if min(v) < 0.6 else 0)
