#!/usr/bin/env python3
"""Telugu voice on a GPU — tries each GPU platform in turn until one finishes the whole video (5 Nov 2026).
  python3 gpu/voice.py <src_dir> <sentences.json> <out_dir> <video_id> <run_id>
Order comes from queue/gpu-order (default below). A platform is tried only if its secrets are saved in the repo:
  modal   MODAL_TOKEN_ID + MODAL_TOKEN_SECRET  free $30/month; one video split over up to 8 GPUs at once
  kaggle  KAGGLE_USERNAME + KAGGLE_KEY         free 30 h/week; one GPU
  runpod  RUNPOD_API_KEY                       paid per minute; one rented GPU, switched off as soon as it finishes
  vast    VAST_API_KEY                         paid per minute; cheapest rented GPU under $0.45/h, switched off after
Env from the request: ONLY (re-voice these lines), TE_REF (another voice clip inside the project), TE_FLOW.
Writes one or more te-*.tgz into <out_dir> and exits 0 only when every sentence has a wav; else exit 1 and the
workflow falls back to the 16 free GitHub CPU machines, exactly as before."""
import glob, io, json, math, os, shutil, subprocess, sys, tarfile, tempfile, time

src, sentences, out_dir, vid, run = sys.argv[1:6]
ONLY, TE_REF, TE_FLOW, TE_SPEED = (os.environ.get(k, "").strip() for k in ("ONLY", "TE_REF", "TE_FLOW", "TE_SPEED"))
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
T0 = time.time()
BUDGET = 75 * 60           # stop trying further platforms after this; the CPU machines then take over

total = sum(len(v) for v in json.load(open(sentences, encoding="utf-8")).values())
WANT = len([x for x in ONLY.split(",") if x]) if ONLY else total


def wavs(files):
    n = 0
    for f in files:
        with tarfile.open(f) as t:
            n += sum(1 for m in t.getmembers() if m.name.endswith(".wav"))
    return n


def sh(*a, timeout=None, env=None):
    return subprocess.run(a, check=True, timeout=timeout, env=env)


def r2(*a):
    return subprocess.run(["python3", f"{ROOT}/r2.py", *a], check=True, capture_output=True, text=True).stdout.strip()


def payload():
    p = os.path.join(tempfile.mkdtemp(), "payload.tgz")
    with tarfile.open(p, "w:gz") as t:
        t.add(sentences, "sentences.json")
        t.add(f"{src}/tools/voice_te.py", "tools/voice_te.py")
        d = os.path.dirname(TE_REF) if TE_REF else "voices/te-chijobha"   # only the clip in use (+ its ref.txt)
        for x in ("ref.wav", "ref.txt"): t.add(f"{src}/{d}/{x}", f"{d}/{x}")
    return p


def have(*keys):
    return all(os.environ.get(k, "").strip() for k in keys)


# ---------- free ----------
def modal_run(p):
    sh("pip", "install", "-q", "modal")
    pieces = max(1, min(8, math.ceil(WANT / 30)))   # about 30 sentences per GPU
    a = ["modal", "run", f"{HERE}/modal_voice.py", "--payload", p, "--shards", str(pieces), "--out-dir", out_dir]
    for k, v in (("--only", ONLY), ("--te-ref", TE_REF), ("--te-flow", TE_FLOW)):
        if v: a += [k, v]
    sh(*a, timeout=40 * 60)
    return glob.glob(f"{out_dir}/te-modal-*.tgz")


def kaggle_run(p):
    sh("pip", "install", "-q", "kaggle")
    env = dict(os.environ)
    if env["KAGGLE_KEY"].startswith("KGAT_"): env["KAGGLE_API_TOKEN"] = env["KAGGLE_KEY"]
    f = f"{out_dir}/te-gpu.tgz"
    sh("python3", f"{ROOT}/kaggle_voice.py", src, sentences, f, f"te-voice-{vid}", timeout=55 * 60, env=env)
    return [f]


# ---------- paid rented machines: same job, started with two short-lived links, always switched off ----------
def rented(p, name, start, stop):
    base = f"work/{vid}/{run}/gpu"
    r2("put", p, f"{base}/payload.tgz")
    res = f"{base}/{name}-result.tgz"
    env = {"PAYLOAD_URL": r2("url", "GET", f"{base}/payload.tgz"), "RESULT_URL": r2("url", "PUT", res),
           "ONLY": ONLY, "TE_REF": TE_REF, "TE_FLOW": TE_FLOW, "TE_SPEED": TE_SPEED}
    job = os.path.join(tempfile.mkdtemp(), "job.sh")       # the job (with its two links) goes up as a file, so the
    open(job, "w").write("#!/bin/bash\n" + "".join(f"export {k}='{v}'\n" for k, v in env.items())  # machine's start
                         + open(f"{HERE}/worker.sh").read())                                     # command stays short
    r2("put", job, f"{base}/job.sh")
    mid = start(r2("url", "GET", f"{base}/job.sh"))
    print(f"{name}: machine {mid} started", flush=True)
    try:
        t = time.time()
        while time.time() - t < 40 * 60:
            time.sleep(30)
            if res in r2("list", f"{base}/"):
                break
            print(f"{name}: working {int(time.time() - t)}s", flush=True)
        else:
            raise RuntimeError("no result in 40 min")
    finally:
        stop(mid)
        print(f"{name}: machine {mid} switched off", flush=True)
    f = f"{out_dir}/te-{name}.tgz"
    r2("get", res, f)
    with tarfile.open(f) as tf:
        if "FAILED" in tf.getnames():
            raise RuntimeError(tf.extractfile("FAILED").read().decode(errors="replace")[-1500:])
    return [f]


