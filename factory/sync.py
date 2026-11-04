#!/usr/bin/env python3
"""Picture-voice sync (4 Nov 2026). A beat is 1–3 spoken sentences; before this, everything of a beat (list items, notes
lines, labels) appeared when the beat STARTED, often seconds before the teacher said it. Now each element appears at the
moment its own words are spoken: its words are found in the beat's text (or the beat before/after) and the time inside the
beat follows the position of those words (the voice speaks at a steady pace, so text position ≈ time).
Idempotent (works from the whole-beat number). Usage: python3 sync.py <spec.json> [...]   (rewrites the files)"""
import json, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

STOP = set("the and for with from that this into are was were has have had its their his her our your about after before "
           "than then also only over under more most very what when where which who whom why how all any each one two three "
           "per cent part chapter section".split())
TEXT_KEYS = ("h", "t", "name", "role", "label", "date", "v", "title", "sub", "lines", "l", "r", "lsub", "rsub", "tag", "big")

def _spoken(t):
    try:
        from gen_spec import speak_digits
        return speak_digits(t)
    except Exception:
        return t

def words(t):
    t = _spoken(re.sub(r"\*\*|\|", " ", str(t)))
    return [w for w in re.findall(r"[a-z][a-z'-]{2,}|[ఀ-౿]{2,}", t.lower()) if w not in STOP]

def en(v):
    """English text of a value ({en, te} pair, plain string, list of them)."""
    if isinstance(v, dict) and "en" in v: return str(v["en"])
    if isinstance(v, list): return " ".join(en(x) for x in v)
    return "" if v is None or isinstance(v, (int, float, bool)) else str(v)

def item_words(it):
    return [w for k in TEXT_KEYS if k in it for w in words(en(it[k]))]

def place(ws, beats, base, lo=0.0, hi=None):
    """Best time (sentence index + fraction) for words ws near beat `base`."""
    hi = len(beats) - 0.05 if hi is None else hi
    if not ws: return None
    best = None
    for b in (base, base + 1, base - 1):
        if not 0 <= b < len(beats): continue
        txt = beats[b]; n = max(1, len(txt))
        pos = [txt.find(w[:max(4, len(w) - 2)]) for w in ws]          # stem match: "elections" ~ "election"
        hits = [p for p in pos if p >= 0]
        if not hits: continue
        score = len(hits) / len(ws) - (0.15 if b != base else 0)
        t = b + max(0.0, min(0.92, min(hits) / n - 0.04))              # just before the word is said
        if best is None or score > best[0]: best = (score, t)
    if not best or best[0] < 0.3: return None
    return min(max(best[1], lo), hi)

def sync_scene(sc):
    d = sc.get("data") or {}
    beats = [en(s["text"]).lower() for s in sc.get("sentences") or []]
    if not beats or sc.get("template") != "stage": return 0
    moved = 0
    for lay in d.get("layers") or []:
        if lay.get("p") == "teFont": continue
        lo = float(lay.get("at", 0)); hi = float(lay["out"]) - 0.1 if "out" in lay else None
        for key in ("items", "nodes", "rungs", "bars", "parts", "branches", "events", "signs", "pins"):
            lst = lay.get(key)
            if not isinstance(lst, list): continue
            prev = lo
            for it in lst:
                if not isinstance(it, dict) or not isinstance(it.get("a"), (int, float)): continue
                t = place(item_words(it), beats, int(it["a"]), lo, hi)
                if t is not None: it["a"] = round(t, 3); moved += 1
                it["a"] = round(max(it["a"], prev), 3); prev = it["a"] + 0.02     # a list still builds in order
        for sub in ("total", "l", "r"):                                # sum.total, vsCards sides
            it = lay.get(sub)
            if isinstance(it, dict) and isinstance(it.get("a"), (int, float)):
                t = place(item_words(it), beats, int(it["a"]), lo, hi)
                if t is not None: it["a"] = round(t, 3); moved += 1
        if isinstance(lay.get("a"), (int, float)) and lay.get("p") in ("nameplate", "trophy", "calPage", "scale"):
            t = place(item_words(lay), beats, int(lay["a"]), lo, hi)
            if t is not None: lay["a"] = round(t, 3); moved += 1
    prev = 0.0
    for it in d.get("items") or []:                                    # the teacher's notes column
        if not isinstance(it.get("at"), (int, float)): continue
        t = place(item_words(it), beats, int(it["at"]))
        if t is not None and int(t) == int(it["at"]): it["at"] = round(t, 3); moved += 1
        it["at"] = round(max(it["at"], prev), 3); prev = it["at"]
    return moved

def sync_spec(spec):
    return sum(sync_scene(sc) for sc in spec.get("scenes") or [])

if __name__ == "__main__":
    for f in sys.argv[1:]:
        s = json.load(open(f, encoding="utf-8")); n = sync_spec(s)
        json.dump(s, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"{f}: {n} elements timed to their words")
