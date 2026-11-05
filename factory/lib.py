"""Teach once, reuse everywhere (4 Nov 2026). v2 (4 Nov, later): pieces written before the voice / screen / script fixes are
not reused (they live on under library/<kind>/ for reference only). The same notes text appears in several subjects (APPSC EO and Group 2 share
much of polity, economy, history, current affairs...). Every finished English piece and every Telugu scene is saved under a
fingerprint of its notes/English text in private storage jobs/factory/library/<kind>/<key>.json; the next time the SAME
text comes up — in any subject — it is reused with no AI call. Different text (even one word) is written fresh."""
import hashlib, json, os, re, subprocess, tempfile
R2 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "r2.py")

def key(text):
    t = re.sub(r"^(#+\s*)[\d.]+\s+", r"\1", text, flags=re.M)          # section numbers differ between books
    t = re.sub(r"[^a-z0-9ఀ-౿]+", " ", t.lower()).strip()
    return hashlib.sha1(t.encode()).hexdigest()[:24]

def get(kind, k):
    if os.environ.get("NO_LIBRARY"): return None
    f = tempfile.mktemp()
    r = subprocess.run(["python3", R2, "get", f"jobs/factory/library/v3/{kind}/{k}.json", f], capture_output=True)
    if r.returncode or not os.path.exists(f): return None
    try:
        o = json.load(open(f, encoding="utf-8"))
        # 5 Nov 2026 remakes: LIB_AFTER=<UTC time> reuses only pieces saved after it (written in the current style); older -> fresh
        if os.environ.get("LIB_AFTER") and str(o.get("_at") or "") < os.environ["LIB_AFTER"]: return None
        return o
    except Exception: return None
    finally:
        if os.path.exists(f): os.remove(f)

def put(kind, k, obj):
    import datetime
    obj = dict(obj, _at=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    f = tempfile.mktemp(suffix=".json")
    json.dump(obj, open(f, "w", encoding="utf-8"), ensure_ascii=False)
    subprocess.run(["python3", R2, "put", f, f"jobs/factory/library/v3/{kind}/{k}.json"], capture_output=True)
    os.remove(f)
