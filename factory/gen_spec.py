#!/usr/bin/env python3
"""English script + scene plan for ONE video part, written section by section (so nothing is squeezed out), checked by
code; failed checks go back to the model. Telugu is added later into the SAME scenes and beats by te_fill.py.
Usage: python3 gen_spec.py <part.json> <studio_dir> <out_spec.json> <out_report.md>
part.json: from split.py. Rules come from the studio repo (CLAUDE.md locked rules, guides/teacher-script.md,
guides/explain-style.md) + menu.md. Models: llm.py (DeepSeek first for English, Gemini if DeepSeek is unavailable).
Nothing here contains course content (the public repo stays content-free)."""
import json, os, re, sys
from llm import ask, LOG
import lib

HERE = os.path.dirname(os.path.abspath(__file__))

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
TEXT_KEYS = {"h", "t", "sub", "title", "label", "name", "role", "root", "date", "month", "l", "lsub", "r", "rsub", "lines", "stamp", "tag", "v"}

def txt(v):
    """On-screen text value: a plain English string (the model writes English only; Telugu is filled later)."""
    return isinstance(v, str) or isinstance(v, (int, float)) and not isinstance(v, bool)

def texts(v):
    if isinstance(v, str): yield v
    elif isinstance(v, dict):
        for k, x in v.items():
            if k not in ("p", "k", "at", "out", "b", "cols", "max", "hi", "hiAt", "stampAt"): yield from texts(x)
    elif isinstance(v, list):
        for x in v: yield from texts(x)

def sentences(t):
    return [s for s in re.split(r"(?<=[.!?])\s+", t.strip()) if s]

def scene_errs(sc):
    e, sid = [], sc.get("id", "?")
    beats = sc.get("beats")
    if not isinstance(beats, list) or not beats: return [f"{sid}: no beats"]
    nb = len(beats)
    for i, b in enumerate(beats):
        if not (isinstance(b, dict) and isinstance(b.get("en"), str) and b["en"].strip()):
            e.append(f"{sid} beat {i}: needs a non-empty 'en'"); continue
        if re.search(r"\d", b["en"]): e.append(f"{sid} beat {i}: digits in speech — write numbers as spoken words")
        if len(b["en"].split()) > 60: e.append(f"{sid} beat {i}: beat too long ({len(b['en'].split())} words, max 45) — split it into two beats")
        for s in sentences(b["en"]):
            if len(s.split()) > 30: e.append(f"{sid} beat {i}: sentence over 28 words — split it: '{s[:60]}…'")
        m = BANNED.search(b["en"])
        if m: e.append(f"{sid} beat {i}: essay word '{m.group(0)}' — speak like a teacher")
        if re.search(r"(^|\s)(Q\s?\w+|See Chapter)\s*:", b["en"]): e.append(f"{sid} beat {i}: colon list — full spoken sentences")
        n = b.get("note")
        if n is not None and not (isinstance(n, dict) and (isinstance(n.get("t"), str) or isinstance(n.get("h"), str))):
            e.append(f"{sid} beat {i}: note must be {{\"t\": \"…\"}} or {{\"h\": \"…\", \"clear\": true}}")
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
                if it.get("k") not in (AP_PINS if p == "apPins" else IN_PINS):
                    e.append(f"{sid} visual {j}: pin '{it.get('k')}' not in the {p} list — use tiles/dates")
        for t in texts(v):
            for ln in str(t).split("|"):
                if len(ln) > 46: e.append(f"{sid} visual {j} ({p}): screen line too long ({len(ln)} chars): '{ln[:50]}' — max 6 words, use |")
            if str(t).count("|") > 2: e.append(f"{sid} visual {j} ({p}): max 3 lines")
    return e

