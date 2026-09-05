# Demo

Two ways to see `standin` work, both keyless and offline (a local server stands
in for the OpenAI API with realistic latency).

## The one-liner (used for the README GIF)

```bash
python demo/demo.py
```

Records 5 model calls once (~8s), then replays them from the cassette (~0.03s):

```
  1st run   real API calls, recording     8.07s   $$$
  every run replayed from cassette        0.029s   $0.00  offline
  => 281x faster, deterministic, no network, no keys.
```

## The pytest example (the real workflow)

```bash
pytest demo/test_summary.py -p standin.pytest_plugin -q   # first run records
pytest demo/test_summary.py -p standin.pytest_plugin -q   # replays, offline
```

(The `-p` flag isn't needed once `standin` is `pip install`ed — the plugin loads
automatically.)

## Regenerating the GIF

The GIF is produced from [`demo.tape`](demo.tape) with
[VHS](https://github.com/charmbracelet/vhs):

```bash
vhs demo/demo.tape        # writes demo/standin.gif
```

No VHS? Record with [asciinema](https://asciinema.org) instead:

```bash
asciinema rec -c "python demo/demo.py" demo/standin.cast
# then: agg demo/standin.cast demo/standin.gif
```
