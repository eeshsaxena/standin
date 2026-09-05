# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/), and the project adheres to
[Semantic Versioning](https://semver.org/).

## [Unreleased]

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
