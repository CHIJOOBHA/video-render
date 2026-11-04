#!/usr/bin/env python3
"""New English words the voice can't say yet -> their sound in Telugu letters (AI-made; checked by tools/pron_listen.py before voicing).
Usage: python3 lex_fill.py <part.json> <missing words, space separated> <out_lexicon.json>
The lexicon value is the Telugu spelling (tools/lexicon-en.json rule): the English voice then says it with Telugu sounds."""
import json, re, sys
sys.path.insert(0, __import__("os").path.dirname(__file__))
from llm import ask, LOG

part, words, out = json.load(open(sys.argv[1], encoding="utf-8")), sys.argv[2].split(), sys.argv[3]
if not words: sys.exit(0)
ans = ask("These English words appear in an English lesson; the matching Telugu notes are below. For EACH word give how it "
            "SOUNDS, written in Telugu letters, so a voice reading the Telugu letters says the SAME word (a transliteration of the "
            "sound — NEVER a translation: 'India' -> 'ఇండియా', never 'భారతదేశం'; 'Sriharikota' -> 'శ్రీహరికోట'). Use the "
            "Telugu notes' spelling only when it is the same word's sound. Every vowel written. Return ONLY JSON {\"word\": \"తెలుగు\"}.\n\nWORDS: "
            + " ".join(words) + "\n\n# TELUGU NOTES\n" + part["te"][:60000], "lexicon", prefer=("anthropic", "deepseek", "gemini"))
want = {w.lower() for w in words}
# only the words asked for (4 Nov 2026: extra keys such as 'us' -> అమెరికా replaced ordinary English in the voice)
lex = {k.lower(): v for k, v in (ans or {}).items() if k.lower() in want and isinstance(v, str) and re.fullmatch(r"[ఀ-౿‌\s'-]+", v.strip())}
json.dump(lex, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"lexicon: {len(lex)}/{len(words)} words", "missing:", [w for w in words if w.lower() not in lex], "|", "; ".join(LOG))
