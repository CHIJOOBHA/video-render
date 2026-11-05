#!/usr/bin/env python3
"""Ledger + coverage check (LOCKED rule: every point of the notes is taught — none missing). 5 Nov 2026.
CHIJOBHA: "don't miss any single point from the notes". The name/number check in gen_spec cannot see a missing *statement*
(a reworded answer key, a trap-box item, a timeline line), so here an AI first numbers every point of a notes piece (the
ledger), then maps each point to the beat that teaches it; code then re-checks each claimed match (its numbers and names
must be in that beat or the one next to it). Unmatched points go back to the writer. Contains no course content.
  points(notes, lang)                  -> [{"n": 1, "point": "...", "keys": ["2026", "BRICS"]}, ...]
  cover(ledger, beats, lang)           -> {n: beat_id or None}   (beats = [(id, text), ...])
  missing(ledger, beats, lang)         -> (missing points, table rows)"""
import json, re, unicodedata
from llm import ask, LOG
import lib

def points(notes, lang):
    k = lib.key("ledger2|" + lang + "|" + notes)
    hit = lib.get("ledger", k)
    if hit and isinstance(hit.get("points"), list) and hit["points"]: return hit["points"]
    ans = ask("You make the LEDGER of a piece of exam notes: number EVERY separate point a student must learn — each fact, "
              "date, number, name, definition, each bullet, each table row, each line of a timeline/tree block, each figure "
              "caption, each cross-reference ('see Chapter 10'), each exam-box line (past questions with their year, question "
              "number, statements and answer key), each trap/confusion-box item, each mnemonic. One point = one statement. "
              "A box title or heading on its own ('Trap box: Don't confuse X vs Y', 'Asked in 2023') is NOT a point — the items under "
              "it are. Skip only practice MCQs at the end of a chapter and pure formatting. Keep the notes' own wording. For each point "
              "give `keys`: the exact numbers, dates, names and terms in it that must be heard (as written in the notes) — never a "
              "section or table number (2.4, 3.13, Table 1.2): those are not spoken."
              f"\nNotes language: {'Telugu' if lang == 'te' else 'English'}.\n\nReturn ONLY JSON: "
              '{"points": [{"n": 1, "point": "…", "keys": ["…"]}]}\n\n# NOTES\n' + notes, f"ledger {lang}",
              prefer=("anthropic", "gemini", "deepseek"))
    pts = [p for p in (ans or {}).get("points") or [] if isinstance(p, dict) and isinstance(p.get("point"), str)]
    for i, p in enumerate(pts): p["n"] = i + 1; p["keys"] = [str(x) for x in p.get("keys") or [] if str(x).strip()]
    if pts: lib.put("ledger", k, {"points": pts})
    return pts

SKIP = set()     # section / table ids of the part (set by the writer): never required to be spoken

def _norm(s):   # 'one hundred and forty' = 'one hundred forty' (num2words leaves out the 'and'); 'Évian' = 'Evian'
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)) if not re.search(r"[ఀ-౿]", s) else s
    return re.sub(r" and ", " ", " " + re.sub(r"[\s\-–,]+", " ", s.lower()).strip() + " ").strip()

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
    # only hard facts are re-checked by code: numbers, and names/abbreviations (capitalised Latin words; a one-word Telugu name).
    # Ordinary words may be said differently ("chair" / "presidency"); whether the meaning is right is the AI mapping's job.
    single_te = lang == "te" and re.fullmatch(r"[ఀ-౿]+", key.strip() or "x")
    for tok in re.findall(r"\d[\d,]*(?:\.\d+)?|[^\W\d_]+", key):
        if re.match(r"\d", tok):
            if lang == "te" or tok in SKIP: continue
            n = tok.rstrip(",")
            if n in t or any(f in t for f in num_forms(n)): continue
            return False
        if re.fullmatch(r"[ఀ-౿]+", tok):
            if single_te and tok[:max(3, len(tok) - 2)] not in t: return False
            continue
        if not tok[:1].isupper() or tok.lower() in ("q", "the", "and", "of", "in", "a"): continue
        if re.fullmatch(r"[A-Z]{2,}", tok) and " ".join(tok).lower() in t: continue
        if tok.lower()[:max(3, len(tok) - 2)] in t: continue
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

def _recheck(pts, beats, lang):
    """A second, focused look at only the points called missing (one long mapping call is noisy)."""
    lines = "\n".join(f"[{i}] {t}" for i, (_, t) in enumerate(beats))
    ans = ask("For EACH point below, find the beat(s) of the lesson that teach it completely and correctly (same facts, numbers, "
              "names, meaning). Quote the words that teach it. If it is not taught, or taught wrongly or only half, say null."
              '\n\nReturn ONLY JSON: {"found": {"<point n>": {"beat": 3, "quote": "…"} or null}}\n\n# POINTS\n' +
              "\n".join(f"{p['n']}. {p['point']}" for p in pts) + "\n\n# BEATS\n" + lines, f"coverage recheck {lang}",
              prefer=("anthropic", "gemini", "deepseek"))
    f = (ans or {}).get("found") or {}; ok = {}
    for p in pts:
        r = f.get(str(p["n"]))
        b = r.get("beat") if isinstance(r, dict) else None
        if isinstance(b, int) and 0 <= b < len(beats):
            near = " ".join(beats[j][1] for j in range(max(0, b - 2), min(len(beats), b + 3)))
            if all(_heard(k, near, lang) for k in p["keys"]): ok[p["n"]] = beats[b][0]
    return ok

