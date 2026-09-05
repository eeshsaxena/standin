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
