# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.6.0] - 2026-09-06

### Added
- `standin diff <a> <b>`: compare two cassettes interaction by interaction. It
  matches requests the same way replay does, then reports which interactions are
  only in the first, only in the second, and which match by request but whose
  response changed (status and/or body), with a per-interaction summary. Exits
  `0` when the two are identical, `1` when they differ, and `2` on a load error,
  so it slots into a re-record review or CI check.

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
  dependency-free — you pass an `embed` callable (`str -> Sequence[float]`), so it
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

[Unreleased]: https://github.com/eeshsaxena/standin/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/eeshsaxena/standin/releases/tag/v0.1.0
