#!/usr/bin/env python3
"""Private-storage helper for the public render runner. No keys here: each call proves 'I am a GitHub Actions run of
CHIJOOBHA/video-render on main' with GitHub's OIDC token; the storage function only allows the render folders.
  python3 r2.py get <key> <file>     python3 r2.py put <file> <key>
  python3 r2.py list <prefix>        python3 r2.py rm <key>"""
import json, os, subprocess, sys, urllib.request, urllib.parse

FN = "https://xijkeywydoesxvqnacnc.supabase.co/functions/v1/video-admin"

def oidc():
    u = os.environ["ACTIONS_ID_TOKEN_REQUEST_URL"] + "&audience=video-admin"
    req = urllib.request.Request(u, headers={"Authorization": "bearer " + os.environ["ACTIONS_ID_TOKEN_REQUEST_TOKEN"]})
    return json.load(urllib.request.urlopen(req))["value"]

def call(action, **q):
    req = urllib.request.Request(f"{FN}?action={action}&" + urllib.parse.urlencode(q), method="POST",
                                 headers={"x-gh-oidc": oidc()})
    try:
        return json.load(urllib.request.urlopen(req, timeout=120))
    except urllib.error.HTTPError as e:
        sys.exit(f"{action} {q.get('key', q.get('prefix'))}: HTTP {e.code} {e.read()[:200]!r}")

def curl(*a):
    subprocess.run(["curl", "-sS", "--fail", "--retry", "4", "--retry-all-errors", *a], check=True)

cmd = sys.argv[1]
if cmd == "get":
    curl("-o", sys.argv[3], call("presign", method="GET", key=sys.argv[2], expires=7200)["url"])
elif cmd == "put":
    curl("-o", "/dev/null", "-X", "PUT", "--upload-file", sys.argv[2], call("presign", method="PUT", key=sys.argv[3], expires=7200)["url"])
elif cmd == "list":
    for it in call("list", prefix=sys.argv[2])["items"]:
        print(it["at"][:10], it["size"], it["key"])
elif cmd == "rm":
    call("delete", key=sys.argv[2])
