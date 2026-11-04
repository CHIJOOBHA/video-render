# Pictures you can use (Journal look — engraved drawings on cream paper)

Each scene shows the teacher's notes column on the right (`note` on a beat) and ONE OR TWO drawings on the left
(`visuals`). A drawing appears on beat `at` and leaves on beat `out` (optional, default = end of the scene).
Two drawings in a scene must not be on screen at the same time: the second one's `at` = the first one's `out`.
Every list item has `b` = the beat on which it appears (it must be inside the drawing's at..out range).
All text is plain English (the Telugu is written later into the same places). On-screen text is SHORT: ≤ 6 words per line, use `|` for a line break
(max 2 lines). Digits ARE allowed on screen (years, amounts, counts) — copy them exactly from the notes.
Pick the drawing that SHOWS the concept (mute test: the picture alone teaches the point). Vary drawings across scenes:
do not use the same drawing in two scenes in a row, and use at least 6 different drawings in a part.

| p | Use it for | Fields (besides p, at, out) |
|---|---|---|
| tiles | a set of 2–8 items (schemes, awards, topics) | `cols` 1–3, `items`: [{`h` title, `t`? subline, `b`, `hi`? true for the key one}] |
| flow | a process / cause → effect, 2–6 steps | `nodes`: [{`t`, `b`, `hi`?}] |
| ladder | levels, tiers, ranks, high → low | `rungs`: [{`t`, `sub`?, `b`}] |
| bars | comparing 2–6 numbers | `max` (number ≥ largest v), `bars`: [{`v` number, `label`, `tag` (the number as shown, e.g. "₹2.5 lakh cr"), `b`}] |
| sum | parts adding up to a total | `title`, `parts`: [{`v` "5", `t`, `b`}], `total`: {`v`, `t`, `b`} |
| tree | one thing with 2–6 branches | `root`, `branches`: [{`h`, `t`, `b`}] |
| plaques | people (name plates — never faces) | `items`: [{`name`, `role`, `b`, `hi`?}] (1–5 people) |
| nameplate | one person in focus | `name`, `role`, `b` |
| dates | 1–5 dated events in order | `events`: [{`date` e.g. "18 Aug 2026", `t`, `b`}] |
| calPage | one key date | `day` "17", `month`, `year` "2026", `t`, `b` |
| sheet | a document: act, order, report, notification | `title`, `sub`, `lines`: [2–3 short lines], `stamp`? short text, `stampAt`? beat |
| scale | two things weighed / compared side by side | `l`, `lsub`, `r`, `rsub`, `b` |
| vsCards | before vs after, A vs B (2–3 lines each) | `l`: {`title`, `lines`, `b`}, `r`: {`title`, `lines`, `b`} |
| trophy | one award / prize / rank | `t`, `sub`?, `b`, `hi`? |
| tally | 2–6 counted categories | `items`: [{`v` category, `t` detail, `b`}] |
| road | the plan of the part / a sequence of stops | `signs`: [{`t`, `b`}], `hi`: [indexes of signs to highlight], `hiAt` beat |
| apPins | places in Andhra Pradesh | `pins`: [{`k` pin name from AP list, `t` label, `b`}] |
| indiaMap | places in India | `pins`: [{`k` pin name from INDIA list, `t` label, `b`}] |

AP pin names (use only these): tirupati machilipatnam guntur banaganapalle araku srikalahasti uppada mangalagiri
venkatagiri dharmavaram ponduru kondapalli etikoppaka budithi bobbili durgi udayagiri allagadda narasapur visakhapatnam
vijayawada kolleru nsstr arasavalli srikakulam godavari krishna amaravati rajahmundry nellore kakinada eluru konaseema
bhimavaram sriharikota amalapuram lepakshi orvakal simhachalam kasibugga
INDIA pin names (use only these): delhi hyderabad vijayawada visakhapatnam mumbai navimumbai indore surat ahmedabad
bhopal lucknow bengaluru maharashtra assam tripura kevadia guwahati patna coimbatore belagavi warangal sriharikota
tirupati ap
A place not in these lists → use tiles or dates instead (never invent a pin name).

## Notes column (`note` on a beat, optional)
`{"t": "notes line"}` — a short line written on the teacher's notes; `**word**` = highlighted.
`{"h": "Heading", "clear": true}` — starts a fresh notes page with a heading.
Give most beats a `note`: it is what the student copies. Keep each ≤ 10 words.

## Scene kinds (`kind`)
`card` = normal teaching · `trap` = an exam trap / common mistake (dark page) · `trick` = a memory trick ·
`diary` = a story told like a diary page.
