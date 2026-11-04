#!/usr/bin/env python3
"""New English words the voice can't say yet -> their Telugu spelling, taken from the Telugu notes by Gemini.
Usage: python3 lex_fill.py <part.json> <missing words, space separated> <out_lexicon.json>
The lexicon value is the Telugu spelling (tools/lexicon-en.json rule): the English voice then says it with Telugu sounds."""
import json, re, sys
sys.path.insert(0, __import__("os").path.dirname(__file__))
from llm import ask, LOG

part, words, out = json.load(open(sys.argv[1], encoding="utf-8")), sys.argv[2].split(), sys.argv[3]
if not words: sys.exit(0)
ans = ask("These English words appear in an English lesson; the matching Telugu notes are below. For EACH word give how it "
            "is written in Telugu script — the spelling the Telugu notes use for that name or term when they have it, otherwise "
            "the natural Telugu spelling of how an Indian teacher says it (every vowel written; for an abbreviation spell the "
            "letters, e.g. 'APPSC' -> 'ఏపీపీఎస్సీ'). Return ONLY JSON {\"word\": \"తెలుగు\"}.\n\nWORDS: " + " ".join(words) +
            "\n\n# TELUGU NOTES\n" + part["te"][:60000], "lexicon", prefer=("deepseek", "gemini"))
lex = {k.lower(): v for k, v in (ans or {}).items() if isinstance(v, str) and re.fullmatch(r"[ఀ-౿‌\s'-]+", v.strip())}
json.dump(lex, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"lexicon: {len(lex)}/{len(words)} words", "missing:", [w for w in words if w.lower() not in lex], "|", "; ".join(LOG))
