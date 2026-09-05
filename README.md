# understudy

**A stand-in for the real LLM in your tests.** Record your LLM API calls once, then replay them forever: fast, free, deterministic, and fully offline. One line, any provider.

```python
import understudy

with understudy.use_cassette("tests/cassettes/summary.json"):
    reply = client.chat.completions.create(model="gpt-4o", messages=[...])
# First run: hits the real API and records it.
# Every run after: replayed from disk. No network, no cost, same answer.
```

Your LLM tests are slow, flaky, and cost money because they hit real APIs. `understudy` makes them **deterministic and offline** by recording the real HTTP calls once and replaying them after, with the things LLM devs actually need: **streaming**, **tool-calls**, **secret redaction**, and **fuzzy matching**.

---

## Why not just VCR.py?

VCR.py is great, but it's a general HTTP tool. `understudy` is built for LLMs:

- **Provider-agnostic, zero wiring.** It hooks `httpx` under the hood, so it works with **OpenAI, Anthropic, Gemini, Mistral, Cohere, litellm, LangChain, LlamaIndex** — anything that sends over httpx. No adapters to install.
- **Streaming just works.** Server-sent event (SSE) responses are recorded and replayed intact.
- **Safe to commit.** API keys in headers and secret-looking tokens in bodies are **redacted automatically**, so cassettes can live in your public repo.
- **Fuzzy, body-aware matching.** Requests match on normalized JSON, so formatting noise doesn't break replays (semantic matching is on the roadmap).
- **One-line pytest fixture**, with sane auto-named cassettes.

## Install

```bash
pip install understudy
```

Requires Python 3.9+ and `httpx` (already a dependency of the major LLM SDKs).

## Quickstart

### With pytest (recommended)

```python
import pytest

@pytest.mark.understudy   # cassette auto-named tests/cassettes/test_summarize.json
def test_summarize(understudy):
    out = summarize("war and peace")      # your code that calls an LLM
    assert "Napoleon" in out
```

First run records against the real API; every run after replays from the cassette. Commit the cassette and your teammates (and CI) run the test with **no keys and no network**.

### Anywhere (context manager)

```python
import understudy
from openai import OpenAI

client = OpenAI()
with understudy.use_cassette("tests/cassettes/haiku.json"):
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

```python
with understudy.use_cassette("x.json", mode="none"):
    ...
```

**In CI**, force replay-only for the whole run so a stray live call fails loudly:

```bash
UNDERSTUDY_MODE=none pytest
```

## What a cassette looks like

Plain, reviewable JSON, secrets already stripped:

```json
{
  "version": 1,
  "recorded_with": "understudy",
  "interactions": [
    {
      "request": {
        "method": "POST",
        "url": "https://api.openai.com/v1/chat/completions",
        "headers": { "authorization": "[REDACTED]" },
        "body": { "json": { "model": "gpt-4o-mini", "messages": [ ... ] } }
      },
      "response": {
        "status_code": 200,
        "body": { "json": { "choices": [ ... ] } }
      }
    }
  ]
}
```

## How it works

`understudy` patches `httpx`'s transport once (inert until you open a cassette). On record it lets the real call through and saves the request/response pair; on replay it returns the saved response without touching the network. Because every major LLM SDK sends over `httpx`, a single hook covers all of them, streaming included. Repeated identical calls replay in order, so multi-step agent runs work too.

## Roadmap

- Semantic request matching (embed + threshold) so paraphrased prompts still hit.
- A `understudy` CLI to inspect, diff, and re-scrub cassettes.
- `requests`/`aiohttp` transport support.
- Redactable custom fields and pluggable matchers.

## License

MIT. Contributions welcome.
