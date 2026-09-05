# Architecture

`standin` is organized as a set of small, single-responsibility layers. The
guiding rule: **the record/replay policy never knows which HTTP client it is
sitting behind.** That keeps the decision logic tiny and testable, and makes new
clients (or storage formats, matchers, redactors) additive rather than invasive.

## Layers

```
                        use_cassette()          <- public API (core.py)
                             │
                             ▼
        ┌───────────────  Engine  ───────────────┐   <- policy (engine.py)
        │  record vs replay, ordering, misses     │
        └───┬───────────┬───────────┬─────────────┘
            │           │           │
        Matcher     Redactor   CassetteStore        <- pluggable protocols
        (matching)  (redaction) (storage)
            │           │           │
            ▼           ▼           ▼
                     Cassette  ── Interaction / Recorded{Request,Response}
                                        (models.py, _codec.py)
            ▲
            │  RawRequest / RawResponse  (transport-neutral)
            │
      ┌─────┴───────────────┐
      │    Interceptor       │   <- transport glue (interceptors/)
      │  HttpxInterceptor    │
      └─────────────────────┘
              │
        httpx.HTTPTransport (patched once, inert until a cassette is open)
```

## Modules

| Module | Responsibility |
| --- | --- |
| `models.py` | Data types. `RawRequest/RawResponse` (in-flight, bytes) vs `RecordedRequest/RecordedResponse/Interaction` (on disk). `Mode` enum. |
| `_codec.py` | Body encode/decode + canonicalization for matching. |
| `redaction.py` | `Redactor` protocol; `DefaultRedactor` (headers + secret patterns), `NullRedactor`. |
| `matching.py` | `Matcher` protocol; `DefaultMatcher` (method/url/body, JSON-aware). |
| `storage.py` | `CassetteStore` protocol; `JSONCassetteStore`. |
| `cassette.py` | In-memory interactions + the ordered replay cursor. |
| `config.py` | Wires the pieces; validates `mode`; picks the redactor. |
| `engine.py` | The **policy**: replay-or-record, per `Mode`. Transport-neutral. |
| `interceptors/` | Adapters from a concrete client to the engine. `HttpxInterceptor` today. |
| `core.py` | `use_cassette` context manager: build config → engine → activate. |
| `pytest_plugin.py` | `standin` fixture + `@pytest.mark.standin`. |

## Data flow

**Record** (cache miss): interceptor converts the client request to a
`RawRequest` → engine calls `do_real` (the real network call) → response is
redacted, encoded, appended to the cassette → returned to the client.

**Replay** (cache hit): interceptor builds the `RawRequest` → engine matches it
against an unplayed `Interaction` → decodes the stored response → returns it,
**without any network call**.

The active engine lives in a `ContextVar`, so recording is correct across threads
and asyncio, and the httpx patch is completely inert whenever no cassette is open.

## Extension points

Every collaborator is a `Protocol`, so you can pass your own:

- **Interceptor** — support another client (`requests`, `aiohttp`). The engine
  is already transport-neutral; you only translate that client's request/response
  to `RawRequest`/`RawResponse`.
- **Matcher** — change when a live request equals a recording (e.g. semantic).
- **Redactor** — change what gets scrubbed.
- **CassetteStore** — change the on-disk format (YAML, a single archive, ...).
