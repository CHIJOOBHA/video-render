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
                t = place(item_words(it), beats, int(it["a"]), 0.0, None)        # where its words are really said
                if t is not None: it["a"] = round(t, 3); it["_w"] = it["a"]; moved += 1
                it["a"] = round(max(it["a"], prev), 3); prev = it["a"] + 0.02     # a list still builds in order
        for sub in ("total", "l", "r"):                                # sum.total, vsCards sides
            it = lay.get(sub)
            if isinstance(it, dict) and isinstance(it.get("a"), (int, float)):
                t = place(item_words(it), beats, int(it["a"]), 0.0, None)
                if t is not None: it["a"] = round(t, 3); it["_w"] = it["a"]; moved += 1
        # 5 Nov 2026: lines of a document / comparison card and the two sides of a scale each appear when spoken
        if lay.get("p") == "sheet" and isinstance(lay.get("lines"), list):
            base = int(lay.get("a", lo) or lo)
            lay["lineAts"] = []; lay["_lw"] = []
            for ln in lay["lines"]:
                t = place(words(en(ln)), beats, base, 0.0, None)
                lay["_lw"].append(t); lay["lineAts"].append(round(t, 3) if t is not None else float(base))
        for side in ("l", "r"):
            cd = lay.get(side)
            if lay.get("p") == "vsCards" and isinstance(cd, dict) and isinstance(cd.get("lines"), list):
                base = int(cd.get("a", lo) or lo)
                cd["lineAts"] = []; cd["_lw"] = []
                for ln in cd["lines"]:
                    t = place(words(en(ln)), beats, base, 0.0, None)
                    cd["_lw"].append(t); cd["lineAts"].append(round(t, 3) if t is not None else float(base))
        if lay.get("p") == "scale":
            for side, key in (("l", "la"), ("r", "ra")):
                ws = words(en(lay.get(side))) + words(en(lay.get(side + "sub")))
                t = place(ws, beats, int(lay.get("a", lo) or lo), 0.0, None)
                if t is not None: lay[key] = round(t, 3); lay["_" + key] = t; moved += 1
        if isinstance(lay.get("a"), (int, float)) and lay.get("p") in ("nameplate", "trophy", "calPage", "scale"):
            t = place(item_words(lay), beats, int(lay["a"]), 0.0, None)
            if t is not None: lay["a"] = round(t, 3); lay["_w"] = lay["a"]; moved += 1
    prev = 0.0
    for it in d.get("items") or []:                                    # the teacher's notes column
        if not isinstance(it.get("at"), (int, float)): continue
        t = place(item_words(it), beats, int(it["at"]))
        if t is not None and int(t) >= int(it["at"]): it["at"] = round(float(int(t)) if int(t) > int(it["at"]) else t, 3); moved += 1
        it["at"] = round(max(it["at"], prev), 3); prev = it["at"]
    return moved

LISTK = ("items", "nodes", "rungs", "bars", "parts", "branches", "events", "signs", "pins")

def no_empty_picture(sc):
    """Drawings follow each other with no gap, and nothing appears before its own words (5 Nov 2026).
    4 Nov: items were pulled to fixed slots and to the drawing's arrival so the picture was never empty — CHIJOBHA: "some
    elements on the screen moved faster than the voice". Now:
      - an element appears at the START of the sentence (voice clip) in which its words are said — never in an earlier clip;
      - a later drawing arrives on the clip where its first element is said (the previous drawing stays until then);
      - the first drawing of a scene arrives at the start; until its first item is said it shows as a faint wordless outline
        (Journal.tsx), so the picture is never empty. timing_report lists any element that would show early, or whose words
        come after its drawing has left; gen_spec sends those scenes back for a rewrite."""
    if sc.get("template") != "stage": return
    nb = len(sc.get("sentences") or [])
    lays = sorted([l for l in (sc.get("data") or {}).get("layers") or [] if l.get("p") != "teFont"], key=lambda l: l.get("at", 0))
    def first_w(l):
        ws = [it.get("_w") for k in LISTK for it in (l.get(k) or []) if isinstance(it, dict)]
        ws += [l[k].get("_w") for k in ("l", "r", "total") if isinstance(l.get(k), dict)] + [l.get("_w")]
        ws = [w for w in ws if isinstance(w, (int, float))]
        return min(ws) if ws else None
    for j, l in enumerate(lays):
        if j == 0: l["at"] = 0
        else:
            fw = first_w(l)
            if fw is not None: l["at"] = max(lays[j - 1]["at"] + 1, min(nb - 1, int(fw)))
            l["at"] = max(l["at"], lays[j - 1]["at"] + 1)
    for j, l in enumerate(lays):
        if j + 1 < len(lays): l["out"] = lays[j + 1]["at"]
        else: l.pop("out", None)
    # 5 Nov 2026: a list item whose words come after its drawing has left moves to the next drawing when that is the same kind
    # of list (tiles -> tiles): it then appears on the clip that says it instead of sending the whole piece back for a rewrite
    for j, l in enumerate(lays[:-1]):
        nx = lays[j + 1]
        if nx.get("p") != l.get("p"): continue
        for k in LISTK:
            if not isinstance(l.get(k), list) or not isinstance(nx.get(k), list): continue
            late = [it for it in l[k] if isinstance(it, dict) and isinstance(it.get("_w"), (int, float)) and int(it["_w"]) >= l["out"]]
            if late and len(late) < len(l[k]):
                l[k] = [it for it in l[k] if it not in late]; nx[k] = late + nx[k]
    for j, l in enumerate(lays):
        at = l["at"]
        def snap(it, key="a"):
            w = it.get("_w")
            if isinstance(w, (int, float)): it[key] = round(max(at, float(int(w))), 3)   # start of the clip that says it
            elif isinstance(it.get(key), (int, float)): it[key] = round(max(at, it[key]), 3)
        for k in LISTK:
            for it in l.get(k) or []:
                if isinstance(it, dict) and ("_w" in it or isinstance(it.get("a"), (int, float))): snap(it)
        for k in ("l", "r", "total"):
            if isinstance(l.get(k), dict): snap(l[k])
        if "_w" in l or isinstance(l.get("a"), (int, float)): snap(l)
        def snap_list(d):
            if isinstance(d.get("lineAts"), list):
                d["lineAts"] = [round(max(at, float(int(w))) if isinstance(w, (int, float)) else max(at, x), 3)
                                for x, w in zip(d["lineAts"], d.get("_lw") or [None] * len(d["lineAts"]))]
        snap_list(l)
        for k in ("l", "r"):
            if isinstance(l.get(k), dict): snap_list(l[k])
        for key in ("la", "ra"):
            w = l.get("_" + key)
            if isinstance(w, (int, float)): l[key] = round(max(at, float(int(w))), 3)
        if l.get("p") == "scale" and isinstance(l.get("la"), (int, float)) and isinstance(l.get("ra"), (int, float)):
            l["a"] = round(max(l.get("a") or 0, l["la"], l["ra"]), 3)       # the beam tips only after both sides are named