def num_forms(tok):
    from num2words import num2words
    t = tok.replace(",", ""); out = set()
    try:
        if re.fullmatch(r"\d+\.\d+", t): out.add(num2words(float(t)))
        else:
            n = int(t); out.add(num2words(n))
            if 1100 <= n <= 2099: out.add(num2words(n, to="year"))
            if n < 200: out.add(num2words(n, to="ordinal"))
            if len(t) > 1 and t.startswith("0"): out.add(" ".join(num2words(int(c)) for c in t))
    except Exception: pass
    norm = lambda s: re.sub(r"[\s-]+", " ", s.lower().replace(" and ", " ").replace(",", "")).strip()
    return {norm(x) for x in out}

def coverage(notes, scenes):
    """Every rare name/term and every number of the English notes must be spoken; the script must not be squeezed."""
    from wordfreq import zipf_frequency
    spoken = " ".join(b["en"] for sc in scenes for b in sc.get("beats", []) if isinstance(b, dict) and isinstance(b.get("en"), str))
    screen = " ".join(t for sc in scenes for v in sc.get("visuals") or [] for t in texts(v))
    low = re.sub(r"[\s-]+", " ", spoken.lower())
    names, nums = set(), set()
    notes = re.sub(r"^(#+\s*)\d+(?:\.\d+)*\s+", r"\1", notes, flags=re.M)     # section numbers are not spoken (teacher-script rule)
    for w in re.findall(r"\b[A-Z][A-Za-z'’]+|\b[A-Z]{2,}\b", notes):
        k = re.sub(r"['’]s$", "", w.lower())
        if len(k) > 2 and not re.fullmatch(r"[IVX]+", w) and (w.isupper() or zipf_frequency(k, "en") < 3.2): names.add(w)
    ids = sec_ids(notes)
    for n in re.findall(r"(?<![\d.,])\d[\d,]*(?:\.\d+)?(?:st|nd|rd|th|[a-z](?![a-z]))?", notes):     # Q12, G20, COP28 count too
        if n in ids: continue
        n = re.sub(r"(?:st|nd|rd|th|[a-z])$", "", n)
        if n in ids: continue
        if n.strip(",") not in ("0", "1"): nums.add(n.strip(","))
    def said(w):
        k = re.sub(r"['’]s$", "", w.lower())
        if k in spoken.lower() or (w.isupper() and " ".join(w).lower() in low): return True
        if len(w) > 2 and w.endswith("s") and w[:-1].isupper(): return said(w[:-1])      # CAPFs = C A P Fs
        return False
    miss_names = sorted(w for w in names if not said(w))
    miss_nums = sorted(n for n in nums if not any(f in low for f in num_forms(n)))   # spoken, not only shown
    nw = len(re.findall(r"\w+", re.sub(r"^#.*$", "", notes, flags=re.M))); sw = len(spoken.split())
    return miss_names, miss_nums, nw, sw

def added_names(notes_all, scenes):
    """Nothing added (LOCKED rule): a rare name or term spoken or shown that the notes of this part never use."""
    from wordfreq import zipf_frequency
    low = re.sub(r"[\s-]+", " ", notes_all.lower())
    txt = " ".join([b["en"] for sc in scenes for b in sc.get("beats", []) if isinstance(b, dict) and isinstance(b.get("en"), str)] +
                   [t for sc in scenes for v in sc.get("visuals") or [] for t in texts(v)] +
                   [b["note"].get("t", "") for sc in scenes for b in sc.get("beats", []) if isinstance(b, dict) and isinstance(b.get("note"), dict)])
    out = set()
    for w in re.findall(r"\b[A-Z][A-Za-z'’]{2,}", txt):
        k = re.sub(r"['’]s$", "", w.lower())
        if zipf_frequency(k, "en") >= 3.2 or k in low: continue
        if re.fullmatch(r"[A-Z]+", w) and " ".join(w).lower() in low: continue
        out.add(w)
    return sorted(out)

# ---------------------------------------------------------------- spec building (EN now; TE filled by te_fill.py)
def P(v): return {"en": str(v), "te": ""}

