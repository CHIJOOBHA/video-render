#!/usr/bin/env python3
"""Gemini writes ONE video part (script + scene plan) from the notes; code checks it; failed checks go back to Gemini.
Usage: python3 gen_spec.py <part.json> <studio_dir> <out_spec.json> <out_report.md>
part.json: {"id","chapter","part","parts","chapter_title","sections":[...],"next":str|null,"en":md,"te":md,"source":[en,te]}
Rules come from the studio repo (CLAUDE.md locked rules, guides/teacher-script.md, guides/explain-style.md) + menu.md.
Key: env GEMINI_API_KEY. Nothing here contains course content (the public repo stays content-free)."""
import json, os, re, sys, time, urllib.request, urllib.error
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
KEY = os.environ["GEMINI_API_KEY"]
API = "https://generativelanguage.googleapis.com/v1beta"
LOG = []
class _Log(list):
    def append(self, x):
        print("  ·", x, flush=True); super().append(x)
LOG = _Log()

# ---------------------------------------------------------------- Gemini
def http(url, body=None, timeout=900):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None,
                                 headers={"content-type": "application/json", "x-goog-api-key": KEY})
    return json.load(urllib.request.urlopen(req, timeout=timeout))

def models():
    names = [m["name"].split("/")[-1] for m in http(f"{API}/models?pageSize=200")["models"]
             if "generateContent" in m.get("supportedGenerationMethods", [])]
    names = [n for n in names if not re.search(r"customtools|image|tts|live|audio|embedding|lite|robotics|computer", n)]
    pref = [r"^gemini-[\d.]+-flash$", r"^gemini-[\d.]+-flash-preview", r"^gemini-2\.5-flash$", r"^gemini-[\d.]+-pro"]
    out = []
    for p in pref:
        out += [n for n in sorted(names, reverse=True) if re.search(p, n) and n not in out]
    return out or names

ORDER = []
def ask(prompt, tag):
    """One JSON answer from the first model with free quota. Waits out per-minute limits; drops models out of daily quota."""
    global ORDER
    if not ORDER: ORDER = models(); LOG.append(f"models: {ORDER[:4]}")
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.5, "responseMimeType": "application/json", "maxOutputTokens": 65536}}
    for n in range(20):
        if not ORDER: raise SystemExit("no Gemini model has free quota left today")
        m = ORDER[0]; t0 = time.time()
        try:
            r = http(f"{API}/models/{m}:generateContent", body)
            txt = "".join(p.get("text", "") for p in r["candidates"][0]["content"]["parts"])
            LOG.append(f"{tag}: {m} {time.time() - t0:.0f}s")
            return json.loads(txt)
        except urllib.error.HTTPError as e:
            msg = e.read()[:500].decode("utf-8", "ignore")
            LOG.append(f"{tag}: {m} HTTP {e.code} {msg[:140]}")
            if e.code == 404 or (e.code == 429 and ("limit: 0" in msg or "PerDay" in msg)): ORDER.pop(0)
            elif e.code == 429:
                w = re.search(r'retryDelay"?:\s*"?(\d+)', msg); time.sleep(int(w.group(1)) + 2 if w else 30)
            elif e.code >= 500: time.sleep(10 + 5 * n)
            else: ORDER.pop(0)
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            fin = (r.get("candidates") or [{}])[0].get("finishReason") if isinstance(locals().get("r"), dict) else None
            LOG.append(f"{tag}: {m} bad answer {type(e).__name__} {e} finish={fin} usage={r.get('usageMetadata') if isinstance(locals().get('r'), dict) else None}"); time.sleep(3)
        except Exception as e:
            LOG.append(f"{tag}: {m} {e}"); time.sleep(10)
    raise SystemExit(f"{tag}: Gemini gave no usable answer")

# ---------------------------------------------------------------- checks
BANNED = re.compile(r"\b(Furthermore|Moreover|Additionally|Specifically|Ultimately|In conclusion|synonymous|great distinction|legendary|renowned|iconic)\b", re.I)
MENU = {  # prop -> required fields
    "tiles": ["items"], "flow": ["nodes"], "ladder": ["rungs"], "bars": ["bars", "max"], "sum": ["parts", "total"],
    "tree": ["root", "branches"], "plaques": ["items"], "nameplate": ["name"], "dates": ["events"], "calPage": ["day", "month"],
    "sheet": ["title"], "scale": ["l", "r"], "vsCards": ["l", "r"], "trophy": ["t"], "tally": ["items"], "road": ["signs"],
    "apPins": ["pins"], "indiaMap": ["pins"]}
