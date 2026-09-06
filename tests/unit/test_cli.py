from standin.cli import main
from standin.models import Interaction, RecordedRequest, RecordedResponse
from standin.storage import JSONCassetteStore


def _write(path, headers=None, body=None):
    JSONCassetteStore().save(path, [Interaction(
        request=RecordedRequest("POST", "http://api/x", headers or {}, body or {"json": {"a": 1}}),
        response=RecordedResponse(200, {}, {"json": {"ok": True}}),
    )])


def test_cli_list(tmp_path, capsys):
    p = tmp_path / "c.json"
    _write(p)
    assert main(["list", str(p)]) == 0
    out = capsys.readouterr().out
    assert "1 interaction" in out and "POST" in out


def test_cli_stats(tmp_path, capsys):
    p = tmp_path / "c.json"
    _write(p)
    assert main(["stats", str(p)]) == 0
    assert "interactions : 1" in capsys.readouterr().out


def test_cli_show(tmp_path, capsys):
    p = tmp_path / "c.json"
    _write(p)
    assert main(["show", str(p), "0"]) == 0
    assert "http://api/x" in capsys.readouterr().out


def test_cli_show_out_of_range_returns_1(tmp_path):
    p = tmp_path / "c.json"
    _write(p)
    assert main(["show", str(p), "9"]) == 1


def test_cli_scrub_redacts_secrets(tmp_path):
    p = tmp_path / "c.json"
    _write(p, headers={"authorization": "Bearer sk-live-SECRETsecret1234567890"},
           body={"json": {"note": "token ghp_" + "a" * 36}})
    assert main(["scrub", str(p)]) == 0
    text = p.read_text(encoding="utf-8")
    assert "sk-live-SECRET" not in text  # header value masked
    assert "ghp_aaaa" not in text  # body token masked
    assert "[REDACTED]" in text


def test_cli_verify_clean_exits_zero(tmp_path, capsys):
    p = tmp_path / "c.json"
    _write(p, headers={"authorization": "[REDACTED]"}, body={"json": {"model": "gpt-4o"}})
    assert main(["verify", str(p)]) == 0
    out = capsys.readouterr().out
    assert "1 interaction" in out
    assert "OK: no suspected secrets" in out


def test_cli_verify_flags_live_secret(tmp_path, capsys):
    p = tmp_path / "c.json"
    _write(p, headers={"authorization": "Bearer real"},
           body={"json": {"api_key": "sk-proj-" + "A" * 24}})
    assert main(["verify", str(p)]) == 1
    out = capsys.readouterr().out
    assert "FAIL" in out
    assert "authorization" in out and "api_key" in out


def test_cli_verify_passes_after_scrub(tmp_path):
    p = tmp_path / "c.json"
    _write(p, headers={"authorization": "Bearer real"},
           body={"json": {"note": "ghp_" + "a" * 36}})
    assert main(["scrub", str(p)]) == 0
    assert main(["verify", str(p)]) == 0


def test_cli_verify_malformed_errors(tmp_path, capsys):
    p = tmp_path / "bad.json"
    p.write_text("{ not valid json", encoding="utf-8")
    assert main(["verify", str(p)]) == 2
    assert "error:" in capsys.readouterr().err
