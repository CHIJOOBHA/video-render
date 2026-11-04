#!/usr/bin/env python3
"""Telugu pass (4 Nov 2026): write the Telugu lines into an English factory spec — the SAME scenes, beats and pictures —
from the TELUGU notes (their names, spellings and wording; not a translation of the English). Gemini first (best Telugu).
Usage: python3 te_fill.py <spec.json in/out> <part.json> <studio_dir> <report.md>"""
import json, os, re, sys
from llm import ask, LOG

TE = re.compile(r"[ఀ-౿]")

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
    locked = open(os.path.join(studio, "CLAUDE.md"), encoding="utf-8").read().split("## Common rules")[0]
    scenes = spec["scenes"]
    groups, cur, n = [], [], 0
    for sc in scenes:
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
                "follow the Telugu notes). Spoken Telugu: natural classroom Telugu, respectful forms for revered people, numbers and "
                "years as spoken Telugu words (రెండు వేల ఇరవై ఐదు), no digits. On-screen text: short Telugu; digits allowed there.\n\n"
                "# TELUGU NOTES\n" + part["te"] + "\n\n# JUST SAID\n" + json.dumps(prev[-3:], ensure_ascii=False) +
                "\n\n# ENGLISH SCENES TO MATCH\n" + json.dumps(ask_scenes, ensure_ascii=False) +
                '\n\nReturn ONLY JSON: {"<scene id>": {"beats": ["తెలుగు", ...same count...], "screen": {"<english text>": "తెలుగు"}}}')
        fixes = {}
        for rnd in range(3):
            out = ask(base if rnd == 0 else base + "\n\n# FIX ONLY THESE\n" + json.dumps(fixes, ensure_ascii=False),
                      f"te group {gi + 1}/{len(groups)} round {rnd}", prefer=("gemini", "anthropic"))   # Telugu: Gemini only (best Telugu); waits for quota
            if not isinstance(out, dict): continue
            fixes = {}
            for sc in g:
                o = out.get(sc["id"]) or {}
                beats, screen = o.get("beats"), o.get("screen") or {}
                if isinstance(beats, list) and len(beats) == len(sc["sentences"]):
                    for k, (s, te) in enumerate(zip(sc["sentences"], beats)):
                        if not s["text"]["te"] and not beat_errs(te): s["text"]["te"] = te.strip()
                elif isinstance(beats, dict):                      # repair answers: {"beat number": "..."}
                    for k, te in beats.items():
                        if str(k).isdigit() and int(k) < len(sc["sentences"]) and not sc["sentences"][int(k)]["text"]["te"] and not beat_errs(te):
                            sc["sentences"][int(k)]["text"]["te"] = te.strip()
                for p in strings(sc["data"], []):
                    if not p["te"] and isinstance(screen.get(p["en"]), str) and screen[p["en"]].strip(): p["te"] = screen[p["en"]].strip()
                miss_b = {k: s["text"]["en"] for k, s in enumerate(sc["sentences"]) if not s["text"]["te"]}
                miss_s = sorted({p["en"] for p in strings(sc["data"], []) if p["en"].strip() and not p["te"]})
                if miss_b or miss_s: fixes[sc["id"]] = {"beats (answer as {\"number\": \"తెలుగు\"})": miss_b, "screen": miss_s}
            if not fixes: break
        for sc in g:
            for p in strings(sc["data"], []):
                if not p["te"]: p["te"] = p["en"]                  # an untranslated label shows the English (logged)
            prev += [s["text"]["te"] for s in sc["sentences"] if s["text"]["te"]]
            bad_total += [f"{sc['id']} beat {k}" for k, s in enumerate(sc["sentences"]) if not s["text"]["te"]]
    if not bad_total: spec.pop("te_pending", None)
    json.dump(spec, open(spec_f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    with open(rep, "a", encoding="utf-8") as f:
        f.write(f"\n# Telugu — {'READY' if not bad_total else 'BLOCKED'}\nbeats without Telugu: {bad_total or 'none'}\n\n## Log\n" +
                "\n".join(f"- {l}" for l in LOG) + "\n")
    print("TE READY" if not bad_total else f"TE BLOCKED {len(bad_total)} beats")
    sys.exit(0 if not bad_total else 3)

if __name__ == "__main__":
    main()
