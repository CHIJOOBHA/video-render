#!/usr/bin/env python3
"""Roach Academia recording scripts, written by the API (CHIJOBHA, 8 Nov 2026: "complete all scripts of all subjects").
A worker claims the next chapter (EN + TE pair) from Supabase video_scripts (edge function video-scripts, GitHub OIDC),
cuts it into parts of ~4-7 min at section boundaries, makes the LEDGER of every point (factory/ledger.py), writes the
spoken script part by part, checks every ledger point is taught (repair up to 2 rounds) and saves the recording script
(numbered paragraphs + part headings) back to video_scripts. Contains NO course content; never prints notes text.
Usage (GitHub Actions only): python3 rscripts/write.py <worker-name> <stop-after-minutes>"""
import json, os, re, sys, time, threading, urllib.request
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "factory"))
import llm, ledger
from rules import RULES
EX = {}

FN = "https://xijkeywydoesxvqnacnc.supabase.co/functions/v1/video-scripts"

def oidc():
    u = os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"] + "&audience=video-admin"
    req = urllib.request.Request(u, headers={"Authorization": "bearer " + os.environ["ACTIONS_ID_TOKEN_REQUEST_TOKEN"]})
    return json.load(urllib.request.urlopen(req, timeout=60))["value"]

def api(action, body=None, **q):
    qs = "&".join(f"{k}={v}" for k, v in q.items())
    for n in range(5):
        try:
            req = urllib.request.Request(f"{FN}?action={action}" + (f"&{qs}" if qs else ""),
                                         data=None if body is None else json.dumps(body, ensure_ascii=False).encode(),
                                         headers={"x-gh-oidc": oidc(), "content-type": "application/json"},
                                         method="GET" if body is None else "POST")
            return json.load(urllib.request.urlopen(req, timeout=120))
        except Exception as e:
            print(f"  api {action}: {str(e)[:120]}", flush=True); time.sleep(10 * (n + 1))
    raise SystemExit(f"api {action} failed")

# ------------------------------------------------------------------ cutting a chapter into parts
MCQ = re.compile(r"\n#{1,3} (?:Practice MCQs|Practice Questions|Practice Quiz|MCQ|అభ్యాస|ప్రాక్టీస్|సాధన ప్రశ్నలు|మాదిరి ప్రశ్నలు)[^\n]*", re.I)
RECAP = re.compile(r"quick revision|summary|key takeaways|త్వరిత|పునశ్చరణ|రివిజన్|సారాంశం", re.I)

def units(md):
    md = MCQ.split("\n" + md)[0].strip()
    secs = re.split(r"\n(?=## )", "\n" + md)
    secs = [s.strip() for s in secs if s.strip()]
    out = []
    for s in secs:
        if wc(s) > 1100 and "\n### " in s:                       # a very long section: cut at its ### sub-headings
            sub = re.split(r"\n(?=### )", s)
            out += [x.strip() for x in sub if x.strip()]
        else: out.append(s)
    return out

def wc(s): return len(re.findall(r"\w+", s))

def group(us, target=560):
    """indices of units per part; Quick Revision stays with the last part unless it is long."""
    words = [wc(u) for u in us]; total = sum(words)
    n = max(1, round(total / target)); goal = total / n
    parts, cur, acc = [], [], 0
    for i, w in enumerate(words):
        if cur and acc >= goal * 0.5 and acc + w / 2 > goal and len(parts) < n - 1 and not (RECAP.search(us[i][:80]) and w < 250):
            parts.append(cur); cur, acc = [], 0
        cur.append(i); acc += w
    if cur: parts.append(cur)
    return parts

def regroup(us, k):
    """split units into exactly k parts of near-equal words (used when TE section count differs from EN)."""
    words = [wc(u) for u in us]; total = sum(words); goal = total / max(1, k)
    parts, cur, acc = [], [], 0
    for i, w in enumerate(words):
        if cur and acc >= goal * 0.5 and acc + w / 2 > goal and len(parts) < k - 1: parts.append(cur); cur, acc = [], 0
        cur.append(i); acc += w
    if cur: parts.append(cur)
    while len(parts) < k: parts.append([])
    return parts

