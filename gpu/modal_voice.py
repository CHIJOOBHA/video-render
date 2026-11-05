"""Telugu voice on Modal (free $30 of GPU time every month). Started by gpu/voice.py:
  modal run gpu/modal_voice.py --payload p.tgz --shards 6 --out-dir out [--only a,b] [--te-ref x] [--te-flow y]
One video is split into <shards> pieces that run on separate T4 GPUs AT THE SAME TIME, so a chapter takes about as long
as its longest piece. The model + weights are built into the machine image once and reused by every later run.
Needs env MODAL_TOKEN_ID + MODAL_TOKEN_SECRET (repo secrets; never printed)."""
import io, os, subprocess, tarfile
import modal

W = "https://huggingface.co/Aditya02/IndicF5/resolve/main"
image = (
    modal.Image.debian_slim(python_version="3.10")
    .apt_install("git", "curl", "ffmpeg", "libsndfile1")
    .pip_install("torch==2.4.1", "torchaudio==2.4.1")
    .pip_install("torchdiffeq", "x_transformers", "vocos", "ema_pytorch", "pydub", "jieba", "pypinyin", "cached_path",
                 "soundfile", "librosa", "safetensors", "accelerate", "datasets", "wandb", "pyyaml", "matplotlib", "tqdm",
                 "hydra-core", "pyarrow<17",
                 "numpy<=1.26.4", "transformers<4.50")
    .run_commands(
        "git clone -q --depth 1 https://github.com/AI4Bharat/IndicF5 /opt/IndicF5-src && pip install -q --no-deps -e /opt/IndicF5-src",
        "mkdir -p /opt/indicf5/checkpoints && cd /opt/indicf5 && "
        + " && ".join(f"curl -sSL --fail --retry 4 -o {f} {W}/{f}" for f in ("config.json", "checkpoints/vocab.txt", "model.safetensors")),
        "sha256sum /opt/indicf5/model.safetensors | grep -q '^ba7f3671180fb778'",   # same weights as Kaggle and CPU
    )
)
app = modal.App("roach-te-voice", image=image)


@app.function(gpu="T4", timeout=3000, retries=1, max_containers=10)
def voice(payload: bytes, shard: str, only: str, te_ref: str, te_flow: str) -> bytes:
    job = "/tmp/job"
    os.makedirs(job, exist_ok=True)
    tarfile.open(fileobj=io.BytesIO(payload), mode="r:gz").extractall(job)
    env = dict(os.environ, INDICF5_DIR="/opt/indicf5", SHARD=shard)
    if only: env["ONLY"] = only
    if te_ref: env["TE_REF"] = f"{job}/{te_ref}"
    if te_flow: env["TE_FLOW"] = te_flow
    subprocess.run(["python", "tools/voice_te.py", "sentences.json", "/tmp/out"], cwd=job, env=env, check=True)
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        t.add("/tmp/out", ".")
    return buf.getvalue()


@app.local_entrypoint()
def main(payload: str, shards: int, out_dir: str, only: str = "", te_ref: str = "", te_flow: str = ""):
    data = open(payload, "rb").read()
    os.makedirs(out_dir, exist_ok=True)
    args = [(data, f"{i}/{shards}", only, te_ref, te_flow) for i in range(shards)]
    for i, out in enumerate(voice.starmap(args)):
        open(f"{out_dir}/te-modal-{i}.tgz", "wb").write(out)
        print(f"modal piece {i + 1}/{shards} done", flush=True)
