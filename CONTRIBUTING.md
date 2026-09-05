# Contributing to standin

Thanks for helping out. `standin` aims to stay small, typed, and dependency-light
(just `httpx`).

## Setup

```bash
git clone https://github.com/eeshsaxena/standin
cd standin
python -m venv .venv && . .venv/bin/activate   # or your tool of choice
pip install -e ".[dev]"
```

## Checks (all run in CI)

```bash
pytest          # tests, no API keys needed (a local server stands in)
ruff check .    # lint
ruff format .   # format
mypy standin    # types
```

Please add a test for any behavior change. The test suite uses a local HTTP
server (see `tests/conftest.py`), so it never makes real network calls or needs
credentials.

## Design

Read [ARCHITECTURE.md](ARCHITECTURE.md) first. The core principle is that the
`Engine` is transport-neutral. New functionality usually means adding a small
implementation of an existing `Protocol` (`Interceptor`, `Matcher`, `Redactor`,
`CassetteStore`) rather than editing the engine.

## Pull requests

- Keep PRs focused; one concern each.
- Update `CHANGELOG.md` under "Unreleased".
- Make sure `pytest`, `ruff`, and `mypy` pass.