def conv(v):
    """Model visual -> studio layer: strings -> {en, te:''}, item `b` -> sentence-time `a`."""
    if isinstance(v, str): return P(v)
    if isinstance(v, list):
        out = []
        for i, x in enumerate(v):
            x = conv(x)
            if isinstance(x, dict) and isinstance(x.get("a"), (int, float)) and float(x["a"]).is_integer():
                x["a"] = x["a"] + 0.05 + 0.1 * (i % 4)
            out.append(x)
        return out
    if isinstance(v, dict):
        return {("a" if k == "b" else k): (x if k in ("p", "k") else conv(x)) for k, x in v.items()}
    return v

def spoken_num(n):
    from num2words import num2words
    return num2words(n)

def say_numbers(t):
    """Digits -> spoken words (years as years), so the title line can be voiced."""
    from num2words import num2words
    f = lambda m: num2words(int(m.group(0)), to="year") if 1100 <= int(m.group(0)) <= 2099 else num2words(int(m.group(0)))
    return re.sub(r"\d+", f, re.sub(r"(\d),(\d)", r"\1\2", t)).replace("–", " to ").replace("@", " at ")

def speak_digits(t):
    """Any digits the writer left in SPOKEN English become words (same number, nothing changed): 1st -> first,
    4.2 -> four point two, 2026 -> twenty twenty-six, 45% -> forty-five per cent, ₹500 -> five hundred rupees."""
    from num2words import num2words
    t = letters_digits(t)
    t = re.sub(r"(\d),(?=\d{2,3}\b)", r"\1", t)
    t = re.sub(r"₹\s?([\d.]+)((?:\s*(?:lakh|crore|thousand|million|billion))*)", lambda m: f"{m.group(1)}{m.group(2)} rupees", t)
    t = re.sub(r"(\d+)(st|nd|rd|th)\b", lambda m: num2words(int(m.group(1)), to="ordinal"), t)
    t = re.sub(r"(\d)\s?%", r"\1 per cent", t)
    t = re.sub(r"(\d+)\.(\d+)", lambda m: num2words(int(m.group(1))) + " point " + " ".join(num2words(int(c)) for c in m.group(2)), t)
    t = re.sub(r"(\w)\s?–\s?(?=\w)", r"\1 to ", t)
    t = re.sub(r"(\d)\s?[–-]\s?(\d)", r"\1 to \2", t)
    t = re.sub(r"\d+", lambda m: num2words(int(m.group(0)), to="year") if 1100 <= int(m.group(0)) <= 2099 and len(m.group(0)) == 4
               else num2words(int(m.group(0))), t)
    return t

# ---------------------------------------------------------------- section / table numbers (teacher-script rule 2; CHIJOBHA 4 Nov 2026:
# "section numbers like 1.2 are copied onto the signs"). Ids come from the notes themselves: "## 1.2 …", "Table 1.2a —", "Box 3.1".
def sec_ids(md):
    ids = set(re.findall(r"^#+\s*(\d+(?:\.\d+)+[a-z]?)\s", md, flags=re.M))
    ids |= set(re.findall(r"\b(?:Table|Box|Figure|Section|Sec\.|§)\s*(\d+(?:\.\d+)+[a-z]?)", md))
    return ids

LABEL_ID = re.compile(r"\b(Table|Box|Figure|Section|Sec\.|§)\s*\d+(?:\.\d+)+[a-z]?\b\.?\s*[—–:·-]?\s*")

def screen_clean(t, ids):
    """On-screen text never shows a section / table number: '1.2 The written exam' -> 'The written exam',
    'Table 1.2a — Events' -> 'Table — Events' -> 'Events', a bare 'Table 1.1' -> 'Table'."""
    if not isinstance(t, str): return t
    o = t
    m = re.match(r"^\s*(\d+(?:\.\d+)+[a-z]?)(?![\d%])\s*[—–:·.-]?\s*", t)
    if m and m.group(1) in ids: t = t[m.end():]
    t = LABEL_ID.sub(lambda m: m.group(1) + " — ", t)
    for i in sorted(ids, key=len, reverse=True):
        t = re.sub(r"(?<![\d.])" + re.escape(i) + r"(?![\da-z%])(?!\s*(?:per\s*cent|%|crore|lakh))\s*[—–:·-]?\s*", "", t)
    t = re.sub(r"^(Table|Box|Figure|Section)\s*—\s*(?=\S)", "", t.strip())
    t = re.sub(r"\s*—\s*$", "", re.sub(r"\s{2,}", " ", t)).strip(" ·:—-")
    return t or o