def missing(ledger, beats, lang):
    cov = cover(ledger, beats, lang)
    first = [p for p in ledger if not cov.get(p["n"])]
    if first: cov.update(_recheck(first, beats, lang))
    miss = [p for p in ledger if not cov.get(p["n"])]
    rows = [f"| {p['n']} | {p['point'][:110].replace('|', '/')} | {cov.get(p['n']) or 'MISSING'} |" for p in ledger]
    LOG.append(f"ledger {lang}: {len(ledger)} points, {len(miss)} not taught")
    return miss, rows

def added(notes, beats, lang, prev=None):
    """Nothing added, nothing changed (LOCKED rule), 5 Nov 2026: every claim the lesson makes must be in the notes, unchanged.
    The AI lists beats that add a fact / number / name / date / advice / conclusion the notes do not give, change a fact's
    meaning ('were in 2012' -> 'came after 2012'), read a box label or heading aloud, or repeat a point already taught."""
    if not beats: return []
    lines = "\n".join(f"[{i}] {t}" for i, (_, t) in enumerate(beats))
    ans = ask("You check a spoken lesson against its notes, strictly. List every beat that does any of these:\n"
              "A) ADDED — states a fact, number, name, date, rule, exam advice or conclusion ABOUT THE SUBJECT that the notes "
              "do not give;\n"
              "B) CHANGED — says something that differs from the notes in meaning (a fact, number, date, order, who did what);\n"
              "C) LABEL — reads a box title or heading aloud as a title ('the trap box is titled…', 'Asked in 2023 Paper-I Q4:') "
              "instead of teaching it in spoken sentences;\n"
              "D) REPEAT — teaches the same point IN FULL a third time or more.\n"
              "These are FINE, never flag them: classroom remarks that state no subject fact ('many students find this hard', "
              "'this is a big one', 'that is the whole trap', 'the chair was not just a title'); greetings; 'what is coming' and "
              "'last time we saw' lines naming topics of the notes; a short 'so…' recap of what was just taught; the key line "
              "said again; the end recap; explaining a notes term in plain words; linking two notes facts; a story or example "
              "that only uses notes facts; saying where students slip when the notes have a trap/confusion box.\n"
              "Return ONLY JSON: "
              '{"problems": [{"beat": 3, "kind": "ADDED|CHANGED|LABEL|REPEAT", "words": "…", "notes_say": "…"}]}'
              f"\n\n# NOTES ({'Telugu' if lang == 'te' else 'English'})\n" + notes +
              (f"\n\n# THE LAST PART COVERED (naming these topics in a 'last time' line is fine)\n{prev}" if prev else "") +
              "\n\n# BEATS\n" + lines,
              f"added check {lang}", prefer=("anthropic", "gemini", "deepseek"))
    # second, focused look (5 Nov 2026): one long check flags harmless teacher lines; each problem must be confirmed
    ps = [p for p in (ans or {}).get("problems") or [] if isinstance(p, dict) and isinstance(p.get("beat"), int)
          and 0 <= p["beat"] < len(beats) and p.get("kind") in ("ADDED", "CHANGED", "LABEL", "REPEAT")]
    if ps:
        c = ask("A checker says these lesson sentences break the rule 'nothing added, nothing changed, no titles read aloud, no "
                "point taught in full three times'. For EACH, look at the notes and the whole lesson and answer true only if it "
                "really does: it states a subject fact/number/name/date/advice the notes do not have, or says a notes fact "
                "differently in meaning, or reads a title aloud, or is a third full teaching. A teacher remark with no subject "
                "fact, a recap, a 'so…' summary, the key line said again, or a plain-words explanation is false."
                '\n\nReturn ONLY JSON: {"real": {"0": true, "1": false, …}}\n\n# CLAIMS\n' +
                "\n".join(f"[{i}] beat [{p['beat']}] {p['kind']}: \"{p.get('words', '')}\" (checker: notes say \"{p.get('notes_say', '')}\")"
                          for i, p in enumerate(ps)) +
                f"\n\n# NOTES ({'Telugu' if lang == 'te' else 'English'})\n" + notes + "\n\n# BEATS\n" + lines,
                f"added confirm {lang}", prefer=("anthropic", "gemini", "deepseek"))
        real = (c or {}).get("real") or {}
        ps = [p for i, p in enumerate(ps) if real.get(str(i), True) is not False]
    ans = {"problems": ps}
    out = []
    for p in (ans or {}).get("problems") or []:
        b = p.get("beat") if isinstance(p, dict) else None
        if isinstance(b, int) and 0 <= b < len(beats) and p.get("kind") in ("ADDED", "CHANGED", "LABEL", "REPEAT"):
            out.append({"beat": beats[b][0], "kind": p["kind"], "words": str(p.get("words", ""))[:200], "notes_say": str(p.get("notes_say", ""))[:200]})
    LOG.append(f"added check {lang}: {len(out)} problems")
    return out
