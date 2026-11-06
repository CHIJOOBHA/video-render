#!/usr/bin/env python3
"""Sample-G pauses for English in CHIJOBHA's own voice (approved 5 Nov 2026).
  python3 factory/pace.py <sentences.json (English)> <voice_dir with <scene>_<i>.wav + durations.json>
Each sentence stays spoken whole; only the silence after it changes, so the heard pause is:
  after a sentence inside a scene: 0.40 s after ".", 0.45 s after "?", 0.50 s after "!"
  between scenes (a new idea):     0.80 s
The video already adds 0.30 s between sentences and 0.53 s between scenes (Journal.tsx GAP / HOLD+LEAD), so the
tail of each wav is cut or padded to make up the rest (never below 0.10 s, so soft last syllables are kept).
Safe to run twice (the tail is measured from the last sound). Rewrites durations.json."""
import json, sys
import numpy as np
import soundfile as sf

PAUSE = {"!": 0.50, "?": 0.45, ".": 0.40}
IDEA_GAP, GAP, SCENE_GAP, MIN_TAIL, FPS = 0.80, 9 / 30, (10 + 6) / 30, 0.10, 30


def edges(w, sr, db=-45):
    thr = 10 ** (db / 20) * max(1e-9, float(np.abs(w).max()))
    idx = np.where(np.abs(w) > thr)[0]
    if not len(idx):
        return 0.0, len(w)
    return idx[0] / sr, idx[-1] + 1


def main():
    src, d = sys.argv[1], sys.argv[2]
    text = json.load(open(src, encoding="utf-8"))
    durs = json.load(open(f"{d}/durations.json"))
    scenes = list(durs)
    lead = {}
    for s in scenes:
        for i in range(len(durs[s])):
            w, sr = sf.read(f"{d}/{s}_{i}.wav", dtype="float32")
            lead[(s, i)] = edges(w if w.ndim == 1 else w.mean(1), sr)[0]
    out, heard = {}, []
    for k, s in enumerate(scenes):
        out[s] = []
        n = len(durs[s])
        for i in range(n):
            f = f"{d}/{s}_{i}.wav"
            w, sr = sf.read(f, dtype="float32")
            mono = w if w.ndim == 1 else w.mean(1)
            if i < n - 1:
                t = (text.get(s, [""] * n)[i] if i < len(text.get(s, [])) else "").strip().rstrip('"\'')
                want, gap, nxt = PAUSE.get(t[-1:] or ".", 0.40), GAP, lead[(s, i + 1)]
            elif k < len(scenes) - 1:
                want, gap, nxt = IDEA_GAP, SCENE_GAP, lead[(scenes[k + 1], 0)]
            else:
                out[s].append(round(len(w) / sr, 3)); continue          # last sentence of the video: leave as is
            # the beat is rounded up to whole frames: count that in
            _, end = edges(mono, sr)
            tail = max(MIN_TAIL, want - gap - nxt)
            for _ in range(2):
                total = end / sr + tail
                extra = (np.ceil(total * FPS) / FPS) - total
                tail = max(MIN_TAIL, want - gap - nxt - extra)
            keep = end + int(round(tail * sr))
            if keep <= len(w):
                w = w[:keep].copy()
                k_ = min(int(0.03 * sr), len(w) // 4)
                fade = np.linspace(1, 0, k_, dtype=np.float32)
                w[-k_:] = (w[-k_:].T * fade).T
            else:
                pad = np.zeros((keep - len(w),) + w.shape[1:], dtype=np.float32)
                w = np.concatenate([w, pad])
            sf.write(f, w, sr)
            L = len(w) / sr
            out[s].append(round(L, 3))
            heard.append((i == n - 1, np.ceil(L * FPS) / FPS - end / sr + gap + nxt))
    json.dump(out, open(f"{d}/durations.json", "w"), indent=1)
    a = [h for last, h in heard if not last]; b = [h for last, h in heard if last]
    print(f"paced {sum(map(len, out.values()))} sentences: inside scenes {np.median(a):.2f} s "
          f"({min(a):.2f}-{max(a):.2f}), between scenes {np.median(b) if b else 0:.2f} s")


if __name__ == "__main__":
    main()
