# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

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