# ------------------------------------------------------------------ writing one part
def heads(text):
    return [re.sub(r"[*_`]", "", h).strip() for h in re.findall(r"^#{2,3} (.+)$", text, re.M)]

def write_part(lang, title, k, n, notes, led, prev_last, next_hint, words_goal):
    if lang not in EX: EX[lang] = api("example", lang=lang).get("text", "")
    ex = EX[lang]
    pts = "\n".join(f"{p['n']}. {p['point']}" for p in led)
    where = (f"Chapter: {title}\nThis is part {k} of {n}.\n"
             + (f"The previous part ended with: {prev_last}\n" if prev_last else "This is the first part of the chapter.\n")
             + f"For the cliffhanger at the end, the next thing students will learn is: {next_hint}\n"
             + f"Aim for about {words_goal} spoken {'English words' if lang == 'en' else 'words (the same length as an English script of that many words)'}.\n")
    prompt = (RULES[lang] + "\n\n# STYLE EXAMPLE (from Chapter 1, already approved — copy the style, never the facts)\n" + ex
              + "\n\n# THIS PART\n" + where + "\n## LEDGER — every point below MUST be taught, in this order\n" + pts
              + "\n\n## NOTES OF THIS PART (the only source of facts)\n" + notes
              + '\n\nReturn ONLY JSON: {"paragraphs": [{"text": "…", "covers": [ledger numbers taught in it]}]}')
    ans = llm.ask(prompt, f"write {lang} p{k}", prefer=("anthropic",))
    return [p for p in (ans or {}).get("paragraphs") or [] if isinstance(p, dict) and str(p.get("text", "")).strip()]

def repair(lang, paras, miss, notes):
    txt = "\n".join(f"[{i + 1}] {p['text']}" for i, p in enumerate(paras))
    m = "\n".join(f"{p['n']}. {p['point']}" for p in miss)
    prompt = (RULES[lang] + "\n\n# THIS PART — REPAIR\nThe script below misses these ledger points (or states them differently from the notes). "
              "Teach each one, in the notes' order and wording for terms, by changing or adding paragraphs where it belongs. "
              "Keep everything else as it is. Return the WHOLE script.\n\n## MISSING POINTS\n" + m
              + "\n\n## SCRIPT\n" + txt + "\n\n## NOTES OF THIS PART\n" + notes
              + '\n\nReturn ONLY JSON: {"paragraphs": [{"text": "…", "covers": []}]}')
    ans = llm.ask(prompt, f"repair {lang}", prefer=("anthropic",))
    out = [p for p in (ans or {}).get("paragraphs") or [] if isinstance(p, dict) and str(p.get("text", "")).strip()]
    return out or paras

def plan_chapter(en_id, te_id):
    """part plan from the notes alone (no AI): EN fixes the parts, TE follows EN's cuts when its sections match."""
    d = {"en": api("notes", id=en_id)}
    if te_id: d["te"] = api("notes", id=te_id)
    us = {l: units(d[l]["notes"]) for l in d}
    g = {"en": group(us["en"])}
    if te_id: g["te"] = g["en"] if len(us["te"]) == len(us["en"]) else regroup(us["te"], len(g["en"]))
    return d, us, g

def one_part(lang, d, us, groups, k):
    g = groups[k - 1]; n = len(groups)
    notes = "\n\n".join(us[i] for i in g)
    if not notes.strip(): return None
    led = ledger.points(notes, lang)
    nxt = groups[k] if k < n else None
    hint = (heads("\n\n".join(us[i] for i in nxt))[:1] or ["the next topic"])[0] if nxt else \
           (f"the next chapter, {d['next_title']}" if d.get("next_title") else "the end of this subject")
    prev = heads("\n\n".join(us[i] for i in groups[k - 2])) if k > 1 else []
    prev_last = ("the previous part taught: " + "; ".join(prev[:4])) if prev else ""
    goal = max(550, min(1150, int(wc(notes) * (1.7 if lang == "en" else 1.25))))
    paras = write_part(lang, d["title"], k, n, notes, led, prev_last, hint, goal)
    miss = []
    for rnd in range(3):
        miss, _ = ledger.missing(led, [(f"p{i}", p["text"]) for i, p in enumerate(paras)], lang)
        if not miss or rnd == 2: break
        print(f"  {lang} p{k}: {len(miss)} points missing -> repair {rnd + 1}", flush=True)
        paras = repair(lang, paras, miss, notes)
    return {"part": k, "headings": heads(notes), "ledger": led, "paragraphs": paras,
            "missing": [{"part": k, "n": p["n"], "point": p["point"]} for p in miss]}

