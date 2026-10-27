"""Smoke test: ingest two repos then run discovery, like the UI does. Usage: python smoke_test.py <base> <enh>"""
import json
import sys
import urllib.error
import urllib.request

API = "http://localhost:8000/api"


def post(path, body):
    req = urllib.request.Request(API + path, json.dumps(body).encode(), {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"{e.code}: {e.read().decode()}")


base, enh = sys.argv[1], sys.argv[2]
rec = post("/repositories/analyze", {"base": {"source": base}, "enhancement": {"source": enh}})
for side in ("base", "enhancement"):
    d = post("/discovery", {"repositoryId": rec[side]["id"]})
    print(side, rec[side]["branch"], d["applicationName"],
          {k: len(v) for k, v in d.items() if isinstance(v, list) and v})
