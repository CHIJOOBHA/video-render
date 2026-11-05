#!/usr/bin/env python3
"""Cut one chapter (EN + TE notes) into video parts of about 11 minutes, at section boundaries.
Practice MCQs (and everything after them) are left out; Quick Revision goes with the last part.
Usage: python3 split.py <notes_dir> <subject> <chapter> <out_dir> [--words 1000]
  notes_dir/<subject>-en/chapters/chNN.md and <subject>-te/... (nt.py pull layout)
Writes out_dir/<id>.json per part ({"id","chapter","part","parts","chapter_title","sections","next","en","te","source"})
and prints the ids."""
import json, os, re, sys

def sections(md):
    md = re.split(r"\n## (?:Practice MCQs|Practice Questions|అభ్యాస|ప్రాక్టీస్|సాధన ప్రశ్నలు)[^\n]*\n", md)[0]
    title = re.search(r"^# (.+)$", md, re.M).group(1).strip()
    out, cur = [], None
    for line in md.split("\n"):
        m = re.match(r"## (.+)$", line)
        if m:
            cur = {"head": m.group(1).strip(), "body": [line]}; out.append(cur)
        elif cur: cur["body"].append(line)
    for s in out: s["body"] = "\n".join(s["body"]).strip()
    return title, out

def key(head):
    m = re.match(r"(\d+\.\d+)", head)
    return m.group(1) if m else ("QR" if out_is_recap(head) else head)

def out_is_recap(head):
    return bool(re.search(r"quick revision|త్వరిత|పునశ్చరణ|రివిజన్", head, re.I))

def main():
    nd, subj, ch, od = sys.argv[1], sys.argv[2], int(sys.argv[3]), sys.argv[4]
    target = int(sys.argv[sys.argv.index("--words") + 1]) if "--words" in sys.argv else 1000
    rd = lambda lang: open(f"{nd}/{subj}-{lang}/chapters/ch{ch:02d}.md", encoding="utf-8").read()
    t_en, en = sections(rd("en")); t_te, te = sections(rd("te"))
    if len(en) != len(te): sys.exit(f"ch{ch}: EN has {len(en)} sections, TE {len(te)} — needs a look")
    words = [len(re.findall(r"\w+", s["body"])) for s in en]
    total = sum(words); n = max(1, round(total / target))
    goal = total / n
    groups, cur, acc = [], [], 0
    for i, w in enumerate(words):
        recap = out_is_recap(en[i]["head"])
        if cur and not recap and acc + w / 2 > goal * (len(groups) + 1) and len(groups) < n - 1:
            groups.append(cur); cur = []
        cur.append(i); acc += w
    if cur: groups.append(cur)
    os.makedirs(od, exist_ok=True)
    base = re.sub(r"-\d{4}$", "", subj)
    short = {"current-events": "ce"}.get(base, base)
    if "--prefix" in sys.argv:                       # app prefix (bhg, ip, g2p...) -> part ids bhg3p1, g2px3p1 (x after a digit)
        pf = sys.argv[sys.argv.index("--prefix") + 1].replace("-", "")
        short = pf + ("x" if pf[-1].isdigit() else "")
    ids = []
    for p, g in enumerate(groups, 1):
        pid = f"{short}{ch}p{p}"
        nxt = "; ".join(en[i]["head"] for i in groups[p]) if p < len(groups) else None
        part = {"id": pid, "subject": subj, "chapter": ch, "part": p, "parts": len(groups),
                "chapter_title": re.sub(r"^Chapter \d+:\s*", "", t_en), "chapter_title_te": re.sub(r"^అధ్యాయం \d+:\s*", "", t_te),
                "sections": [en[i]["head"] for i in g], "next": nxt,
                "prev": "; ".join(en[i]["head"] for i in groups[p - 2]) if p > 1 else None,
                "prev_te": "; ".join(te[i]["head"] for i in groups[p - 2]) if p > 1 and all("head" in te[i] for i in groups[p - 2]) else None,
                "en": f"# {t_en}\n\n" + "\n\n".join(en[i]["body"] for i in g),
                "te": f"# {t_te}\n\n" + "\n\n".join(te[i]["body"] for i in g),
                "words": sum(words[i] for i in g),
                "source": [f"Roach Academia notes · {t_en.split(':')[0]}", f"Roach Academia notes (Telugu) · {t_te.split(':')[0]}"]}
        json.dump(part, open(f"{od}/{pid}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        ids.append(pid); print(pid, part["words"], "words ·", " | ".join(part["sections"]))

if __name__ == "__main__":
    main()
