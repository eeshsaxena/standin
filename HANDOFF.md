# standin — handoff

**What it is:** a "VCR for LLMs". Record your LLM/HTTP API calls once, replay them
forever: fast, free, deterministic, offline. Provider-agnostic and LLM-aware.

- **Repo:** `github.com/eeshsaxena/standin` (PUBLIC). Local: `Downloads/understudy`.
- **Current: v0.7.0** on `main`. **PyPI has 0.2.0** — the newer versions are NOT
  published yet (publishing is your local `twine` step; CI publish is billing-blocked).

## Shipped (verified: ruff + mypy clean, 117 tests + 1 aiohttp skip on 3.14; aiohttp verified on 3.12)
- **Transports:** hooks `httpx`, `requests`, and `aiohttp` (transport-universal).
- **Matchers:** `DefaultMatcher` (exact, JSON key-order-insensitive), `FuzzyMatcher`
  (string-similarity drift), `SemanticMatcher` (embedding cosine, dependency-free —
  you pass an `embed` callable).
- **Replay-miss diagnostics:** unmatched request in replay-only mode shows the closest
  recording + field-level diff, or "already replayed" (agent-loop mistake).
- **Redaction:** hardened — auth headers, shape-based secret detection (sk-/sk-ant-/
  AKIA/AIza/…), secret field names, custom-rule API. Cassettes are commit-safe.
- **CLI:** `standin list|show|stats|scrub|verify|diff`. `verify` is a CI "is this
  cassette safe to commit?" gate (non-zero if a live-looking secret remains).
- **pytest:** `standin` fixture + `@pytest.mark.standin`; `--standin-mode` /
  `--standin-record` CLI options; `STANDIN_MODE=none` env for CI.
- **Performance:** O(1) key-indexed replay lookup for the default matcher
  (~5.7x faster than the scan at 5k interactions; benchmark in `benchmarks/`).
- Four modes (once/none/all/new_episodes), streaming (SSE), tool-calls, examples for
  OpenAI/Anthropic/litellm/LangChain.

## Architecture
Transport-neutral engine (RawRequest/RawResponse + do_real). Layers: models/_codec →
redaction → matching → storage → cassette → config → engine → interceptors (httpx/
requests/aiohttp) → core.use_cassette + pytest_plugin. See ARCHITECTURE.md.

## Remaining (your call)
- Publish the new versions to PyPI when ready (local twine; `standin` 0.2.0 is live,
  0.7.0 is not). Testing/lint/build all green.
- Commits omit the Co-Authored-By AI trailer, per your OSS preference.
