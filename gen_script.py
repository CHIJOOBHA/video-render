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
    names = [n for n in names if not re.search(r"customtools|image|tts|live|audio|embedding|lite", n)]
    # free tier (4 Nov 2026): Pro models answer 429 "quota" on a free key, so Flash first; Pro kept as a last try
    pref = [r"^gemini-[\d.]+-flash$", r"^gemini-[\d.]+-flash-preview", r"^gemini-2\.5-flash$", r"^gemini-[\d.]+-pro"]
    out = []
    for p in pref:
        out += [n for n in sorted(names, reverse=True) if re.search(p, n) and n not in out]
    return out or names

def ask(model, prompt):
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.4, "responseMimeType": "application/json"}}
    r = http(f"{API}/models/{model}:generateContent", body)
    return json.loads(r["candidates"][0]["content"]["parts"][0]["text"])


EN_NUM = re.compile(r"\b(eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|lakh|crore|million|billion|per cent)", re.I)   # years and big numbers; small words like "one", "first" are ordinary speech
TE_NUM = re.compile(r"(పదకొండ|పన్నెండ|పదమూడ|పద్నాలుగ|పదిహేన|పదహార|పదిహేడ|పద్దెనిమిద|పంతొమ్మిద|ఇరవ|ముప్ప|నలభ|యాభ|అరవ|డెబ్బ|ఎనభ|తొంభ|వంద|వేల|లక్ష|కోట|శాత)")   # stems: ordinals and case endings change the last letter
STOP = set("A An And As At But By For From He His I If In It Its Let Now Of On Or So She That The Their Then There These This Those To We What When Which Who Why With You Your First Next Finally Also Our".split())
def names(t):
    return {w.strip(".,;:!?'\"()") for w in re.findall(r"(?<![.!?]\s)(?<!^)\b[A-Z][\w'-]+", t)} - STOP
def bag(rx, t):
    from collections import Counter
    return Counter(m.lower() for m in rx.findall(t))
BANNED = re.compile(r"\b(Furthermore|Moreover|Additionally|Specifically|Ultimately|In conclusion|synonymous|great distinction|legendary|renowned|iconic)\b", re.I)

def beat_errs(ob, b):
    if not (isinstance(b, list) and len(b) == 2 and all(isinstance(x, str) and x.strip() for x in b)):
        return ["must be [english, telugu]"]
    e = []
    if re.search(r"\d", b[0] + b[1]): e.append("digits found — write numbers as spoken words")
    lost = {w for w in names(ob[0]) if re.sub(r"'s$", "", w).lower() not in b[0].lower()}
    if lost: e.append(f"English dropped {sorted(lost)} — keep every name and term")
    for rx, k, nm in ((EN_NUM, 0, "English"), (TE_NUM, 1, "Telugu")):
        miss = bag(rx, ob[k]) - bag(rx, b[k])
        if miss: e.append(f"{nm} dropped number words {dict(miss)} — keep every number and date")
    m = BANNED.search(b[0])
    if m: e.append(f"essay word or added praise '{m.group(0)}' — speak like a teacher, add nothing")
    if re.search(r"(^|\s)(Q\s?\w+|See Chapter)\s*:", b[0]): e.append("colon list / 'Q nine:' style — use full spoken sentences")
    return e

def check(group, out):
    if not isinstance(out, dict):
        return ['answer must be ONE JSON object keyed by scene id: {"<scene id>": [[english, telugu], ...]}']
    errs = []
    for sc in group:
        new = out.get(sc["id"])
        if not isinstance(new, list) or len(new) != len(sc["beats"]):
            errs.append(f"scene {sc['id']}: need exactly {len(sc['beats'])} beats"); continue
        errs += [f"scene {sc['id']} beat {i}: {x}" for i, b in enumerate(new) for x in beat_errs(sc["beats"][i], b)]
    return errs