LISTS = {"tiles": "items", "flow": "nodes", "ladder": "rungs", "bars": "bars", "sum": "parts", "tree": "branches",
         "plaques": "items", "dates": "events", "tally": "items", "road": "signs", "apPins": "pins", "indiaMap": "pins"}
AP_PINS = set("tirupati machilipatnam guntur banaganapalle araku srikalahasti uppada mangalagiri venkatagiri dharmavaram ponduru "
              "kondapalli etikoppaka budithi bobbili durgi udayagiri allagadda narasapur visakhapatnam vijayawada kolleru nsstr "
              "arasavalli srikakulam godavari krishna amaravati rajahmundry nellore kakinada eluru konaseema bhimavaram sriharikota "
              "amalapuram lepakshi orvakal simhachalam kasibugga".split())
IN_PINS = set("delhi hyderabad vijayawada visakhapatnam mumbai navimumbai indore surat ahmedabad bhopal lucknow bengaluru maharashtra "
              "assam tripura kevadia guwahati patna coimbatore belagavi warangal sriharikota tirupati ap".split())

def pair(v):
    return isinstance(v, list) and len(v) == 2 and all(isinstance(x, (str, int, float)) for x in v)

def texts(v, k=0):
    """All on-screen strings of one language inside a visual."""
    if pair(v): yield str(v[k])
    elif isinstance(v, dict):
        for kk, x in v.items():
            if kk not in ("p", "k"): yield from texts(x, k)
    elif isinstance(v, list):
        for x in v: yield from texts(x, k)

def sentences(t):
    return [s for s in re.split(r"(?<=[.!?])\s+", t.strip()) if s]

def scene_errs(sc):
    e, sid = [], sc.get("id", "?")
    beats = sc.get("beats")
    if not isinstance(beats, list) or not beats: return [f"{sid}: no beats"]
    nb = len(beats)
    for i, b in enumerate(beats):
        if not (isinstance(b, dict) and isinstance(b.get("en"), str) and isinstance(b.get("te"), str) and b["en"].strip() and b["te"].strip()):
            e.append(f"{sid} beat {i}: needs non-empty en and te"); continue
        if re.search(r"\d", b["en"] + b["te"]): e.append(f"{sid} beat {i}: digits in speech — write numbers as spoken words")
        if len(b["en"].split()) > 60: e.append(f"{sid} beat {i}: English beat too long ({len(b['en'].split())} words, max 45)")
        for s in sentences(b["en"]):
            if len(s.split()) > 30: e.append(f"{sid} beat {i}: English sentence over 28 words — split it")
        m = BANNED.search(b["en"])
        if m: e.append(f"{sid} beat {i}: essay word '{m.group(0)}' — speak like a teacher")
        if re.search(r"(^|\s)(Q\s?\w+|See Chapter)\s*:", b["en"]): e.append(f"{sid} beat {i}: colon list — full spoken sentences")
        n = b.get("note")
        if n is not None and not (isinstance(n, dict) and (pair(n.get("t")) or pair(n.get("h")))):
            e.append(f"{sid} beat {i}: note must be {{\"t\": [en, te]}} or {{\"h\": [en, te], \"clear\": true}}")
    vis = sc.get("visuals") or []
    if not isinstance(vis, list) or not vis: e.append(f"{sid}: needs 1–2 visuals"); vis = []
    for j, v in enumerate(vis):
        if not isinstance(v, dict) or v.get("p") not in MENU:
            e.append(f"{sid} visual {j}: p must be one of {sorted(MENU)}"); continue
        p = v["p"]
        for f in MENU[p]:
            if f not in v: e.append(f"{sid} visual {j} ({p}): missing '{f}'")
        at = v.get("at", 0)
        if not isinstance(at, int) or not 0 <= at < nb: e.append(f"{sid} visual {j}: at must be a beat index 0..{nb - 1}")
        lst = v.get(LISTS.get(p, ""), [])
        if p in LISTS and (not isinstance(lst, list) or not lst): e.append(f"{sid} visual {j} ({p}): '{LISTS[p]}' must be a non-empty list")
        for it in lst if isinstance(lst, list) else []:
            if isinstance(it, dict) and "b" in it and not (isinstance(it["b"], (int, float)) and 0 <= it["b"] < nb):
                e.append(f"{sid} visual {j} ({p}): item b={it['b']} outside beats 0..{nb - 1}")
            if p in ("apPins", "indiaMap") and isinstance(it, dict):
                ok = AP_PINS if p == "apPins" else IN_PINS
                if it.get("k") not in ok: e.append(f"{sid} visual {j}: pin '{it.get('k')}' not in the {p} list — use tiles/dates")
        for t in list(texts(v, 0)) + list(texts(v, 1)):
            for ln in str(t).split("|"):
                if len(ln) > 46: e.append(f"{sid} visual {j} ({p}): screen line too long ({len(ln)} chars): '{ln[:50]}' — max 6 words, use |")
            if str(t).count("|") > 2: e.append(f"{sid} visual {j} ({p}): max 3 lines")
    return e

