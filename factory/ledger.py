#!/usr/bin/env python3
"""Ledger + coverage check (LOCKED rule: every point of the notes is taught — none missing). 5 Nov 2026.
CHIJOBHA: "don't miss any single point from the notes". The name/number check in gen_spec cannot see a missing *statement*
(a reworded answer key, a trap-box item, a timeline line), so here an AI first numbers every point of a notes piece (the
ledger), then maps each point to the beat that teaches it; code then re-checks each claimed match (its numbers and names
must be in that beat or the one next to it). Unmatched points go back to the writer. Contains no course content.
  points(notes, lang)                  -> [{"n": 1, "point": "...", "keys": ["2026", "BRICS"]}, ...]
  cover(ledger, beats, lang)           -> {n: beat_id or None}   (beats = [(id, text), ...])
  missing(ledger, beats, lang)         -> (missing points, table rows)"""
import json, re
from llm import ask, LOG
import lib

def points(notes, lang):
    k = lib.key("ledger|" + lang + "|" + notes)
    hit = lib.get("ledger", k)
    if hit and isinstance(hit.get("points"), list) and hit["points"]: return hit["points"]
    ans = ask("You make the LEDGER of a piece of exam notes: number EVERY separate point a student must learn — each fact, "
              "date, number, name, definition, each bullet, each table row, each line of a timeline/tree block, each figure "
              "caption, each cross-reference ('see Chapter 10'), each exam-box line (past questions with their year, question "
              "number, statements and answer key), each trap/confusion-box item, each mnemonic. One point = one statement. "
              "Skip only practice MCQs at the end of a chapter and pure formatting. Keep the notes' own wording. For each point "
              "give `keys`: the exact numbers, dates, names and terms in it that must be heard (as written in the notes)."
              f"\nNotes language: {'Telugu' if lang == 'te' else 'English'}.\n\nReturn ONLY JSON: "
              '{"points": [{"n": 1, "point": "…", "keys": ["…"]}]}\n\n# NOTES\n' + notes, f"ledger {lang}",
              prefer=("anthropic", "gemini", "deepseek"))
    pts = [p for p in (ans or {}).get("points") or [] if isinstance(p, dict) and isinstance(p.get("point"), str)]
    for i, p in enumerate(pts): p["n"] = i + 1; p["keys"] = [str(x) for x in p.get("keys") or [] if str(x).strip()]
    if pts: lib.put("ledger", k, {"points": pts})
    return pts

def _norm(s): return re.sub(r"[\s\-–,]+", " ", s.lower()).strip()

def _heard(key, text, lang):
    """A key is heard if each of its parts is in the text: words by their stem (Telugu endings change: 'దేశాలు'/'దేశాల'),
    numbers in any spoken form ('Q4' = 'question four', '16–20' = 'sixteen … twenty', '21st' = 'twenty-first'); Telugu numbers
    are spoken as Telugu words, so for Telugu they are left to the AI mapping step."""
    t = _norm(text)
    if _norm(key) in t: return True
    try:
        from gen_spec import num_forms
    except Exception:
        num_forms = lambda n: {n}
    for tok in re.findall(r"\d[\d,]*(?:\.\d+)?|[^\W\d_]+", key):
        if re.match(r"\d", tok):
            if lang == "te": continue
            n = tok.rstrip(",")
            if n in t or any(f in t for f in num_forms(n)): continue
            return False
        if tok.lower() in ("q", "st", "nd", "rd", "th", "the", "and", "of", "in", "a"): continue
        if re.fullmatch(r"[A-Z]{2,}", tok) and " ".join(tok).lower() in t: continue
        stem = tok.lower()[:max(3, len(tok) - 2)]
        if stem in t: continue
        return False
    return True

def cover(ledger, beats, lang):
    if not ledger: return {}
    lines = "\n".join(f"[{i}] {t}" for i, (_, t) in enumerate(beats))
    pts = "\n".join(f"{p['n']}. {p['point']}" for p in ledger)
    ans = ask("Below are the numbered POINTS of a notes piece and the numbered BEATS of a spoken lesson made from it. For each "
              "point give the index of the beat that teaches it COMPLETELY and CORRECTLY (same facts, same numbers, same names, "
              "same meaning — a reworded answer, a changed number, a point only half taught = not taught), or null. Be strict."
              '\n\nReturn ONLY JSON: {"map": {"1": 3, "2": null, …}}\n\n# POINTS\n' + pts + "\n\n# BEATS\n" + lines,
              f"coverage {lang}", prefer=("anthropic", "gemini", "deepseek"))
    m = (ans or {}).get("map") or {}
    out = {}
    for p in ledger:
        b = m.get(str(p["n"]))
        if not isinstance(b, int) or not 0 <= b < len(beats): out[p["n"]] = None; continue
        near = " ".join(beats[j][1] for j in range(max(0, b - 2), min(len(beats), b + 3)))   # a point may span a few beats
        out[p["n"]] = beats[b][0] if all(_heard(k, near, lang) for k in p["keys"]) else None
    return out

def missing(ledger, beats, lang):
    cov = cover(ledger, beats, lang)
    miss = [p for p in ledger if not cov.get(p["n"])]
    rows = [f"| {p['n']} | {p['point'][:110].replace('|', '/')} | {cov.get(p['n']) or 'MISSING'} |" for p in ledger]
    LOG.append(f"ledger {lang}: {len(ledger)} points, {len(miss)} not taught")
    return miss, rows
