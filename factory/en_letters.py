#!/usr/bin/env python3
"""English in CHIJOBHA's own voice (5 Nov 2026, his samples E/G): the voice engine is IndicF5 (his Telugu voice engine),
which reads Telugu letters perfectly but garbles English letters. So every English line is written in Telugu letters
the way he says English ("ప్రిపేరింగ్ ఫర్ కాంపిటీటివ్ ఎగ్జామ్స్"), with commas only where an English speaker breathes.
Screen text never changes — only what the voice reads. The render's English listening check (qa_final) then hears the
finished video against the ORIGINAL English lines, so a word that came out wrong blocks the video.
  python3 factory/en_letters.py <sentences.json (English)> <out sentences-voice.json>
Same keys and line counts as the input."""
import json, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from llm import ask, LOG

LATIN = re.compile(r"[A-Za-z0-9]")
TE = re.compile(r"[ఀ-౿]")

RULES = """You write ENGLISH sentences in TELUGU LETTERS, exactly the way an educated Telugu teacher says that English
sentence aloud in class (Indian English accent), so a Telugu voice engine can read it. It is still ENGLISH — never
translate into Telugu.
- Every word, in the same order. Add nothing, drop nothing.
- Numbers, years, dates, money, percentages and symbols as the spoken English words:
  2026 -> టూ థౌజండ్ ట్వెంటీ సిక్స్ ; 12 September -> ట్వెల్ఫ్త్ సెప్టెంబర్ ; 34% -> థర్టీ ఫోర్ పర్సెంట్ ; Rs 500 -> ఫైవ్ హండ్రెడ్ రూపీస్
- Letter-by-letter abbreviations spelled as letters: APPSC -> ఏ పీ పీ ఎస్ సీ ; UN -> యూ ఎన్ . Acronyms said as words stay
  words: BRICS -> బ్రిక్స్ ; NATO -> నాటో ; ASEAN -> ఆసియాన్ .
- Indian names, places and Sanskrit/Telugu words in their normal Telugu spelling: Narendra Modi -> నరేంద్ర మోదీ ;
  Bharat Mandapam -> భారత్ మండపం ; Tirumala -> తిరుమల .
- Natural English phrasing: keep . ? ! at the end. A comma ONLY where a native English speaker pauses for breath (between
  clauses, after an opening phrase, around a date or a list). Remove any comma that splits a phrase in the middle
  ("you already know, how" -> no comma). A long sentence may get one comma at its natural breath point.
- Output only Telugu letters and punctuation: no English letters, no digits.
Example: "Then you already know how confusing international summits can be in current affairs." ->
"దెన్ యూ ఆల్రెడీ నో హౌ కన్ఫ్యూజింగ్ ఇంటర్నేషనల్ సమ్మిట్స్ కెన్ బి ఇన్ కరెంట్ అఫైర్స్."
Example: "The 18th BRICS summit was held on 12-13 September 2026 at Bharat Mandapam, New Delhi." ->
"ది ఎయిటీన్త్ బ్రిక్స్ సమ్మిట్ వాజ్ హెల్డ్ ఆన్ ట్వెల్వ్ టు థర్టీన్ సెప్టెంబర్, టూ థౌజండ్ ట్వెంటీ సిక్స్, ఎట్ భారత్ మండపం, న్యూ ఢిల్లీ."
"""


def bad(en, te):
    if not isinstance(te, str) or not te.strip(): return "empty"
    if LATIN.search(te): return "English letters or digits left"
    if not TE.search(te): return "no Telugu letters"
    ne, nt = len(re.findall(r"[A-Za-z]+|\d+", en)), len(te.split())
    if ne and not (0.6 <= nt / ne <= 2.6): return f"{nt} words for {ne} English words — something added or dropped"
    return None


def main():
    src, out = sys.argv[1:3]
    sents = json.load(open(src, encoding="utf-8"))
    flat = [(sc, i, s) for sc, ss in sents.items() for i, s in enumerate(ss)]
    # no per-line library lookup (5 Nov 2026): each miss retried for ~15 s, 103 lines = 26 min before any AI call.
    # A whole video is ~3 quick AI calls, so lines are simply written fresh.
    res, todo = {}, list(flat)
    LOG.append(f"{len(flat)} lines to write in Telugu letters")
    for b in range(0, len(todo), 40):
        batch = todo[b:b + 40]
        ask_d = {str(n + 1): s for n, (_, _, s) in enumerate(batch)}
        fixes = {}
        for rnd in range(3):
            pend = {k: v for k, v in ask_d.items() if (batch[int(k) - 1][0], batch[int(k) - 1][1]) not in res}
            if not pend: break
            o = ask(RULES + ("\n\nThese came back wrong last time — fix them:\n" + json.dumps(fixes, ensure_ascii=False) if fixes else "")
                    + '\n\nReturn ONLY JSON {"<number>": "<Telugu letters>"} for every line:\n' + json.dumps(pend, ensure_ascii=False),
                    f"en letters {b // 40 + 1} round {rnd}", prefer=("anthropic", "deepseek", "gemini"))
            fixes = {}
            for k, s in pend.items():
                te = (o or {}).get(k) if isinstance(o, dict) else None
                why = bad(s, te)
                if why: fixes[k] = {"english": s, "problem": why}; continue
                sc, i, _ = batch[int(k) - 1]
                res[(sc, i)] = te.strip()
    left = [f"{sc}_{i}: {s[:70]}" for sc, i, s in flat if (sc, i) not in res]
    if left:
        print("::error title=English letters::" + f"{len(left)} lines could not be written in Telugu letters: " + " | ".join(left[:5]))
        sys.exit(1)
    json.dump({sc: [res[(sc, i)] for i in range(len(ss))] for sc, ss in sents.items()},
              open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"English in Telugu letters: {len(flat)} lines")


if __name__ == "__main__":
    main()