def clean_screen(v, ids):
    if isinstance(v, str): return screen_clean(v, ids)
    if isinstance(v, list): return [clean_screen(x, ids) for x in v]
    if isinstance(v, dict): return {k: (x if k in ("p", "k", "at", "out", "b", "cols", "max", "hi", "hiAt", "stampAt") else clean_screen(x, ids)) for k, x in v.items()}
    return v

def spoken_ids(t, ids):
    """Section / table numbers left in SPOKEN text (before digits become words)."""
    found = [m.group(0) for m in re.finditer(r"\b(?:Table|Box|Figure|Section|Sec\.|§)\s*\d+(?:\.\d+)+[a-z]?", t)]
    found += [i for i in ids if re.search(r"(?<![\d.])" + re.escape(i) + r"(?![\da-z])(?!\s*(?:per\s*cent|%|crore|lakh|million|billion))", t)]
    return found

def letters_digits(t):
    """G20 -> G twenty, COP28 -> COP twenty-eight, 5G -> five G: the number is spoken as a word, the letters stay letters."""
    from num2words import num2words
    t = re.sub(r"\b([A-Z]{1,6})-?(\d{1,4})\b", lambda m: f"{m.group(1)} {num2words(int(m.group(2)))}", t)
    t = re.sub(r"\b(\d{1,3})([A-Z]{1,3})\b", lambda m: f"{num2words(int(m.group(1)))} {m.group(2)}", t)
    return t

def build(part, scenes_in):
    ch, pt = part["chapter"], part["part"]
    secs = [re.sub(r"^[\d.]+\s*", "", s) for s in part["sections"]]
    say = f"Chapter {spoken_num(ch)}, part {spoken_num(pt)}. {part['chapter_title']}. In this part: {', '.join(secs[:4])}."
    scenes = [{"id": "c00", "template": "chapterCard", "sentences": [{"text": P(say_numbers(say))}],
               "data": {"kicker": P(f"Chapter {ch} · Part {pt}"), "title": P(part["chapter_title"]),
                        "sub": P(" · ".join(secs[:3])[:90]), "art": "vimana"}}]
    nb_total = 0
    ids = sec_ids(part.get("en", ""))
    for i, sc in enumerate(scenes_in):
        sc = clean_screen(sc, ids)
        beats = sc["beats"]; nb = len(beats)
        layers = [{"p": "teFont", "at": 0}]
        vis = sorted([v for v in sc.get("visuals") or [] if isinstance(v, dict)], key=lambda v: v.get("at", 0))[:2]
        for j, v in enumerate(vis):
            lay = conv(dict(v)); lay.setdefault("at", 0); lay["fit"] = "full"; lay["k"] = 0.95
            nxt = vis[j + 1].get("at") if j + 1 < len(vis) else None
            if nxt is not None and nxt > lay["at"]: lay["out"] = nxt
            elif "out" in lay and not (isinstance(lay["out"], int) and lay["at"] < lay["out"] <= nb): lay.pop("out")
            if lay["p"] in ("nameplate", "trophy", "calPage", "scale") and "a" not in lay: lay["a"] = lay["at"]
            if lay["p"] == "sheet" and isinstance(lay.get("lines"), list): lay["lines"] = lay["lines"][:3]
            if lay["p"] == "road" and "hiAt" not in lay: lay["hiAt"] = nb - 0.2
            if lay["p"] == "bars":
                for b in lay.get("bars", []):
                    if isinstance(b.get("v"), dict): b["v"] = float(re.sub(r"[^\d.]", "", b["v"]["en"]) or 0)
                if isinstance(lay.get("max"), dict): lay["max"] = float(re.sub(r"[^\d.]", "", lay["max"]["en"]) or 1)
            layers.append(lay)
        items = []
        for k, b in enumerate(beats):
            n = b.get("note")
            if isinstance(n, dict):
                it = {kk: P(x) for kk, x in n.items() if kk in ("t", "h") and isinstance(x, str)}
                if n.get("clear"): it["clear"] = True
                if it: it["at"] = k; items.append(it)
        scenes.append({"id": f"s{i + 1:02d}", "template": "stage",
                       "sentences": [{"text": {"en": b["en"].strip(), "te": ""}} for b in beats],
                       "data": {"v": sc.get("kind") if sc.get("kind") in ("card", "trap", "trick", "diary") else "card",
                                "kicker": P(sc.get("kicker") or ""), "title": P(sc.get("title") or ""), "layers": layers, "items": items}})
        nb_total += nb
    base = re.sub(r"-\d{4}$", "", part.get("subject", "current-events"))
    look = {"current-events": "current-affairs", "g2-current-affairs": "current-affairs", "bhagavatam": "bhagavatam",
            "disaster-management": "geography", "endowment-finance-lands": "temple", "eo-economy": "economy", "g2-economy": "economy",
            "family-adoption-succession": "polity", "festivals-fine-arts": "festivals", "general-science-tech": "science",
            "g2-science-tech": "science", "india-ap-geography": "geography", "g2-geography": "geography", "india-ap-history": "history",
            "g2-ap-history": "history", "g2-indian-history": "history", "indian-polity": "polity", "g2-polity": "polity",
            "g2-indian-society": "polity", "mahabharatam": "mahabharata", "philosophies-gurus": "philosophy", "purana-darshini": "puranas",
            "ramayanam": "ramayana", "sustainable-development-environment": "environment", "temple-agamas": "temple",
            "vedic-culture": "philosophy"}.get(base, "current-affairs")          # the subject's one accent colour (theme.ts ACCENT)
    return size_spec({"subject": look, "source": {"en": part["source"][0], "te": part["source"][1]}, "te_pending": True,
            "scenes": scenes}), nb_total + 1

