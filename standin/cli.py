"""The `standin` command: inspect and maintain cassettes.

    standin list    cassette.json          # one line per interaction
    standin show    cassette.json 0        # full request/response of interaction 0
    standin stats   cassette.json          # summary counts
    standin scrub   cassette.json          # re-run secret redaction over a cassette
    standin verify  cassette.json          # fail if a live-looking secret remains
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from . import __version__
from .exceptions import CassetteError
from .redaction import DefaultRedactor
from .storage import JSONCassetteStore


def _load(path: str):
    return JSONCassetteStore().load(Path(path))


def _redact_body(body: dict, r: DefaultRedactor) -> dict:
    if "json" in body:
        return {"json": r.redact_obj(body["json"])}
    if "text" in body:
        return {"text": r.redact_text(body["text"])}
    return body


def _scan_body(body, r: DefaultRedactor) -> list[tuple[str, str]]:
    if not isinstance(body, dict):
        return []
    if "json" in body:
        return r.scan_obj(body["json"])
    if "text" in body:
        return r.scan_obj(body["text"])
    return []


def cmd_list(args) -> int:
    items = _load(args.cassette)
    print(f"{len(items)} interaction(s) in {args.cassette}")
    for i, it in enumerate(items):
        print(f"  [{i}] {it.request.method:<6} {it.response.status_code}  {it.request.url}")
    return 0


def cmd_show(args) -> int:
    items = _load(args.cassette)
    it = items[args.index]
    print(json.dumps({"request": vars(it.request), "response": vars(it.response)}, indent=2, ensure_ascii=False))
    return 0


def cmd_stats(args) -> int:
    items = _load(args.cassette)
    print(f"interactions : {len(items)}")
    print(f"methods      : {dict(Counter(it.request.method for it in items))}")
    print(f"statuses     : {dict(Counter(it.response.status_code for it in items))}")
    return 0


def cmd_scrub(args) -> int:
    store = JSONCassetteStore()
    path = Path(args.cassette)
    items = store.load(path)
    r = DefaultRedactor()
    for it in items:
        it.request.headers = r.redact_headers(it.request.headers)
        it.response.headers = r.redact_headers(it.response.headers)
        it.request.body = _redact_body(it.request.body, r)
        it.response.body = _redact_body(it.response.body, r)
    store.save(path, items)
    print(f"scrubbed {len(items)} interaction(s) in {path}")
    return 0


def cmd_verify(args) -> int:
    try:
        items = _load(args.cassette)
    except CassetteError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(f"{args.cassette}: {len(items)} interaction(s)")
    print(f"  methods  : {dict(Counter(it.request.method for it in items))}")
    print(f"  statuses : {dict(Counter(it.response.status_code for it in items))}")

    r = DefaultRedactor()
    findings: list[str] = []
    for i, it in enumerate(items):
        for label, headers in (("request", it.request.headers), ("response", it.response.headers)):
            for name, snippet in r.scan_headers(headers):
                findings.append(f"  [{i}] {label} header {name}: {snippet}")
        for label, body in (("request", it.request.body), ("response", it.response.body)):
            for loc, snippet in _scan_body(body, r):
                findings.append(f"  [{i}] {label} body {loc}: {snippet}")

    if findings:
        print(f"\nFAIL: {len(findings)} suspected secret(s) still present:")
        for line in findings:
            print(line)
        return 1
    print("\nOK: no suspected secrets found")
    return 0


def main(argv=None) -> int:
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        try:
            reconfigure(encoding="utf-8")
        except Exception:
            pass

    ap = argparse.ArgumentParser(prog="standin", description="Inspect and maintain standin cassettes.")
    ap.add_argument("--version", action="version", version=f"standin {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list", help="list interactions in a cassette")
    p.add_argument("cassette")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("show", help="show one interaction as JSON")
    p.add_argument("cassette")
    p.add_argument("index", type=int)
    p.set_defaults(func=cmd_show)

    p = sub.add_parser("stats", help="summary counts for a cassette")
    p.add_argument("cassette")
    p.set_defaults(func=cmd_stats)

    p = sub.add_parser("scrub", help="re-run secret redaction over a cassette")
    p.add_argument("cassette")
    p.set_defaults(func=cmd_scrub)

    p = sub.add_parser("verify", help="fail if a live-looking secret remains (CI gate)")
    p.add_argument("cassette")
    p.set_defaults(func=cmd_verify)

    args = ap.parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError:
        print(f"error: cassette not found: {args.cassette}", file=sys.stderr)
        return 1
    except IndexError:
        print("error: interaction index out of range", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
