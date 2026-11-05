#!/usr/bin/env python3
"""Telugu pass (4 Nov 2026): write the Telugu lines into an English factory spec — the SAME scenes, beats and pictures —
from the TELUGU notes (their names, spellings and wording; not a translation of the English). Gemini first (best Telugu).
Usage: python3 te_fill.py <spec.json in/out> <part.json> <studio_dir> <report.md>"""
import json, os, re, sys
from llm import ask, LOG
import lib

TE = re.compile(r"[ఀ-౿]")
# 5 Nov 2026: ten parts at once used up Gemini's free daily quota and the rest fell to the weakest 'lite' model, which left beats
# empty. Telugu is written by the Anthropic writer first, Gemini second (its lite models are never used for Telugu).
PREFER = ("anthropic", "gemini")
import llm
_gm = llm._g_models
llm._g_models = lambda key: [m for m in _gm(key) if "lite" not in m]

def strings(v, out):
    """Every {en, te} pair inside a scene's data (screen text) -> list of the pair dicts."""
    if isinstance(v, dict):
        if set(v) == {"en", "te"}: out.append(v); return out
        for x in v.values(): strings(x, out)
    elif isinstance(v, list):
        for x in v: strings(x, out)
    return out

def beat_errs(te):
    e = []
    if not isinstance(te, str) or not te.strip(): return ["empty"]
    if not TE.search(te): e.append("not Telugu")
    if re.search(r"\d", te): e.append("digits — write numbers as spoken Telugu words")
    if len(te.split()) > 45: e.append("too long — max about 20 words per sentence")
    return e