# ---------------------------------------------------------------- layout fixes (both languages; run again after Telugu)
def _len(v):
    if isinstance(v, dict): return max((max(len(x) for x in str(t).split("|")) for t in v.values() if t), default=0)
    return max((len(x) for x in str(v or "").split("|")), default=0)

def size_spec(spec):
    _size(spec)
    from sync import sync_spec
    sync_spec(spec)                      # every element appears when its own words are spoken (sync.py)
    return spec

def _size(spec):
    """Boxes grow with their longest words (drawings are scaled to fit afterwards, so nothing spills out); the first drawing
    starts on the first beat (no empty picture); the notes column turns a page every 7 lines (nothing runs off the bottom)."""
    for sc in spec["scenes"]:
        d = sc.get("data") or {}
        # a long list of wide tiles would shrink below readable size: show it 4 at a time, each group on its own beats
        new = []
        for l in d.get("layers") or []:
            # a time line with more than 3 dates is shown 3 at a time (5 on one line shrank the words below readable size)
            key = "items" if l.get("p") == "tiles" else "events" if l.get("p") == "dates" else None
            its = l.get(key) if key else None
            wide = its and (key == "events" or max((_len(i.get("h")) for i in its), default=0) > 16)
            G = 3 if key == "events" else 4
            if its and len(its) > G and wide:
                groups = [its[k:k + G] for k in range(0, len(its), G)]
                starts = [l.get("at", 0)] + [int(g[0].get("a", 0)) for g in groups[1:]]
                for gi, g in enumerate(groups):
                    if gi and starts[gi] <= starts[gi - 1]: new[-1][key] += g; continue
                    m = {**l, key: g, "at": starts[gi]}
                    if gi + 1 < len(groups) and starts[gi + 1] > starts[gi]: m["out"] = starts[gi + 1]
                    elif "out" in l: m["out"] = l["out"]
                    else: m.pop("out", None)
                    new.append(m)
            else: new.append(l)
        d["layers"] = new
        lays = [l for l in d.get("layers") or [] if l.get("p") != "teFont"]
        if lays and lays[0].get("at", 0) != 0: lays[0]["at"] = 0
        for l in lays:
            if l.get("p") == "tiles" and isinstance(l.get("items"), list):
                its = l["items"]; hl = max((_len(i.get("h")) for i in its), default=8); tl = max((_len(i.get("t")) for i in its), default=0)
                w = max(420, int(max(hl * 29, tl * 21)) + 70)
                l["cols"] = 1 if w > 760 or len(its) <= 2 and w > 600 else min(l.get("cols") or 2, 3 if w < 520 else 2, 2 if len(its) == 4 else 3)
                l["w"] = w
                nl = max((len(str((i.get("t") or {}).get("en", i.get("t")) if isinstance(i.get("t"), dict) else i.get("t") or "").split("|")) if i.get("t") else 0) for i in its)
                l["h"] = 130 + 50 * nl
            if l.get("p") == "flow" and isinstance(l.get("nodes"), list):
                l["w"] = max(560, max((_len(n.get("t")) for n in l["nodes"]), default=10) * 26 + 80)
            if l.get("p") == "tally" and isinstance(l.get("items"), list):
                l["w"] = 340      # 4 Nov 2026: words wrap inside the box; a box as wide as its longest word made 6 boxes unreadably small
            if l.get("p") in ("dates", "plaques"):
                its = l.get("events") or l.get("items") or []
                l["w"] = max(l.get("w") or 0, 900, max((max(_len(i.get("t")), _len(i.get("name")), _len(i.get("role"))) for i in its), default=10) * 24 + 200)
                if l["p"] == "dates": l["w"] = max(l["w"], 330 * (len(its) + 1))
        n = 0
        for it in d.get("items") or []:
            if it.get("clear"): n = 0
            n += 1
            if n > 7: it["clear"] = True; n = 1
    return spec

