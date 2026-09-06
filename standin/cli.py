"""The `standin` command: inspect and maintain cassettes.

    standin list    cassette.json          # one line per interaction
    standin show    cassette.json 0        # full request/response of interaction 0
    standin stats   cassette.json          # summary counts
    standin scrub   cassette.json          # re-run secret redaction over a cassette
    standin verify  cassette.json          # fail if a live-looking secret remains
    standin diff    a.json b.json          # what changed between two cassettes
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from . import __version__
from .exceptions import CassetteError
from .matching import DefaultMatcher
from .models import Interaction, RecordedResponse
from .redaction import DefaultRedactor
from .storage import JSONCassetteStore


def _load(path: str):
    return JSONCassetteStore().load(Path(path))


def _content_type(headers) -> str:
    if isinstance(headers, dict):
        for k, v in headers.items():
            if isinstance(k, str) and k.lower() == "content-type" and isinstance(v, str):
                return v
    return ""


def _is_form(content_type: str) -> bool:
    return "application/x-www-form-urlencoded" in (content_type or "").lower()


def _redact_body(body: dict, r: DefaultRedactor, content_type: str = "") -> dict:
    if "json" in body:
        return {"json": r.redact_obj(body["json"])}
    if "text" in body:
        text = body["text"]
        return {"text": r.redact_query(text) if _is_form(content_type) else r.redact_text(text)}
    return body


def _scan_body(body, r: DefaultRedactor, content_type: str = "") -> list[tuple[str, str]]:
    if not isinstance(body, dict):
        return []
    if "json" in body:
        return r.scan_obj(body["json"])
    if "text" in body:
        return r.scan_query(body["text"]) if _is_form(content_type) else r.scan_obj(body["text"])
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
        req_ct = _content_type(it.request.headers)
        resp_ct = _content_type(it.response.headers)
        it.request.url = r.redact_url(it.request.url)
        it.request.headers = r.redact_headers(it.request.headers)
        it.response.headers = r.redact_headers(it.response.headers)
        it.request.body = _redact_body(it.request.body, r, req_ct)
        it.response.body = _redact_body(it.response.body, r, resp_ct)
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
        for loc, snippet in r.scan_url(it.request.url):
            findings.append(f"  [{i}] request {loc}: {snippet}")
        for label, headers in (("request", it.request.headers), ("response", it.response.headers)):
            for name, snippet in r.scan_headers(headers):
                findings.append(f"  [{i}] {label} header {name}: {snippet}")
        for label, body, ct in (
            ("request", it.request.body, _content_type(it.request.headers)),
            ("response", it.response.body, _content_type(it.response.headers)),
        ):
            for loc, snippet in _scan_body(body, r, ct):
                findings.append(f"  [{i}] {label} body {loc}: {snippet}")

    if findings:
        print(f"\nFAIL: {len(findings)} suspected secret(s) still present:")
        for line in findings:
            print(line)
        return 1
    print("\nOK: no suspected secrets found")
    return 0


def _response_changes(a: RecordedResponse, b: RecordedResponse) -> list[str]:
    changes: list[str] = []
    if a.status_code != b.status_code:
        changes.append(f"status {a.status_code} -> {b.status_code}")
    if a.body != b.body:
        changes.append("body changed")
    return changes


def _by_request(
    items: list[Interaction], matcher: DefaultMatcher
) -> tuple[dict[str, list[tuple[int, Interaction]]], list[str]]:
    # Group interactions by their match key, keeping order and original index.
    # A repeated request (agent loops) keeps every occurrence so they pair up.
    groups: dict[str, list[tuple[int, Interaction]]] = {}
    order: list[str] = []
    for idx, it in enumerate(items):
        key = matcher.stored_key(it.request)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append((idx, it))
    return groups, order


def cmd_diff(args) -> int:
    try:
        a = _load(args.cassette_a)
        b = _load(args.cassette_b)
    except CassetteError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    matcher = DefaultMatcher(DefaultRedactor())
    ga, oa = _by_request(a, matcher)
    gb, ob = _by_request(b, matcher)
    keys = list(oa) + [k for k in ob if k not in ga]

    lines: list[str] = []
    changed = only_a = only_b = unchanged = 0
    for key in keys:
        la = ga.get(key, [])
        lb = gb.get(key, [])
        paired = min(len(la), len(lb))
        for (ia, ita), (ib, itb) in zip(la[:paired], lb[:paired]):
            notes = _response_changes(ita.response, itb.response)
            if notes:
                changed += 1
                lines.append(f"  ~ A[{ia}] B[{ib}]  {ita.request.method} {ita.request.url}  {', '.join(notes)}")
            else:
                unchanged += 1
        for ia, ita in la[paired:]:
            only_a += 1
            lines.append(f"  - A[{ia}]  {ita.request.method} {ita.request.url}  ({ita.response.status_code})")
        for ib, itb in lb[paired:]:
            only_b += 1
            lines.append(f"  + B[{ib}]  {itb.request.method} {itb.request.url}  ({itb.response.status_code})")

    print(f"diff {args.cassette_a} -> {args.cassette_b}")
    print(f"  A: {len(a)} interaction(s)   B: {len(b)} interaction(s)")
    if lines:
        print("  (- only in A, + only in B, ~ response changed)\n")
        for line in lines:
            print(line)
    print(f"\n  {changed} changed, {only_a} only in A, {only_b} only in B, {unchanged} unchanged")
    if changed or only_a or only_b:
        print("differ")
        return 1
    print("identical")
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

    p = sub.add_parser("diff", help="compare two cassettes interaction by interaction")
    p.add_argument("cassette_a")
    p.add_argument("cassette_b")
    p.set_defaults(func=cmd_diff)

    args = ap.parse_args(argv)
    try:
        return args.func(args)
    except FileNotFoundError:
        print(f"error: cassette not found: {args.cassette}", file=sys.stderr)
        return 1
    except IndexError:
        print("error: interaction index out of range", file=sys.stderr)
        return 1
    except CassetteError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except RecursionError:
        # A hand-crafted, pathologically nested cassette (e.g. pulled from a PR)
        # must not crash the tool with a traceback.
        print("error: cassette is too deeply nested to process", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