def num_forms(tok):
    """Spoken English forms of a number written in the notes ('2026' -> 'twenty twenty-six' / 'two thousand twenty-six')."""
    from num2words import num2words
    t = tok.replace(",", "")
    out = set()
    try:
        if re.fullmatch(r"\d+\.\d+", t): out.add(num2words(float(t)))
        else:
            n = int(t); out.add(num2words(n))
            if 1100 <= n <= 2099: out.add(num2words(n, to="year"))
            if len(t) > 1 and t.startswith("0"): out.add(" ".join(num2words(int(c)) for c in t))
    except Exception: pass
    norm = lambda s: re.sub(r"[\s-]+", " ", s.lower().replace(" and ", " ").replace(",", "")).strip()
    return {norm(x) for x in out}

def coverage(part, scenes):
    """Every rare name/term and every number of the English notes must be spoken in the English script."""
    from wordfreq import zipf_frequency
    en = part["en"]
    spoken = " ".join(b["en"] for sc in scenes for b in sc.get("beats", []) if isinstance(b, dict) and isinstance(b.get("en"), str))
    screen = " ".join(t for sc in scenes for v in sc.get("visuals") or [] for t in texts(v, 0))
    low = re.sub(r"[\s-]+", " ", spoken.lower())
    names, nums = set(), set()
    for w in re.findall(r"\b[A-Z][A-Za-z'’]+|\b[A-Z]{2,}\b", en):
        k = re.sub(r"['’]s$", "", w.lower())
        if len(k) > 2 and (w.isupper() or zipf_frequency(k, "en") < 3.2): names.add(w)
    for n in re.findall(r"(?<![\w.])\d[\d,]*(?:\.\d+)?", en):
        if n.strip(",") not in ("0", "1"): nums.add(n.strip(","))
    miss_names = sorted(w for w in names if re.sub(r"['’]s$", "", w.lower()) not in spoken.lower()
                        and not (w.isupper() and " ".join(w) .lower() in low))
    miss_nums = sorted(n for n in nums if not any(f in low for f in num_forms(n)) and n not in screen)
    return miss_names, miss_nums

# ---------------------------------------------------------------- spec building
def L(v): return {"en": str(v[0]), "te": str(v[1])} if pair(v) else v

def conv(v):
    """Gemini visual -> studio layer: [en, te] pairs -> L(), item `b` -> sentence-time `a`."""
    if pair(v): return L(v)
    if isinstance(v, list):
        out = []
        for i, x in enumerate(v):
            x = conv(x)
            if isinstance(x, dict) and "a" in x and isinstance(x["a"], (int, float)) and float(x["a"]).is_integer():
                x["a"] = x["a"] + 0.05 + 0.1 * (i % 4)     # items of one beat come in one after another
            out.append(x)
        return out
    if isinstance(v, dict):
        return {("a" if k == "b" else k): conv(x) for k, x in v.items()}
    return v

