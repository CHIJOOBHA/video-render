#!/usr/bin/env python3
"""Rewrite a lesson's narration with Gemini (free tier) using the teacher-script recipe.
in.json : {"recipe": str, "notes_en": str, "notes_te": str, "scenes": [{"id", "title", "beats": [[en, te], ...]}]}
out.json: {"model": str, "scenes": {scene_id: [[en, te], ...]}, "log": [...]}
Same number of beats per scene (the picture of beat i stays). Key: env GEMINI_API_KEY. No other dependencies."""
import json, os, re, sys, time, urllib.request, urllib.error

KEY = os.environ["GEMINI_API_KEY"]
API = "https://generativelanguage.googleapis.com/v1beta"
log = []

def http(url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 headers={"content-type": "application/json", "x-goog-api-key": KEY})
    return json.load(urllib.request.urlopen(req, timeout=600))

def models():
    names = [m["name"].split("/")[-1] for m in http(f"{API}/models?pageSize=200")["models"]
             if "generateContent" in m.get("supportedGenerationMethods", [])]
    pref = [r"^gemini-3[\d.]*-pro$", r"^gemini-3[\d.]*-pro-preview", r"^gemini-2\.5-pro$",
            r"^gemini-3[\d.]*-flash$", r"^gemini-3[\d.]*-flash-preview", r"^gemini-2\.5-flash$"]
    out = []
    for p in pref:
        out += [n for n in sorted(names, reverse=True) if re.search(p, n) and n not in out]
    return out or names

def ask(model, prompt):
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.4, "responseMimeType": "application/json"}}
    r = http(f"{API}/models/{model}:generateContent", body)
    return json.loads(r["candidates"][0]["content"]["parts"][0]["text"])

def check(group, out):
    errs = []
    for sc in group:
        new = out.get(sc["id"])
        if not isinstance(new, list) or len(new) != len(sc["beats"]):
            errs.append(f"scene {sc['id']}: need exactly {len(sc['beats'])} beats, got {len(new) if isinstance(new, list) else 'none'}")
            continue
        for i, b in enumerate(new):
            if not (isinstance(b, list) and len(b) == 2 and all(isinstance(x, str) and x.strip() for x in b)):
                errs.append(f"scene {sc['id']} beat {i}: must be [english, telugu]"); continue
            if re.search(r"\d", b[0] + b[1]):
                errs.append(f"scene {sc['id']} beat {i}: digits found — write numbers as spoken words")
            if re.search(r"(^|\s)(Q\s?\w+|See Chapter)\s*:", b[0]):
                errs.append(f"scene {sc['id']} beat {i}: colon list / 'Q nine:' style — use full spoken sentences")
    return errs

def main():
    inp = json.load(open(sys.argv[1], encoding="utf-8"))
    scenes = inp["scenes"]
    groups, cur, n = [], [], 0          # ~24 beats per request keeps the answer well inside the output limit
    for sc in scenes:
        if cur and n + len(sc["beats"]) > 24:
            groups.append(cur); cur, n = [], 0
        cur.append(sc); n += len(sc["beats"])
    if cur: groups.append(cur)
    order, result, prev = models(), {}, []
    log.append(f"models: {order[:4]}")
    for gi, g in enumerate(groups):
        base = (inp["recipe"] + "\n\n# ENGLISH NOTES (the only source of facts for English)\n" + inp["notes_en"] +
                "\n\n# TELUGU NOTES (the only source of facts and wording for Telugu)\n" + inp["notes_te"] +
                "\n\n# WHAT WAS JUST SAID (continue naturally from here)\n" + json.dumps(prev[-3:], ensure_ascii=False) +
                "\n\n# SCENES TO REWRITE NOW — old beats as [english, telugu]\n" +
                json.dumps([{"id": s["id"], "title": s.get("title"), "beats": s["beats"]} for s in g], ensure_ascii=False, indent=0) +
                "\n\nReturn ONLY JSON: {\"<scene id>\": [[\"english beat\", \"telugu beat\"], ...], ...} with exactly the same "
                "number of beats per scene, in order. Rewrite every beat by the recipe: complete flowing teacher sentences, "
                "every fact of the old beat kept, explained and connected; nothing added.")
        prompt, done = base, None
        for attempt in range(6):
            model = order[min(attempt // 2, len(order) - 1)]
            try:
                out = ask(model, prompt)
            except urllib.error.HTTPError as e:
                msg = e.read()[:300].decode("utf-8", "ignore")
                log.append(f"group {gi} {model}: HTTP {e.code} {msg}")
                time.sleep(30 if e.code == 429 else 5); continue
            except Exception as e:
                log.append(f"group {gi} {model}: {e}"); time.sleep(5); continue
            errs = check(g, out)
            if not errs:
                done = out; log.append(f"group {gi}: ok with {model} (attempt {attempt + 1})"); break
            log.append(f"group {gi} {model}: {len(errs)} problems, retrying: {errs[:3]}")
            prompt = base + "\n\nYour previous answer had these problems — fix them all:\n" + "\n".join(errs[:40])
        if not done:
            sys.exit("FAILED group %d\n%s" % (gi, "\n".join(log)))
        for s in g:
            result[s["id"]] = done[s["id"]]; prev += done[s["id"]]
        time.sleep(4)
    json.dump({"model": order[0], "scenes": result, "log": log}, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n".join(log))

if __name__ == "__main__":
    main()
