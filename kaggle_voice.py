#!/usr/bin/env python3
"""Telugu voice on a free Kaggle GPU (~50x faster than CPU). Called by render.yml job `tegpu`.
  python3 kaggle_voice.py <src_dir> <sentences.json> <out.tgz> <slug>
Packs the sentences + CHIJOBHA's voice sample + tools/voice_te.py into a private Kaggle script (GPU + internet on),
runs it, waits, downloads te.tgz and checks every sentence has a wav. Any problem -> exit 1, and the workflow falls back
to the 16 GitHub CPU machines. Needs env KAGGLE_USERNAME + KAGGLE_KEY (repo secrets; never printed)."""
import base64, io, json, os, subprocess, sys, tarfile, tempfile, time

src, sentences, out_tgz, slug = sys.argv[1:5]
user = os.environ["KAGGLE_USERNAME"].strip()

buf = io.BytesIO()
with tarfile.open(fileobj=buf, mode="w:gz") as t:
    t.add(sentences, "sentences.json")
    t.add(f"{src}/tools/voice_te.py", "tools/voice_te.py")
    # only the ONE voice clip this video uses (5 Nov 2026: packing his Telugu clips + his English clip made the job too
    # big for Kaggle -> "SaveKernel 400 Bad Request"); old-hook-7s is never packed
    ref = os.environ.get("TE_REF", "").strip()
    if ref:
        d = os.path.dirname(ref); t.add(f"{src}/{d}/ref.wav", f"{d}/ref.wav"); t.add(f"{src}/{d}/ref.txt", f"{d}/ref.txt")
    else:
        for x in ("ref.wav", "ref.txt"): t.add(f"{src}/voices/te-chijobha/{x}", f"voices/te-chijobha/{x}")
payload = base64.b64encode(buf.getvalue()).decode()
import shlex   # ONLY (re-voice lines), TE_REF (voice clip inside the job), TE_FLOW passed to the voice on Kaggle
ENVS = " ".join(f"{k}={shlex.quote(('/tmp/job/' + v) if k == 'TE_REF' else v)}"
                for k, v in ((k, os.environ.get(k, "").strip()) for k in ("ONLY", "TE_REF", "TE_FLOW")) if v)

kernel = r'''
import base64, io, os, subprocess, tarfile, hashlib
def sh(c):
    print(">>", c[:120], flush=True); subprocess.run(c, shell=True, check=True)
W = "/tmp/job"; os.makedirs(W, exist_ok=True)
tarfile.open(fileobj=io.BytesIO(base64.b64decode(PAYLOAD)), mode="r:gz").extractall(W)
sh("pip install -q torchdiffeq x_transformers vocos ema_pytorch pydub jieba pypinyin cached_path soundfile librosa safetensors accelerate datasets wandb pyyaml")
sh("git clone -q --depth 1 https://github.com/AI4Bharat/IndicF5 /tmp/IndicF5-src && pip install -q --no-deps -e /tmp/IndicF5-src")
M = "/tmp/indicf5"; os.makedirs(M + "/checkpoints", exist_ok=True)
for f in ("config.json", "checkpoints/vocab.txt", "model.safetensors"):
    sh(f"curl -sSL --retry 4 -o {M}/{f} https://huggingface.co/Aditya02/IndicF5/resolve/main/{f}")
h = hashlib.sha256(open(M + "/model.safetensors", "rb").read()).hexdigest()
assert h.startswith("ba7f3671180fb778"), "weights fingerprint mismatch"
sh(f"cd {W} && ENVS_HERE INDICF5_DIR={M} python tools/voice_te.py sentences.json /tmp/te-out")
sh("tar -czf /kaggle/working/te.tgz -C /tmp/te-out .")
print("DONE", flush=True)
'''.replace("PAYLOAD", repr(payload)).replace("ENVS_HERE", ENVS)

d = tempfile.mkdtemp()
open(f"{d}/te_voice.py", "w").write(kernel)
json.dump({"id": f"{user}/{slug}", "title": slug, "code_file": "te_voice.py", "language": "python",
           "kernel_type": "script", "is_private": True, "enable_gpu": True, "enable_internet": True,
           "dataset_sources": [], "competition_sources": [], "kernel_sources": []}, open(f"{d}/kernel-metadata.json", "w"))

def k(*a, check=True):
    r = subprocess.run(["kaggle", *a], capture_output=True, text=True)
    if check and r.returncode:
        sys.exit(f"kaggle {a[0]} {a[1]} failed: {(r.stderr or r.stdout)[-300:]}")
    return r.stdout

print(k("kernels", "push", "-p", d).strip()[-200:])
t0 = time.time()
while True:
    time.sleep(30)
    st = k("kernels", "status", f"{user}/{slug}", check=False).lower()
    print(f"{int(time.time() - t0)}s {st.strip()[-80:]}", flush=True)
    if "complete" in st:
        break
    if "error" in st or "cancel" in st or time.time() - t0 > 3000:
        sys.exit("kaggle run did not finish")
o = tempfile.mkdtemp()
k("kernels", "output", f"{user}/{slug}", "-p", o)
if not os.path.exists(f"{o}/te.tgz"):
    sys.exit("no te.tgz in kaggle output")
with tarfile.open(f"{o}/te.tgz") as t:
    got = {m.name.lstrip("./") for m in t.getmembers() if m.name.endswith(".wav")}
want = sum(len(v) for v in json.load(open(sentences, encoding="utf-8")).values())
if os.environ.get("ONLY", "").strip(): want = len([x for x in os.environ["ONLY"].split(",") if x.strip()])
if len(got) < want:
    sys.exit(f"kaggle made {len(got)} of {want} sentences")
os.replace(f"{o}/te.tgz", out_tgz)
print(f"kaggle voice ok: {len(got)} sentences in {int(time.time() - t0)}s")