def main():
    spec_f, part_f, studio, rep = sys.argv[1:5]
    spec, part = json.load(open(spec_f, encoding="utf-8")), json.load(open(part_f, encoding="utf-8"))
    guide = open(os.path.join(studio, "guides/teacher-script.md"), encoding="utf-8").read()
    sp = os.path.join(studio, "guides/script-sample-te.md")
    if os.path.exists(sp):     # CHIJOBHA's own model script (5 Nov 2026): copy its style, never its facts
        guide += "\n\n# MODEL SCRIPT — write Telugu exactly in THIS style (style only, never its facts)\n" + open(sp, encoding="utf-8").read()
    locked = open(os.path.join(studio, "CLAUDE.md"), encoding="utf-8").read().split("## Common rules")[0]
    scenes = spec["scenes"]
    # Telugu of a scene whose English is identical to one already done (any subject) is reused from the library
    keys, todo = {}, []
    for sc in scenes:
        ens = [s["text"]["en"] for s in sc["sentences"]]
        keys[sc["id"]] = lib.key("te2|" + json.dumps([ens, sorted({p["en"] for p in strings(sc["data"], [])})]))
        hit = lib.get("te", keys[sc["id"]])
        if hit and len(hit.get("beats") or []) == len(ens):
            for s, te in zip(sc["sentences"], hit["beats"]): s["text"]["te"] = te
            for p in strings(sc["data"], []):
                h = hit.get("screen", {}).get(p["en"])
                if h and sorted(re.findall(r"\d+", p["en"])) == sorted(re.findall(r"\d+", h)): p["te"] = h   # digits kept, else written again
            LOG.append(f"{sc['id']}: Telugu reused from the library")
        if any(not s["text"]["te"] for s in sc["sentences"]) or any(p["en"].strip() and not p["te"] for p in strings(sc["data"], [])): todo.append(sc)
    groups, cur, n = [], [], 0
    for sc in todo:
        if cur and n + len(sc["sentences"]) > 22: groups.append(cur); cur, n = [], 0
        cur.append(sc); n += len(sc["sentences"])
    if cur: groups.append(cur)
    bad_total, prev = [], []
    for gi, g in enumerate(groups):
        ask_scenes = [{"id": sc["id"], "beats": [s["text"]["en"] for s in sc["sentences"]],
                       "screen": sorted({p["en"] for p in strings(sc["data"], []) if p["en"].strip() and not p["te"]})} for sc in g]
        base = ("You write the TELUGU edition of a Roach Academia video lesson (APPSC exam class). The English lesson below is already "
                "made; the Telugu video uses the SAME scenes, beats and pictures, so write one Telugu beat for every English beat "
                "(same point, same order) and a Telugu version of every on-screen text.\n\n# RULES\n" + locked + "\n\n" + guide +
                "\n\nTelugu facts, names and spellings come from the TELUGU NOTES below (where the English and Telugu notes differ, "
                "follow the Telugu notes). Every point of the Telugu notes that the English beat teaches must be in its Telugu beat — "
                "completely, with the Telugu notes' own wording, numbers and names; never drop a point to shorten. Write it the way "
                "the MODEL SCRIPT talks: a Telugu teacher in class, Telugu mixed with the English words students use, greeting "
                "'నమస్కారం!' where the English greets, 'కామన్ మిస్టేక్ అలర్ట్! … ఎగ్జాంపుల్ 1 (కరెక్ట్) … ఎగ్జాంపుల్ 2 (రాంగ్) … "
                "ఈ తప్పు చేయకండి.' where the English has a Common Mistake Alert. Spoken Telugu: respectful forms for revered people, numbers and "
                "years as spoken Telugu words (రెండు వేల ఇరవై ఐదు), no digits. On-screen text: short Telugu, and every number written in DIGITS exactly as in the English (1 March 2014 -> 1 మార్చి 2014).\n\n"
                "# TELUGU NOTES\n" + part["te"] + "\n\n# JUST SAID\n" + json.dumps(prev[-3:], ensure_ascii=False) +
                "\n\n# ENGLISH SCENES TO MATCH\n" + json.dumps(ask_scenes, ensure_ascii=False) +
                '\n\nReturn ONLY JSON: {"<scene id>": {"beats": ["తెలుగు", ...same count...], "screen": {"<english text>": "తెలుగు"}}}')
        fixes, why = {}, {}
        for rnd in range(5):
            out = ask(base if rnd == 0 else base + "\n\n# FIX ONLY THESE\n" + json.dumps(fixes, ensure_ascii=False),
                      f"te group {gi + 1}/{len(groups)} round {rnd}", prefer=PREFER)
            if not isinstance(out, dict): continue
            fixes = {}
            for sc in g:
                o = out.get(sc["id"]) or {}
                beats, screen = o.get("beats"), o.get("screen") or {}
                if isinstance(beats, list) and len(beats) == len(sc["sentences"]):
                    for k, (s, te) in enumerate(zip(sc["sentences"], beats)):
                        if not s["text"]["te"] and not beat_errs(te): s["text"]["te"] = te.strip()
                        elif not s["text"]["te"]: why[(sc["id"], k)] = beat_errs(te)
                elif isinstance(beats, dict):                      # repair answers: {"beat number": "..."}
                    for k, te in beats.items():
                        if str(k).isdigit() and int(k) < len(sc["sentences"]) and not sc["sentences"][int(k)]["text"]["te"]:
                            if not beat_errs(te): sc["sentences"][int(k)]["text"]["te"] = te.strip()
                            else: why[(sc["id"], int(k))] = beat_errs(te)
                for p in strings(sc["data"], []):
                    if not p["te"] and isinstance(screen.get(p["en"]), str) and screen[p["en"]].strip():
                        t = screen[p["en"]].strip()
                        # numbers on screen stay digits, exactly as in English (4 Nov 2026: a date shown as words overflowed)
                        if sorted(re.findall(r"\d+", p["en"])) == sorted(re.findall(r"\d+", t)): p["te"] = t
                # 5 Nov 2026: the writer is told WHY its last answer for a beat was refused (digits, too long…)
                miss_b = {k: s["text"]["en"] + (f"  [your last answer was refused: {', '.join(why[(sc['id'], k)])}]" if (sc["id"], k) in why else "")
                          for k, s in enumerate(sc["sentences"]) if not s["text"]["te"]}
                miss_s = sorted({p["en"] for p in strings(sc["data"], []) if p["en"].strip() and not p["te"]})
                if miss_b or miss_s: fixes[sc["id"]] = {"beats (answer as {\"number\": \"తెలుగు\"})": miss_b, "screen": miss_s}
            if not fixes: break
        for sc in g:
            for p in strings(sc["data"], []):
                if not p["te"]: p["te"] = p["en"]                  # an untranslated label shows the English (logged)
            prev += [s["text"]["te"] for s in sc["sentences"] if s["text"]["te"]]
            bad_total += [f"{sc['id']} beat {k}" for k, s in enumerate(sc["sentences"]) if not s["text"]["te"]]
            if all(s["text"]["te"] for s in sc["sentences"]):
                lib.put("te", keys[sc["id"]], {"beats": [s["text"]["te"] for s in sc["sentences"]],
                                               "screen": {p["en"]: p["te"] for p in strings(sc["data"], []) if p["te"]}})
    # ledger (5 Nov 2026): every point of the TELUGU notes of this part must be taught by the Telugu beats
    import ledger
    from gen_spec import sec_ids
    ledger.SKIP = sec_ids(part["te"], part.get("chapter"))
    led = ledger.points(part["te"], "te") if not bad_total else []
    miss, rows, adds = [], [], []
    for rnd in range(3):
        if not led: break
        beats = [(f"{sc['id']}#{k}", s["text"]["te"]) for sc in scenes for k, s in enumerate(sc["sentences"])]
        miss, rows = ledger.missing(led, beats, "te")
        adds = ledger.added(part["te"], beats, "te", prev=part.get("prev_te") or part.get("prev"))
        if (not miss and not adds) or rnd == 2: break
        idx = [{"id": f"{sc['id']}#{k}", "en": s["text"]["en"], "te": s["text"]["te"]} for sc in scenes for k, s in enumerate(sc["sentences"])]
        out = ask("The Telugu lesson below misses these points of the TELUGU NOTES (or teaches them wrongly):\n" +
                  "\n".join(f"- {p['point']}" for p in miss) +
                  ("\n\nand these beats add or change something the Telugu notes do not say (fix them: say it exactly as the notes "
                   "say, remove what the notes do not give, teach labels as spoken sentences, drop repeats):\n" +
                   "\n".join(f"- {a['beat']} {a['kind']}: \"{a['words']}\" (notes: {a['notes_say']})" for a in adds) if adds else "") +
                  "\n\nAdd each one, completely and exactly as the Telugu notes say, into the Telugu beat where its English beat "
                  "teaches it (rewrite only those beats; keep everything else; same style; no digits; numbers as Telugu words). "
                  'Return ONLY JSON: {"<beat id>": "new Telugu beat", …}\n\n# RULES\n' + guide + "\n\n# TELUGU NOTES\n" +
                  part["te"] + "\n\n# BEATS\n" + json.dumps(idx, ensure_ascii=False), f"te ledger fix {rnd}", prefer=PREFER)
        for bid, te in (out or {}).items():
            sid, _, k = str(bid).partition("#")
            for sc in scenes:
                if sc["id"] == sid and k.isdigit() and int(k) < len(sc["sentences"]) and isinstance(te, str) and not beat_errs(te):
                    sc["sentences"][int(k)]["text"]["te"] = te.strip()
    if adds: bad_total += [f"added/changed: {len(adds)} Telugu beats — " + "; ".join(f"{a['kind']} {a['words'][:50]}" for a in adds[:6])]
    if led and miss: bad_total += [f"ledger: {len(miss)} of {len(led)} Telugu notes points not taught — " + "; ".join(p["point"][:70] for p in miss[:6])]
    if not led and not bad_total: bad_total.append("ledger: no Telugu ledger could be made")
    if not bad_total: spec.pop("te_pending", None)
    from gen_spec import size_spec
    size_spec(spec)                      # Telugu words are longer: boxes and pages re-fitted
    json.dump(spec, open(spec_f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with open(rep, "a", encoding="utf-8") as f:
        f.write(f"\n# Telugu — {'READY' if not bad_total else 'BLOCKED'}\nproblems: {bad_total or 'none'}\n\n"
                f"## Telugu ledger + coverage ({len(led)} points)\n| # | point | beat |\n|---|---|---|\n" + "\n".join(rows) + "\n\n## Log\n" +
                "\n".join(f"- {l}" for l in LOG) + "\n")
    print("TE READY" if not bad_total else f"TE BLOCKED {len(bad_total)} beats")
    sys.exit(0 if not bad_total else 3)

if __name__ == "__main__":
    main()
