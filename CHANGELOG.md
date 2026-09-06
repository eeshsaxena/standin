# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.7.1] - 2026-09-06

### Security
- Redact secrets in request URLs. Recording now strips basic-auth credentials
  from the URL (`https://user:pass@host` -> `https://[REDACTED]@host`), masks
  secret query-string values by key name (`?api_key=`, `?access_token=`,
  Google's `?key=`, signed-URL `?sig=`/`?signature=`, ...), and sweeps the URL
  for any secret-shaped token. Previously the URL was written verbatim, so a key
  in a query param or basic-auth in the URL landed in the committed cassette.
- `standin verify` now scans the URL as well as headers and bodies, so a secret
  in a query param or in the URL userinfo fails the gate instead of passing it.
  `standin scrub` likewise redacts the URL.
- Redact secrets in `application/x-www-form-urlencoded` bodies by field name
  (e.g. an OAuth `client_secret=...` token exchange), not just by token shape.
- Broaden default coverage: mask the `token`, `id_token`, `session_token`, and
  `private_key` field names, recognise JSON Web Tokens, and strip a
  secret-shaped token out of any header value even when the header name is not
  on the known-sensitive list.

### Changed
- The `DefaultMatcher`/`FuzzyMatcher`/`SemanticMatcher` redact the URL on both
  the live and stored sides before comparing, so record/replay still line up
  after the stored URL is redacted (existing raw-URL cassettes keep replaying).
- `standin list`/`stats`/`show`/`scrub` now report a clean error (exit 2) on a
  malformed cassette instead of dumping a traceback, and a pathologically nested
  cassette raises `CassetteError` rather than an uncaught `RecursionError`.

## [0.7.0] - 2026-09-06

### Changed
- Replay lookup is now O(1) per request with the default matcher. When the
  active matcher exposes `live_key`/`stored_key` (`DefaultMatcher`), the cassette
  builds a key -> queue index and pops the next unplayed recording for a request
  instead of scanning every interaction. Semantics are unchanged: repeated calls
  replay in recorded order, each recording plays once, misses still return the
  same replay-miss diagnostics, and the lookup stays thread-safe. `FuzzyMatcher`,
  `SemanticMatcher`, and any custom matcher without those key functions keep the
  linear scan. On-disk format and public API are unchanged. `benchmarks/bench_matching.py`
  replays a 5,000-interaction cassette about 5.5x faster than the scan, and the
  per-request cost stays flat (~6 us) as the cassette grows.

## [0.6.0] - 2026-09-06

### Added
- `standin diff <a> <b>`: compare two cassettes interaction by interaction. It
  matches requests the same way replay does, then reports which interactions are
  only in the first, only in the second, and which match by request but whose
  response changed (status and/or body), with a per-interaction summary. Exits
  `0` when the two are identical, `1` when they differ, and `2` on a load error,
  so it slots into a re-record review or CI check.
- pytest command-line mode options. `--standin-mode=<once|none|all|new_episodes>`
  sets the mode for cassettes opened by the `standin` fixture/marker, and
  `--standin-record` is shorthand for `--standin-mode=all`. An explicit option
  wins over both the marker mode and `STANDIN_MODE`; with neither flag the
  existing env override and marker behavior are unchanged.

## [0.5.0] - 2026-09-06

### Added
- `standin verify <cassette>`: a "safe to commit?" gate for CI and pre-commit
  hooks. It prints a summary (interactions, methods, statuses), scans every
  header and body for anything still shaped like a live secret, prints each
  finding with its interaction index and location, and exits non-zero if any
  remain (2 on a malformed/unloadable cassette). The scanner reuses the
  redactor's rules, so a cassette that passes `scrub` passes `verify`.

### Changed
- Hardened `DefaultRedactor`. It now also masks the `x-goog-api-key`,
  `api-key`, `cookie`, and `set-cookie` headers; recognises OpenAI project
  keys, AWS access-key ids, and Google API keys by shape; and redacts common
  secret field names (`api_key`, `access_token`, `refresh_token`, `password`,
  `client_secret`, ...) regardless of value. New `extra_field_names=[...]`
  constructor argument for custom field names; `extra_headers` and
  `extra_patterns` are unchanged. Redaction stays idempotent and fails safe on
  nested or non-string inputs.

## [0.4.0] - 2026-09-06

### Added
- `SemanticMatcher`: match method/url exactly but compare request bodies by
  embedding cosine similarity, so a paraphrased prompt still replays. It stays
  dependency-free: you pass an `embed` callable (`str -> Sequence[float]`), so it
  works with sentence-transformers, an embeddings API, or anything else. Cosine is
  computed in pure Python.
- Runnable examples for the Anthropic SDK and litellm under `examples/`, and an
  integration test proving an OpenAI-style tool-call response round-trips through
  a cassette.

## [0.3.0] - 2026-09-06

### Added
- `requests` and `aiohttp` interceptors, so standin now covers SDKs and tools
  built on those clients, not only `httpx`. On record, the real response is
  returned; on replay it is served offline.
- Replay-miss diagnostics: in replay-only mode, an unmatched request now reports
  the closest recording with a field-level diff, or says the matching recording
  was already replayed (the usual agent-loop / call-count mistake), instead of a
  bare "no recorded interaction".

## [0.2.0] - 2026-09-05

### Added
- `standin` command-line tool: `list`, `show`, `stats`, and `scrub` (re-run
  secret redaction over an existing cassette).
- `FuzzyMatcher`: match method/url exactly but allow the request body to differ
  up to a similarity threshold, so a reworded/reformatted prompt still replays.
  A semantic/embedding matcher plugs in the same way (implement `matches`).
- Runnable examples for OpenAI and LangChain under `examples/`.

### Changed
- The `Matcher` protocol is now a single `matches(live, stored)` predicate
  (exact and fuzzy strategies share the cassette lookup). `DefaultMatcher` keeps
  its `live_key`/`stored_key` helpers.

## [0.1.0] - 2026-09-05

### Added
- `use_cassette` context manager and a `standin` pytest fixture / marker.
- Provider-agnostic record & replay via an httpx transport interceptor
  (OpenAI, Anthropic, Gemini, Mistral, Cohere, litellm, LangChain, LlamaIndex).
- Streaming (SSE) record and replay.
- Automatic redaction of auth headers and secret tokens in cassettes.
- VCR-style modes: `once`, `none`, `all`, `new_episodes`; `STANDIN_MODE` override.
- JSON-body-aware matching; ordered replay for repeated calls (agent loops).
- Pluggable `Matcher`, `Redactor`, and `CassetteStore` protocols.

[Unreleased]: https://github.com/eeshsaxena/standin/compare/v0.7.1...HEAD
[0.7.1]: https://github.com/eeshsaxena/standin/compare/v0.7.0...v0.7.1
[0.7.0]: https://github.com/eeshsaxena/standin/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/eeshsaxena/standin/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/eeshsaxena/standin/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/eeshsaxena/standin/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/eeshsaxena/standin/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/eeshsaxena/standin/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/eeshsaxena/standin/releases/tag/v0.1.0