def build(part, plan):
    nb_total, scenes = 0, []
    card = plan.get("card") or {}
    say = card.get("say") if pair(card.get("say")) else [f"Chapter {part['chapter']}, part {part['part']}.", f"అధ్యాయం {part['chapter']}, భాగం {part['part']}."]
    scenes.append({"id": "c00", "template": "chapterCard", "sentences": [{"text": L(say)}],
                   "data": {"kicker": L(card.get("kicker") or [f"Chapter {part['chapter']} · Part {part['part']}", f"అధ్యాయం {part['chapter']} · భాగం {part['part']}"]),
                            "title": L(card.get("title") or [part["chapter_title"], part["chapter_title"]]),
                            "sub": L(card.get("sub") or ["", ""]), "art": "vimana"}})
    for i, sc in enumerate(plan["scenes"]):
        beats = sc["beats"]; nb = len(beats)
        layers, last_at = [{"p": "teFont", "at": 0}], None
        vis = sorted([v for v in sc.get("visuals") or [] if isinstance(v, dict)], key=lambda v: v.get("at", 0))[:2]
        for j, v in enumerate(vis):
            lay = conv({k: x for k, x in v.items()})
            lay.setdefault("at", 0); lay["fit"] = "full"; lay["k"] = 0.95
            nxt = vis[j + 1].get("at") if j + 1 < len(vis) else None
            if nxt is not None and nxt > lay["at"]: lay["out"] = nxt          # one drawing at a time
            elif "out" in lay and not (isinstance(lay["out"], int) and lay["at"] < lay["out"] <= nb): lay.pop("out")
            if lay["p"] in ("nameplate", "trophy", "calPage", "scale") and "a" not in lay: lay["a"] = lay["at"]
            if lay["p"] in ("sheet",) and isinstance(lay.get("lines"), list): lay["lines"] = lay["lines"][:3]
            if lay["p"] == "road" and "hiAt" not in lay: lay["hiAt"] = nb - 0.2
            layers.append(lay)
        items = []
        for k, b in enumerate(beats):
            n = b.get("note")
            if isinstance(n, dict):
                it = {kk: L(x) for kk, x in n.items() if kk in ("t", "h") and pair(x)}
                if n.get("clear"): it["clear"] = True
                if it: it["at"] = k; items.append(it)
        scenes.append({"id": f"s{i + 1:02d}", "template": "stage", "sentences": [{"text": {"en": b["en"].strip(), "te": b["te"].strip()}} for b in beats],
                       "data": {"v": sc.get("kind") if sc.get("kind") in ("card", "trap", "trick", "diary") else "card",
                                "kicker": L(sc.get("kicker") or ["", ""]), "title": L(sc.get("title") or ["", ""]),
                                "layers": layers, "items": items}})
        nb_total += nb
    return {"subject": "current-affairs", "source": L(part["source"]), "scenes": scenes}, nb_total

# ---------------------------------------------------------------- prompt
SHAPE = """Return ONLY one JSON object:
{"card": {"kicker": [en, te], "title": [en, te], "sub": [en, te], "say": [en, te]},
 "scenes": [{"kind": "card|trap|trick|diary", "kicker": [en, te], "title": [en, te],
             "beats": [{"en": "spoken English", "te": "spoken Telugu", "note": {"t": [en, te]} }],
             "visuals": [{"p": "tiles", "at": 0, "out": 4, "cols": 2, "items": [{"h": [en, te], "t": [en, te], "b": 1}]}]}]}
`card.say` is the first spoken line (chapter and part name, what this part covers).
Each scene teaches one idea in 3–9 beats. A beat = 1–3 spoken sentences (15–40 English words)."""

