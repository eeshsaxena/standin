import base64

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


def _interaction(url="http://api/x", status=200, body=None):
    return Interaction(
        request=RecordedRequest("POST", url, {}, {"json": {"a": 1}}),
        response=RecordedResponse(status, {}, body or {"json": {"ok": True}}),
    )


def test_cli_diff_identical_exits_zero(tmp_path, capsys):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    JSONCassetteStore().save(a, [_interaction()])
    JSONCassetteStore().save(b, [_interaction()])
    assert main(["diff", str(a), str(b)]) == 0
    out = capsys.readouterr().out
    assert "identical" in out
    assert "1 unchanged" in out


def test_cli_diff_reports_changes_exits_one(tmp_path, capsys):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    JSONCassetteStore().save(a, [_interaction(status=200)])
    JSONCassetteStore().save(b, [
        _interaction(status=500, body={"json": {"ok": False}}),
        _interaction(url="http://api/y"),  # only in B
    ])
    assert main(["diff", str(a), str(b)]) == 1
    out = capsys.readouterr().out
    assert "status 200 -> 500" in out
    assert "body changed" in out
    assert "http://api/y" in out and "only in B" in out
    assert "differ" in out


def test_cli_diff_malformed_errors(tmp_path, capsys):
    a = tmp_path / "a.json"
    JSONCassetteStore().save(a, [_interaction()])
    bad = tmp_path / "bad.json"
    bad.write_text("{ not valid json", encoding="utf-8")
    assert main(["diff", str(a), str(bad)]) == 2
    assert "error:" in capsys.readouterr().err


def test_cli_diff_reports_only_in_a(tmp_path, capsys):
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    JSONCassetteStore().save(a, [_interaction(), _interaction(url="http://api/gone")])
    JSONCassetteStore().save(b, [_interaction()])
    assert main(["diff", str(a), str(b)]) == 1
    out = capsys.readouterr().out
    assert "http://api/gone" in out and "only in A" in out


def test_cli_verify_tolerates_non_dict_body(tmp_path, capsys):
    # A legacy or hand-edited cassette may carry a bare-string body; verify must
    # scan it without crashing.
    p = tmp_path / "legacy.json"
    JSONCassetteStore().save(p, [Interaction(
        request=RecordedRequest("POST", "http://api/x", {}, "a raw string body"),
        response=RecordedResponse(200, {}, {"json": {"ok": True}}),
    )])
    assert main(["verify", str(p)]) == 0
    assert "OK: no suspected secrets" in capsys.readouterr().out


def test_cli_verify_flags_secret_in_url(tmp_path, capsys):
    # A live secret in the request URL (query param) must not slip past verify.
    p = tmp_path / "c.json"
    JSONCassetteStore().save(p, [Interaction(
        request=RecordedRequest("GET", "https://api/x?api_key=sk-proj-" + "A" * 24, {}, {"empty": True}),
        response=RecordedResponse(200, {}, {"json": {"ok": True}}),
    )])
    assert main(["verify", str(p)]) == 1
    out = capsys.readouterr().out
    assert "FAIL" in out
    assert "url" in out and "api_key" in out


def test_cli_verify_flags_basic_auth_in_url(tmp_path, capsys):
    p = tmp_path / "c.json"
    JSONCassetteStore().save(p, [Interaction(
        request=RecordedRequest("GET", "https://user:s3cretPass@api/x", {}, {"empty": True}),
        response=RecordedResponse(200, {}, {"json": {"ok": True}}),
    )])
    assert main(["verify", str(p)]) == 1
    assert "userinfo" in capsys.readouterr().out


def test_cli_scrub_redacts_url_then_verify_passes(tmp_path):
    p = tmp_path / "c.json"
    JSONCassetteStore().save(p, [Interaction(
        request=RecordedRequest("GET", "https://user:pw@api/x?api_key=sk-proj-" + "A" * 24, {}, {"empty": True}),
        response=RecordedResponse(200, {}, {"json": {"ok": True}}),
    )])
    assert main(["scrub", str(p)]) == 0
    text = p.read_text(encoding="utf-8")
    assert "sk-proj-" not in text and "user:pw@" not in text
    assert main(["verify", str(p)]) == 0


def test_cli_verify_flags_form_urlencoded_secret(tmp_path, capsys):
    p = tmp_path / "c.json"
    JSONCassetteStore().save(p, [Interaction(
        request=RecordedRequest(
            "POST", "http://api/token",
            {"content-type": "application/x-www-form-urlencoded"},
            {"text": "grant_type=x&client_secret=plainsecretvalue"},
        ),
        response=RecordedResponse(200, {}, {"json": {"ok": True}}),
    )])
    assert main(["verify", str(p)]) == 1
    assert "client_secret" in capsys.readouterr().out


def test_cli_list_on_malformed_cassette_is_clean(tmp_path, capsys):
    # A malformed cassette (e.g. pulled from a PR) must not dump a traceback from
    # list/stats/show/scrub; they should report a clean error and exit 2.
    p = tmp_path / "bad.json"
    p.write_text("{ not valid json", encoding="utf-8")
    assert main(["list", str(p)]) == 2
    assert main(["stats", str(p)]) == 2
    assert "error:" in capsys.readouterr().err


def test_cli_verify_on_deeply_nested_cassette_is_clean(tmp_path, capsys):
    p = tmp_path / "deep.json"
    depth = 30000
    body = ('{"version": 1, "interactions": [{"request": {"method":"GET","url":"http://x",'
            '"headers":{},"body":{"json": %s}}, "response":{"status_code":200,"headers":{},'
            '"body":{"empty":true}}}]}') % ("[" * depth + "]" * depth)
    p.write_text(body, encoding="utf-8")
    assert main(["verify", str(p)]) == 2
    assert "error:" in capsys.readouterr().err


def test_cli_scrub_and_verify_handle_text_and_b64_bodies(tmp_path, capsys):
    # A text body carrying a token, plus a base64 body that scrub/verify must pass
    # through untouched (the non-json/non-text branches).
    p = tmp_path / "c.json"
    JSONCassetteStore().save(p, [
        Interaction(
            request=RecordedRequest("POST", "http://api/x", {}, {"text": "call ghp_" + "a" * 36}),
            response=RecordedResponse(200, {}, {"b64": base64.b64encode(b"\x00\x01").decode()}),
        ),
    ])
    assert main(["verify", str(p)]) == 1  # token in the text body is flagged
    assert "body" in capsys.readouterr().out

    assert main(["scrub", str(p)]) == 0
    assert "ghp_aaaa" not in p.read_text(encoding="utf-8")
    assert main(["verify", str(p)]) == 0  # clean after scrub