# ---------------------------------------------------------------- notes -> chunks
def chunks(md, limit=520):
    """Cut the part's English notes at ## / ### headings into pieces of at most ~limit words (whole subsections)."""
    body = re.sub(r"^# .*\n", "", md, count=1)
    pieces = re.split(r"\n(?=#{2,3} )", body)
    out, cur = [], ""
    for p in pieces:
        # never across a ## section (pieces then match the same section in another subject -> reused from the library)
        if cur and (p.startswith("## ") or len(re.findall(r"\w+", cur + p)) > limit): out.append(cur); cur = ""
        cur += ("\n" if cur else "") + p
    if cur.strip(): out.append(cur)
    return out

SHAPE = """Return ONLY one JSON object (ENGLISH only — the Telugu is written later into the same beats):
{"scenes": [{"kind": "card|trap|trick|diary", "kicker": "short label", "title": "scene title",
             "beats": [{"en": "spoken English", "note": {"t": "notes-column line"}}],
             "visuals": [{"p": "tiles", "at": 0, "out": 4, "cols": 2, "items": [{"h": "title", "t": "subline", "b": 1}]}]}]}
All on-screen text and notes are plain English strings (not pairs). Never put a section or table number (1.2, Table 1.2a)
in speech or on screen: say "this table", "the next section", or name the topic.
Each scene teaches one idea in 3–9 beats. A beat = 1–3 spoken sentences (15–40 words)."""