def main():
    part, studio, out_spec, out_rep = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    part = json.load(open(part, encoding="utf-8"))
    rd = lambda p: open(os.path.join(studio, p), encoding="utf-8").read()
    locked = rd("CLAUDE.md").split("## Common rules")[0]
    rules = (locked + "\n\n" + rd("guides/teacher-script.md") + "\n\n" + rd("guides/explain-style.md") + "\n\n" +
             open(os.path.join(HERE, "menu.md"), encoding="utf-8").read())
    where = (f"This is Chapter {part['chapter']} ({part['chapter_title']}), Part {part['part']} of {part['parts']}. "
             f"It teaches these sections, in this order: {'; '.join(part['sections'])}. "
             + (f"The next part covers: {part['next']}. End with a short recap of this part, then name what comes next."
                if part.get("next") else "This is the LAST part of the chapter: end with a recap of the whole chapter's key lines."))
    base = ("You write ONE video lesson for Roach Academia (APPSC exam classes), English AND Telugu together, from the notes below.\n\n"
            "# RULES (the LOCKED rules win over everything)\n" + rules + "\n\n# THIS PART\n" + where +
            "\nTeach EVERY point of these notes — every name, number, date, section, term — in order, explained like a teacher; "
            "leave out only practice MCQs and their answers. English speech teaches the ENGLISH notes; Telugu speech teaches the "
            "TELUGU notes (their own words and spellings), it is not a translation of your English. Same scenes, same beats, same "
            "pictures for both languages.\n\n# ENGLISH NOTES\n" + part["en"] + "\n\n# TELUGU NOTES\n" + part["te"] + "\n\n# ANSWER\n" + SHAPE)
    plan = ask(base, "plan")
    for rnd in range(5):
        if not isinstance(plan, dict) or not isinstance(plan.get("scenes"), list):
            plan = ask(base + "\n\nYour last answer was not the JSON shape asked for. Answer again.", f"reshape {rnd}"); continue
        errs = [x for sc in plan["scenes"] for x in scene_errs(sc)] if isinstance(plan["scenes"], list) else ["scenes missing"]
        for i, sc in enumerate(plan["scenes"]): sc["id"] = f"s{i + 1:02d}"
        mn, mu = coverage(part, plan["scenes"])
        LOG.append(f"round {rnd}: {len(plan['scenes'])} scenes, {sum(len(s.get('beats') or []) for s in plan['scenes'])} beats, "
                   f"{len(errs)} rule errors, missing names {len(mn)}, numbers {len(mu)}")
        if not errs and not mn and not mu: break
        bad = sorted({e.split(" ")[0].rstrip(":") for e in errs})
        fix = ("# YOUR CURRENT LESSON (JSON)\n" + json.dumps(plan, ensure_ascii=False) + "\n\n# PROBLEMS FOUND BY THE CHECKER\n" +
               "\n".join(errs[:80]) +
               (f"\nThese names/terms of the English notes are never SPOKEN in English — teach each where the notes have it: {mn}" if mn else "") +
               (f"\nThese numbers of the English notes are never SPOKEN (as words) in English — say each where it belongs: {mu}" if mu else "") +
               "\n\nFix every problem; change nothing else. Return the WHOLE corrected lesson JSON in the same shape.")
        if rnd == 4: break
        new = ask(base + "\n\n" + fix, f"repair {rnd + 1}")
        if isinstance(new, dict) and isinstance(new.get("scenes"), list): plan = new
    errs = [x for sc in plan["scenes"] for x in scene_errs(sc)]
    mn, mu = coverage(part, plan["scenes"])
    # structural errors that can't be rendered are dropped visuals -> tiles of the notes column (never a missing fact)
    for sc in plan["scenes"]:
        sc["visuals"] = [v for j, v in enumerate(sc.get("visuals") or []) if not any(e.startswith(f"{sc['id']} visual {j}") for e in errs)]
        if not sc["visuals"]:
            hs = [b["note"]["t"] for b in sc["beats"] if isinstance(b.get("note"), dict) and pair(b["note"].get("t"))][:6]
            sc["visuals"] = [{"p": "tiles", "at": 0, "cols": 1 if len(hs) < 4 else 2,
                              "items": [{"h": [re.sub(r"\*\*", "", h[0])[:44], re.sub(r"\*\*", "", h[1])[:44]], "b": k} for k, h in enumerate(hs)] or
                                       [{"h": sc.get("title") or ["", ""], "b": 0}]}]
    blocking = [e for e in errs if " visual " not in e]
    spec, nb = build(part, plan)
    json.dump(spec, open(out_spec, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ok = not blocking and not mn
    with open(out_rep, "w", encoding="utf-8") as f:
        f.write(f"# {part['id']} — {'READY' if ok else 'BLOCKED'}\n\nscenes {len(spec['scenes'])}, sentences {nb + 1}\n\n")
        f.write("## Coverage\n" + f"- names/terms not spoken (blocking): {mn or 'none'}\n- numbers not spoken as words (shown on screen or check by ear): {mu or 'none'}\n")
        f.write("## Rule problems left\n" + ("\n".join(f"- {e}" for e in errs) or "none") + "\n\n## Log\n" + "\n".join(f"- {l}" for l in LOG) + "\n")
    print("READY" if ok else "BLOCKED", part["id"], f"scenes={len(spec['scenes'])} sentences={nb + 1} missing_names={len(mn)} numbers={len(mu)} errors={len(errs)}")
    sys.exit(0 if ok else 3)

if __name__ == "__main__":
    main()