IMG = "pytorch/pytorch:2.4.1-cuda12.1-cudnn9-runtime"


def runpod_run(p):
    lib_dir = os.path.join(tempfile.gettempdir(), "gpu-pylib")   # installed beside us, so this Python sees it
    sh(sys.executable, "-m", "pip", "install", "-q", "--target", lib_dir, "runpod")
    sys.path.insert(0, lib_dir)
    import runpod
    runpod.api_key = os.environ["RUNPOD_API_KEY"].strip()

    def start(url):
        cmd = f"bash -c 'curl -sSL --retry 4 -o /job.sh \"{url}\"; bash /job.sh; sleep infinity'"
        last = None
        for gpu in ("NVIDIA GeForce RTX 3090", "NVIDIA RTX A4000", "NVIDIA RTX A5000", "NVIDIA GeForce RTX 4090"):
            for cloud in ("COMMUNITY", "SECURE"):
                try:
                    return runpod.create_pod(f"te-voice-{vid}"[:60], IMG, gpu, cloud_type=cloud, start_ssh=False,
                                             container_disk_in_gb=30, docker_args=cmd)["id"]
                except Exception as e:
                    last = e
        raise RuntimeError(f"no RunPod GPU available: {last}")

    return rented(p, "runpod", start, lambda i: runpod.terminate_pod(i))


def vast_run(p):
    sh("pip", "install", "-q", "vastai")
    key = ["--api-key", os.environ["VAST_API_KEY"].strip()]

    def vast(*a):
        return subprocess.run(["vastai", *a, *key], check=True, capture_output=True, text=True).stdout

    def start(url):
        offers = json.loads(vast("search", "offers", "num_gpus=1 gpu_ram>=12 reliability>0.97 inet_down>100 "
                                 "cuda_vers>=12.1 dph<=0.45 rentable=true verified=true", "-o", "dph", "--raw"))
        cmd = f"curl -sSL --retry 4 -o /root/job.sh '{url}'; nohup bash /root/job.sh > /root/job.log 2>&1 &"
        for o in offers[:5]:
            try:
                r = json.loads(vast("create", "instance", str(o["id"]), "--image", IMG, "--disk", "30", "--ssh",
                                    "--direct", "--cancel-unavail", "--onstart-cmd", cmd, "--raw"))
                if r.get("new_contract"):
                    return r["new_contract"]
            except Exception as e:
                print(f"vast offer {o['id']}: {e}", flush=True)
        raise RuntimeError("no Vast.ai GPU under $0.45/h available")

    return rented(p, "vast", start, lambda i: vast("destroy", "instance", str(i)))


PLATFORMS = {"modal": (("MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET"), modal_run),
             "kaggle": (("KAGGLE_USERNAME", "KAGGLE_KEY"), kaggle_run),
             "runpod": (("RUNPOD_API_KEY",), runpod_run),
             "vast": (("VAST_API_KEY",), vast_run)}

order_f = f"{ROOT}/queue/gpu-order"
order = open(order_f).read().split() if os.path.exists(order_f) else ["modal", "kaggle", "runpod", "vast"]
if os.environ.get("GPU_ORDER", "").strip():   # 6 Nov 2026: a request can limit the platforms (e.g. "kaggle" = free only)
    order = os.environ["GPU_ORDER"].split()
os.makedirs(out_dir, exist_ok=True)
p = payload()
for name in order:
    if name not in PLATFORMS: continue
    keys, fn = PLATFORMS[name]
    if not have(*keys):
        print(f"{name}: no secrets saved - skipped"); continue
    if time.time() - T0 > BUDGET:
        print("time budget used - leaving the rest to the CPU machines"); break
    shutil.rmtree(out_dir); os.makedirs(out_dir)
    try:
        files = fn(p)
        got = wavs(files)
        if got < WANT:
            raise RuntimeError(f"made {got} of {WANT} sentences")
        print(f"GPU voice ok on {name}: {got} sentences in {int(time.time() - T0)}s")
        sys.exit(0)
    except Exception as e:
        print(f"::warning::{name} did not finish: {str(e)[-600:]}", flush=True)
sys.exit("no GPU platform finished - using the CPU machines")