def speak_md(lang, title, parts):
    if lang == "en":
        out = [f"# {title} — English recording script", "Read the numbered paragraphs in order. Leave a short pause between paragraphs, and a longer pause at each part heading.", ""]
        ph = "Part"
    else:
        out = [f"# {title} — తెలుగు రికార్డింగ్ స్క్రిప్ట్", "నంబర్ వేసిన పేరాలను వరుసగా చదవండి. పేరాల మధ్య చిన్న విరామం, ప్రతి భాగం హెడింగ్ దగ్గర కొంచెం పెద్ద విరామం ఇవ్వండి.", ""]
        ph = "భాగం"
    n = 0
    for p in parts:
        out += [f"## {ph} {p['part']}", ""]
        for q in p["paragraphs"]:
            n += 1; out += [f"{n}. {q['text'].strip()}", ""]
    return "\n".join(out), n

def chapter(job):
    from concurrent.futures import ThreadPoolExecutor
    ids = sorted(job["ids"], key=lambda x: "-te-" in x)          # EN first
    os.environ["ANTHROPIC_MODEL"] = job.get("model") or "claude-haiku-5-5"
    en_id = ids[0]; te_id = ids[1] if len(ids) > 1 else None
    t0 = time.time()
    d, us, g = plan_chapter(en_id, te_id)
    tasks = [(l, k) for l in g for k in range(1, len(g[l]) + 1)]
    with ThreadPoolExecutor(max_workers=int(os.environ.get("PART_THREADS", "6"))) as ex:
        futs = {t: ex.submit(one_part, t[0], d[t[0]], us[t[0]], g[t[0]], t[1]) for t in tasks}
        res = {t: f.result() for t, f in futs.items()}
    for lang, rid in (("en", en_id), ("te", te_id)):
        if not rid: continue
        parts = [res[(lang, k)] for k in range(1, len(g[lang]) + 1) if res.get((lang, k))]
        md, paras = speak_md(lang, d[lang]["title"], parts)
        missing = [m for p in parts for m in p.pop("missing")]
        pts = sum(len(p["ledger"]) for p in parts)
        status = "ready" if not missing else "check"
        api("put", {"id": rid, "status": status, "speak_md": md, "parts": len(parts), "words": len(md.split()),
                    "parts_json": parts, "model": os.environ["ANTHROPIC_MODEL"],
                    "coverage": {"points": pts, "covered": pts - len(missing), "missing": missing},
                    "note": f"{paras} paragraphs, {time.time() - t0:.0f}s"})
        print(f"{rid}: {status} · {len(parts)} parts · {paras} paragraphs · points {pts} missing {len(missing)} · {time.time() - t0:.0f}s", flush=True)

def main():
    worker, stop = sys.argv[1], float(sys.argv[2]) * 60
    t0 = time.time(); done = 0
    while time.time() - t0 < stop:
        job = api("claim", {"worker": worker})
        if not job.get("pair_id"): print("queue empty", flush=True); break
        print(f"== {job['pair_id']} ({job.get('model')})", flush=True)
        try:
            chapter(job); done += 1
        except SystemExit as e:
            print(f"  {job['pair_id']} stopped: {e}", flush=True)
            for rid in job["ids"]: api("put", {"id": rid, "status": "pending", "note": f"retry: {str(e)[:150]}"})
            if llm.AN_DEAD: print("Anthropic key/credit not usable — stopping this worker", flush=True); break
        except Exception as e:
            print(f"  {job['pair_id']} error {type(e).__name__}: {str(e)[:200]}", flush=True)
            for rid in job["ids"]: api("put", {"id": rid, "status": "pending", "note": f"retry: {type(e).__name__}"})
        for line in llm.LOG[-6:]: print("   ", line[:200], flush=True)
        llm.LOG.clear()
    print(f"worker {worker}: {done} chapters in {(time.time() - t0) / 60:.0f} min", flush=True)

if __name__ == "__main__":
    main()