def main():
    part, studio, out_spec, out_rep = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
    part = json.load(open(part, encoding="utf-8"))
    rd = lambda p: open(os.path.join(studio, p), encoding="utf-8").read()
    locked = rd("CLAUDE.md").split("## Common rules")[0]
    rules = (locked + "\n\n" + rd("guides/teacher-script.md") + "\n\n" + rd("guides/explain-style.md") + "\n\n" +
             open(os.path.join(HERE, "menu.md"), encoding="utf-8").read())
    rules = rules.replace('All text is a pair `["English", "Telugu"]`.', "All text is plain English (Telugu is added later).")
    pieces = chunks(part["en"])
    ids = sec_ids(part["en"])
    if part.get("next"): part["next"] = screen_clean(str(part["next"]), ids)
    all_scenes, lex, report, blocking = [], {}, [], []
    for ci, piece in enumerate(pieces):
        first, last = ci == 0, ci == len(pieces) - 1
        where = (f"Chapter {part['chapter']} ({part['chapter_title']}), Part {part['part']} of {part['parts']}; it covers: "
                 f"{'; '.join(part['sections'])}. You now write piece {ci + 1} of {len(pieces)} of this part's lesson. "
                 + ("Start with the hook and what this part covers (the chapter title card is already shown). " if first else
                    "Continue naturally from what was just said (do not greet or restart). ")
                 + ((f"End this piece with a short recap of the whole part, then say the next part covers: {part['next']}."
                     if part.get("next") else "End with a recap of the whole chapter's key lines.") if last else
                    "Do not recap yet — the lesson continues in the next piece."))
        prev = [b["en"] for sc in all_scenes[-2:] for b in sc["beats"]][-4:]
        # the same notes text, in the same role (opening / middle / closing of a part), is reused from the library
        lk = lib.key(piece + ("|first|" + "; ".join(part["sections"]) if first else "") + ("|last|" + str(part.get("next")) if last else ""))
        hit = lib.get("en", lk)
        if hit and isinstance(hit.get("scenes"), list) and hit["scenes"]:
            for k, sc in enumerate(hit["scenes"]): sc["id"] = f"p{ci + 1}s{k + 1}"
            all_scenes += hit["scenes"]; lex.update(hit.get("lexicon") or {})
            report.append(f"- piece {ci + 1}: reused from the library ({lk}) — no AI call"); LOG.append(f"piece {ci + 1}: library hit {lk}")
            continue
        base = ("You write part of ONE video lesson for Roach Academia (APPSC exam classes), in ENGLISH, from the notes below.\n\n"
                "# RULES (the LOCKED rules win over everything)\n" + rules + "\n\n# WHERE WE ARE\n" + where +
                "\n\n# JUST SAID (continue from here)\n" + json.dumps(prev) +
                "\n\n# TEACH EVERY POINT OF THESE NOTES — every sentence, bullet, table row, name, number, date, section, term, "
                "exam box and source note — in order, explained like a teacher (at least one beat per notes point; usually "
                "more words than the notes, never fewer). Leave out only practice MCQs.\n" + piece + "\n\n# ANSWER\n" + SHAPE)
        out, errs, mn, mu = None, [], [], []
        for rnd in range(4):
            prompt = base if out is None else (base + "\n\n# YOUR LAST ANSWER\n" + json.dumps(out) + "\n\n# CHECKER FOUND\n" +
                     "\n".join(errs[:60]) +
                     (f"\nNever spoken (teach each where the notes have it): {mn}" if mn else "") +
                     (f"\nNumbers never spoken as words: {mu}" if mu else "") +
                     (f"\nToo short: {sw} spoken words for {nw} words of notes — explain every point fully." if sw < 0.9 * nw else "") +
                     "\nFix all of it, keep everything else, return the WHOLE answer again.")
            new = ask(prompt, f"piece {ci + 1}/{len(pieces)} round {rnd}", prefer=("anthropic", "deepseek", "gemini"))
            if isinstance(new, dict) and isinstance(new.get("scenes"), list) and new["scenes"]:
                out = new
                said_ids = sorted({x for sc in out["scenes"] for b in sc.get("beats") or [] if isinstance(b, dict) and isinstance(b.get("en"), str)
                                   for x in spoken_ids(b["en"], ids)})
                for sc in out["scenes"]:
                    for b in sc.get("beats") or []:
                        if isinstance(b, dict) and isinstance(b.get("en"), str) and re.search(r"\d", b["en"]): b["en"] = speak_digits(b["en"])
            elif out is None: continue
            for k, sc in enumerate(out["scenes"]): sc["id"] = f"p{ci + 1}s{k + 1}"
            errs = [x for sc in out["scenes"] for x in scene_errs(sc)]
            if said_ids: errs.append(f"section/table numbers spoken {said_ids} — never say a section or table number; say 'this table', "
                                     "'the next section' or name its topic instead")
            add = added_names(part["en"] + " " + part.get("chapter_title", ""), out["scenes"])
            if add: errs.append(f"names/terms not in the notes {add} — nothing may be added; use only the notes' own names and terms")
            mn, mu, nw, sw = coverage(piece, out["scenes"])
            LOG.append(f"piece {ci + 1}: {len(out['scenes'])} scenes, {sum(len(s.get('beats') or []) for s in out['scenes'])} beats, "
                       f"{sw} spoken words / {nw} notes words, rule errors {len(errs)}, missing names {mn}, numbers {mu}")
            hard = [e for e in errs if " visual " not in e and "sentence over" not in e]
            if not mn and not mu and not hard and sw >= 0.9 * nw and len(errs) <= 4: break
        if out is None: sys.exit(f"piece {ci + 1}: no usable answer")
        # visuals that still break a rule are replaced by tiles of the notes column (a picture slip never blocks a video)
        for sc in out["scenes"]:
            ok = [v for j, v in enumerate(sc.get("visuals") or []) if not any(e.startswith(f"{sc['id']} visual {j}") for e in errs)]
            if not ok:
                hs = [b["note"]["t"] for b in sc["beats"] if isinstance(b, dict) and isinstance(b.get("note"), dict) and isinstance(b["note"].get("t"), str)][:6]
                ok = [{"p": "tiles", "at": 0, "cols": 1 if len(hs) < 4 else 2,
                       "items": [{"h": re.sub(r"\*\*", "", h)[:44], "b": k} for k, h in enumerate(hs)] or [{"h": sc.get("title") or "", "b": 0}]}]
            sc["visuals"] = ok
        all_scenes += out["scenes"]
        lex.update({k.lower(): v for k, v in (out.get("lexicon") or {}).items()
                    if isinstance(v, str) and re.fullmatch(r"[ఀ-౿‌\s'-]+", v.strip())})
        hard = [e for e in errs if " visual " not in e and "sentence over" not in e]
        if not mn and not mu and not hard and sw >= 0.7 * nw:
            lib.put("en", lk, {"scenes": out["scenes"], "lexicon": {k.lower(): v for k, v in (out.get("lexicon") or {}).items() if isinstance(v, str)}})
        report.append(f"- piece {ci + 1}: {sw} spoken / {nw} notes words · missing names {mn or 'none'} · numbers not spoken {mu or 'none'} · rule problems {len(hard)}")
        if mn: blocking.append(f"piece {ci + 1}: names/terms never spoken {mn}")
        if mu: blocking.append(f"piece {ci + 1}: numbers never spoken {mu}")     # LOCKED rule: every number is taught
        if hard: blocking += [f"piece {ci + 1}: {e}" for e in hard]
        if sw < 0.7 * nw: blocking.append(f"piece {ci + 1}: script far shorter than the notes ({sw}/{nw} words)")
    spec, nsent = build(part, all_scenes)
    json.dump(spec, open(out_spec, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(lex, open(out_spec.replace(".json", "-lex.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ok = not blocking
    with open(out_rep, "w", encoding="utf-8") as f:
        f.write(f"# {part['id']} — {'READY' if ok else 'BLOCKED'} (English)\n\nscenes {len(spec['scenes'])}, sentences {nsent}\n\n")
        f.write("## Coverage by piece\n" + "\n".join(report) + "\n\n## Blocking\n" + ("\n".join(f"- {b}" for b in blocking) or "none") +
                "\n\n## Log\n" + "\n".join(f"- {l}" for l in LOG) + "\n")
    print("READY" if ok else "BLOCKED", part["id"], f"scenes={len(spec['scenes'])} sentences={nsent} blocking={len(blocking)}")
    sys.exit(0 if ok else 3)

if __name__ == "__main__":
    main()
