#!/usr/bin/env python3
"""Speak faster without changing the pitch (CHIJOBHA, 6 Nov 2026: "too slow" — marketing videos).
  python3 factory/tempo.py <voice_dir with <scene>_<i>.wav + durations.json> <factor, e.g. 1.15>
Every wav is time-compressed with ffmpeg atempo (pitch kept), then durations.json is rewritten. Run pace.py after it."""
import json, os, subprocess, sys
import soundfile as sf

d, k = sys.argv[1], float(sys.argv[2])
durs = json.load(open(f"{d}/durations.json"))
for sc, ds in durs.items():
    for i in range(len(ds)):
        f = f"{d}/{sc}_{i}.wav"; t = f[:-4] + ".t.wav"
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", f, "-filter:a", f"atempo={k}", t], check=True)
        os.replace(t, f)
        ds[i] = round(sf.info(f).duration, 3)
json.dump(durs, open(f"{d}/durations.json", "w"), indent=1)
print(f"tempo x{k}: {sum(map(len, durs.values()))} sentences")
