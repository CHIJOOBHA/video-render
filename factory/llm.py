"""Model access for the video factory (4 Nov 2026). Two providers, used together:
- DeepSeek (paid, very cheap; env DEEPSEEK_API_KEY, optional DEEPSEEK_MODEL) — English scripts, no tight daily cap.
- Gemini (free tier; env GEMINI_API_KEY) — Telugu, and English when DeepSeek has no key/credit. Free quota is small
  (gemini-3.8-flash: 20 requests/day), so every free model is tried in turn.
ask(prompt, tag, prefer=[...]) returns parsed JSON from the first provider that answers."""
import json, os, re, time, urllib.request, urllib.error

class _Log(list):
    def append(self, x):
        print("  ·", x, flush=True); super().append(x)
LOG = _Log()

def _post(url, body, headers, timeout=900):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"content-type": "application/json", **headers})
    return json.load(urllib.request.urlopen(req, timeout=timeout))

def _json(txt):
    txt = txt.strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", txt, re.S)
    if m: txt = m.group(1)
    return json.loads(txt)

# ---------------------------------------------------------------- DeepSeek (OpenAI-style API)
DS_DEAD = False
def _deepseek(prompt, tag):
    global DS_DEAD
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if not key or DS_DEAD: return None
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
    body = {"model": model, "temperature": 0.5, "max_tokens": 8192, "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": "You write exam-class video lessons. Answer with ONE JSON object only."},
                         {"role": "user", "content": prompt}]}
    for n in range(6):
        t0 = time.time()
        try:
            r = _post("https://api.deepseek.com/chat/completions", body, {"authorization": f"Bearer {key}"})
            c = r["choices"][0]; u = r.get("usage", {})
            LOG.append(f"{tag}: deepseek/{model} {time.time() - t0:.0f}s in={u.get('prompt_tokens')} out={u.get('completion_tokens')} finish={c.get('finish_reason')}")
            return _json(c["message"]["content"])
        except urllib.error.HTTPError as e:
            msg = re.sub(r"\s+", " ", e.read()[:800].decode("utf-8", "ignore"))
            LOG.append(f"{tag}: deepseek HTTP {e.code} {msg[:300]}")
            if e.code in (401, 402, 403):          # bad key / no balance: stop using DeepSeek in this run
                DS_DEAD = True; return None
            time.sleep(10 * (n + 1))
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            LOG.append(f"{tag}: deepseek bad answer {type(e).__name__} {e}"); time.sleep(2)
        except Exception as e:
            LOG.append(f"{tag}: deepseek {e}"); time.sleep(10)
    return None

# ---------------------------------------------------------------- Gemini (free tier)
G_ORDER = []
def _g_models(key):
    req = urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/models?pageSize=200", headers={"x-goog-api-key": key})
    names = [m["name"].split("/")[-1] for m in json.load(urllib.request.urlopen(req, timeout=60))["models"]
             if "generateContent" in m.get("supportedGenerationMethods", [])]
    names = [n for n in names if not re.search(r"customtools|image|tts|live|audio|embedding|robotics|computer|gemma|nano|learnlm", n)]
    pref = [r"^gemini-[\d.]+-flash$", r"^gemini-[\d.]+-flash-(preview|latest)", r"^gemini-flash-latest$", r"^gemini-[\d.]+-pro", r"^gemini-[\d.]+-flash-lite"]
    out = []
    for p in pref:
        out += [n for n in sorted(names, reverse=True) if re.search(p, n) and n not in out]
    return out

def _gemini(prompt, tag):
    global G_ORDER
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key: return None
    if not G_ORDER:
        try: G_ORDER = _g_models(key); LOG.append(f"gemini models: {G_ORDER[:6]}")
        except Exception as e: LOG.append(f"gemini models: {e}"); return None
    body = {"contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.5, "responseMimeType": "application/json", "maxOutputTokens": 65536}}
    for n in range(3 * max(1, len(G_ORDER))):
        if not G_ORDER: LOG.append(f"{tag}: no Gemini model has free quota left today"); return None
        m = G_ORDER[0]; t0 = time.time(); r = None
        try:
            r = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent", body, {"x-goog-api-key": key})
            txt = "".join(p.get("text", "") for p in r["candidates"][0]["content"]["parts"])
            LOG.append(f"{tag}: gemini/{m} {time.time() - t0:.0f}s")
            return _json(txt)
        except urllib.error.HTTPError as e:
            msg = re.sub(r"\s+", " ", e.read()[:3000].decode("utf-8", "ignore"))
            LOG.append(f"{tag}: gemini/{m} HTTP {e.code} {msg[:220]}")
            if e.code in (400, 403, 404) or (e.code == 429 and re.search(r"per day|PerDay", msg)): G_ORDER.pop(0)
            elif e.code == 429:
                w = re.search(r"retry in (\d+)(?:\.\d+)?s", msg); time.sleep(min(int(w.group(1)) + 2, 90) if w else 30)
            else: G_ORDER.append(G_ORDER.pop(0)); time.sleep(5)      # busy: next model
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            fin = r and (r.get("candidates") or [{}])[0].get("finishReason")
            LOG.append(f"{tag}: gemini/{m} bad answer {type(e).__name__} finish={fin}"); time.sleep(2)
        except Exception as e:
            LOG.append(f"{tag}: gemini/{m} {e}"); time.sleep(10)
    return None

def ask(prompt, tag, prefer=("deepseek", "gemini")):
    for p in prefer:
        out = (_deepseek if p == "deepseek" else _gemini)(prompt, tag)
        if out is not None: return out
    raise SystemExit(f"{tag}: no model could answer (DeepSeek key/credit? Gemini daily quota?)")

def available():
    return [p for p, k in (("deepseek", "DEEPSEEK_API_KEY"), ("gemini", "GEMINI_API_KEY")) if os.environ.get(k, "").strip()]