def call(order, prompt, tag):
    """Ask the first model that has free quota and is not busy. Returns parsed JSON or None."""
    for _ in range(14):
        if not order: return None
        model = order[0]
        try:
            return ask(model, prompt)
        except urllib.error.HTTPError as e:
            msg = e.read()[:400].decode("utf-8", "ignore")
            log.append(f"{tag} {model}: HTTP {e.code} {msg[:120]}")
            if e.code == 404 or (e.code == 429 and ("limit: 0" in msg or "PerDay" in msg)): order.pop(0)
            elif e.code >= 500: order.append(order.pop(0)); time.sleep(10)
            else: time.sleep(40)
        except Exception as e:
            log.append(f"{tag} {model}: {e}"); time.sleep(5)
    return None

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
        final = {sc["id"]: [None] * len(sc["beats"]) for sc in g}
        def take(out):
            if not isinstance(out, dict): return
            for sc in g:
                new = out.get(sc["id"])
                if isinstance(new, dict): new = [new.get(str(k)) for k in range(len(sc["beats"]))]
                if not isinstance(new, list) or len(new) != len(sc["beats"]): continue
                for k, b in enumerate(new):
                    if final[sc["id"]][k] is None and b is not None and not beat_errs(sc["beats"][k], b):
                        final[sc["id"]][k] = b
        take(call(order, base, f"group {gi}"))
        for rnd in range(5):                              # repair only the beats that failed, keep the good ones
            bad = [(sc, k) for sc in g for k in range(len(sc["beats"])) if final[sc["id"]][k] is None]
            if not bad: break
            log.append(f"group {gi} round {rnd + 1}: repairing {len(bad)} beats")
            ask_ = [{"scene": sc["id"], "beat": k, "old": sc["beats"][k],
                     "before": final[sc["id"]][k - 1] if k else None,
                     "rule": "keep every name, term, year and number of 'old'; complete teacher sentences; add nothing"} for sc, k in bad]
            out = call(order, base + "\n\n# ONLY THESE BEATS ARE NEEDED NOW\n" + json.dumps(ask_, ensure_ascii=False) +
                       '\n\nReturn ONLY JSON: {"<scene id>": {"<beat number>": ["english", "telugu"]}, ...}', f"group {gi} repair")
            if isinstance(out, dict):
                for sc, k in bad:
                    b = (out.get(sc["id"]) or {}).get(str(k)) if isinstance(out.get(sc["id"]), dict) else None
                    if b is not None and not beat_errs(sc["beats"][k], b): final[sc["id"]][k] = b
        for sc in g:                                      # never lose a fact: a beat that still fails keeps its old words
            for k in range(len(sc["beats"])):
                if final[sc["id"]][k] is None:
                    final[sc["id"]][k] = sc["beats"][k]; log.append(f"group {gi}: {sc['id']} beat {k} kept old words")
        aud = call(order, inp["recipe"] + "\n\n# ENGLISH NOTES\n" + inp["notes_en"] + "\n\n# TELUGU NOTES\n" + inp["notes_te"] +
                   "\n\n# OLD BEATS\n" + json.dumps({x["id"]: x["beats"] for x in g}, ensure_ascii=False) +
                   "\n\n# NEW BEATS\n" + json.dumps(final, ensure_ascii=False) +
                   "\n\nYou are a strict exam-notes editor. Compare each NEW beat with its OLD beat and the notes. Fix every fact "
                   "dropped, changed or added (including praise or claims the notes do not make) and any line that does not sound "
                   "like a teacher speaking. Same shape and beat counts. Return ONLY the corrected NEW BEATS JSON.", f"group {gi} audit")
        fixed = 0
        if isinstance(aud, dict):
            for sc in g:
                new = aud.get(sc["id"])
                if isinstance(new, list) and len(new) == len(sc["beats"]):
                    for k, b in enumerate(new):
                        if b != final[sc["id"]][k] and not beat_errs(sc["beats"][k], b): final[sc["id"]][k] = b; fixed += 1
        log.append(f"group {gi}: done; audit changed {fixed} beats")
        for s_ in g:
            result[s_["id"]] = final[s_["id"]]; prev += final[s_["id"]]
        time.sleep(4)
    json.dump({"model": order[0], "scenes": result, "log": log}, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n".join(log))

if __name__ == "__main__":
    main()
