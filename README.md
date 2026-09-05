# standin

**A stand-in for the real LLM in your tests.** Record your LLM API calls once, then replay them forever: fast, free, deterministic, and fully offline. One line, any provider.

<p align="center"><img src="demo/standin.gif" alt="standin: record LLM calls once, replay them instantly and offline" width="820"></p>

```python
import standin

with standin.use_cassette("tests/cassettes/summary.json"):
    reply = client.chat.completions.create(model="gpt-4o", messages=[...])
# First run: hits the real API and records it.
# Every run after: replayed from disk. No network, no cost, same answer.
```

Your LLM tests are slow, flaky, and cost money because they hit real APIs. `standin` makes them **deterministic and offline** by recording the real HTTP calls once and replaying them after, with the things LLM devs actually need: **streaming**, **tool-calls**, **secret redaction**, and **body-aware matching**.

---

## Why not just VCR.py?

VCR.py is great, but it's a general HTTP tool. `standin` is built for LLMs:

- **Provider-agnostic, zero wiring.** It hooks `httpx` under the hood, so it works with **OpenAI, Anthropic, Gemini, Mistral, Cohere, litellm, LangChain, LlamaIndex** — anything that sends over httpx. No per-SDK adapters.
- **Streaming just works.** Server-sent event (SSE) responses are recorded and replayed intact.
- **Safe to commit.** API keys in headers and secret-looking tokens in bodies are **redacted automatically**, so cassettes can live in a public repo.
- **Body-aware matching.** Requests match on normalized JSON, so key ordering and formatting noise don't break replays. Repeated identical calls (agent loops) replay in order.
- **One-line pytest fixture**, with sane auto-named cassettes.
- **Clean, typed, extensible core** (see [ARCHITECTURE.md](ARCHITECTURE.md)) — swap the matcher, redactor, or storage backend.

## Install

```bash
pip install standin
```

Python 3.9+ and `httpx` (already a dependency of the major LLM SDKs).

## Quickstart

### With pytest (recommended)

```python
import pytest

@pytest.mark.standin          # cassette auto-named tests/cassettes/test_summarize.json
def test_summarize(standin):
    out = summarize("war and peace")     # your code that calls an LLM
    assert "Napoleon" in out
```

First run records against the real API; every run after replays from the cassette. Commit the cassette and teammates (and CI) run the test with **no keys and no network**.

### Anywhere (context manager)

```python
import standin
from openai import OpenAI

client = OpenAI()
with standin.use_cassette("tests/cassettes/haiku.json"):
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "haiku about testing"}],
    )
```

## Modes

| Mode | Behavior |
| --- | --- |
| `once` (default) | Replay if the cassette exists, otherwise record it. |
| `none` | Replay only. **Errors on any unrecorded call** — use this in CI. |
| `all` | Always re-record, ignoring existing interactions. |
| `new_episodes` | Replay what's recorded, record anything new (great for agent loops). |

**In CI**, force replay-only for the whole run so a stray live call fails loudly:

```bash
STANDIN_MODE=none pytest
```

## What a cassette looks like

Plain, reviewable JSON, secrets already stripped:

```json
{
  "version": 1,
  "recorded_with": "standin",
  "interactions": [
    {
      "request": {
        "method": "POST",
        "url": "https://api.openai.com/v1/chat/completions",
        "headers": { "authorization": "[REDACTED]" },
        "body": { "json": { "model": "gpt-4o-mini", "messages": [ ] } }
      },
      "response": { "status_code": 200, "body": { "json": { "choices": [ ] } } }
    }
  ]
}
```

## Extending it

Everything is a small protocol you can replace (see [ARCHITECTURE.md](ARCHITECTURE.md)):

```python
standin.use_cassette(path, matcher=MyMatcher(), redactor=MyRedactor(), store=MyStore())
```

- **Matcher** — decide when a live request equals a recorded one. Ships with
  `DefaultMatcher` (exact) and `FuzzyMatcher` (body may drift up to a similarity
  threshold, so a reworded prompt still replays):

  ```python
  from standin import use_cassette, FuzzyMatcher, DefaultRedactor
  with use_cassette(path, matcher=FuzzyMatcher(DefaultRedactor(), threshold=0.9)):
      ...
  ```
- **Redactor** — control what gets scrubbed before writing.
- **CassetteStore** — change the on-disk format.

## Command line

```bash
standin list  tests/cassettes/summary.json     # one line per interaction
standin show  tests/cassettes/summary.json 0   # full request/response
standin stats tests/cassettes/summary.json     # counts by method/status
standin scrub tests/cassettes/summary.json     # re-run secret redaction in place
```

## Roadmap

- Embedding-based semantic matching (a `Matcher` you drop in; `FuzzyMatcher`
  already covers string-similarity drift today).
- `requests` / `aiohttp` interceptors (the engine is already transport-neutral).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Run the suite with `pytest`, lint with `ruff`, type-check with `mypy`.

## License

MIT. See [LICENSE](LICENSE).