def timing_report(spec):
    """Elements that would appear before the clip in which their words are said (or after their drawing has left)."""
    out = []
    for sc in spec.get("scenes") or []:
        for j, l in enumerate([l for l in (sc.get("data") or {}).get("layers") or [] if l.get("p") != "teFont"]):
            end = l.get("out", len(sc.get("sentences") or []))
            its = [(f"{k}[{i}]", it) for k in LISTK for i, it in enumerate(l.get(k) or []) if isinstance(it, dict)]
            its += [(k, l[k]) for k in ("l", "r", "total") if isinstance(l.get(k), dict)] + [("drawing", l)]
            for d0, nm in [(l, "line")] + [(l[k], f"{k} line") for k in ("l", "r") if isinstance(l.get(k), dict)]:
                for i, (x, w) in enumerate(zip(d0.get("lineAts") or [], d0.get("_lw") or [])):
                    if isinstance(w, (int, float)) and x < int(w) - 0.01:
                        out.append(f"{sc['id']} visual {j} ({l.get('p')}) {nm} {i}: would show in beat {int(x)}, words said in beat {int(w)}")
            for key in ("la", "ra"):
                w = l.get("_" + key)
                if isinstance(w, (int, float)) and l.get(key, 0) < int(w) - 0.01:
                    out.append(f"{sc['id']} visual {j} (scale) {key}: early")
            for name, it in its:
                w, a = it.get("_w"), it.get("a")
                if not isinstance(w, (int, float)) or not isinstance(a, (int, float)): continue
                if a < int(w) - 0.01:
                    out.append(f"{sc['id']} visual {j} ({l.get('p')}) {name}: would show in beat {int(a)}, but its words are said in beat {int(w)}")
                elif int(w) >= end:
                    out.append(f"{sc['id']} visual {j} ({l.get('p')}) {name}: its words are said in beat {int(w)}, after this drawing has "
                               f"left (the next drawing starts on beat {end}) — move it to the next drawing or say it earlier")
    return out

def strip_marks(spec):
    for sc in spec.get("scenes") or []:
        for l in (sc.get("data") or {}).get("layers") or []:
            for m in ("_w", "_lw", "_la", "_ra"): l.pop(m, None)
            for k in LISTK + ("l", "r", "total"):
                v = l.get(k)
                for it in (v if isinstance(v, list) else [v] if isinstance(v, dict) else []):
                    if isinstance(it, dict): it.pop("_w", None); it.pop("_lw", None)

def text_shapes(spec):
    """6 Nov 2026: a drawing field that must be one text line sometimes comes back from the AI as a {h, t} card
    (tree root in Ch 3 P5) and the whole render crashed ("t.split is not a function"). Keep its heading."""
    for sc in spec.get("scenes") or []:
        for l in (sc.get("data") or {}).get("layers") or []:
            for k in ("root", "title", "sub", "name", "role", "stamp"):
                v = l.get(k)
                if isinstance(v, dict) and not ({"en", "te"} >= set(v)):
                    l[k] = v.get("h") or v.get("t") or {"en": "", "te": ""}

def sync_spec(spec, report=None):
    text_shapes(spec)
    n = sum(sync_scene(sc) for sc in spec.get("scenes") or [])
    for sc in spec.get("scenes") or []: no_empty_picture(sc)
    if report is not None: report += timing_report(spec)
    strip_marks(spec)
    return n

if __name__ == "__main__":
    # python3 sync.py <spec.json> ...           rewrite the timing
    # python3 sync.py --check <spec.json> ...   also exit 1 if any element shows before the clip that says it
    check = "--check" in sys.argv; bad = []
    for f in [a for a in sys.argv[1:] if a != "--check"]:
        s = json.load(open(f, encoding="utf-8")); rep = []; n = sync_spec(s, rep); bad += rep
        json.dump(s, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"{f}: {n} elements timed to their words; shown early: {len(rep)}")
    for b in bad[:40]: print("EARLY", b)
    sys.exit(1 if check and bad else 0)
