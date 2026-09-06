from standin.redaction import DefaultRedactor, NullRedactor


def test_sensitive_headers_masked():
    r = DefaultRedactor()
    out = r.redact_headers({"Authorization": "Bearer abc", "X-Trace": "keep"})
    assert out["Authorization"] == "[REDACTED]"
    assert out["X-Trace"] == "keep"


def test_secret_tokens_in_body_masked():
    r = DefaultRedactor()
    out = r.redact_obj({"msg": "here is sk-ant-abcdefghijklmnopqrstuvwxyz012345 ok"})
    assert "sk-ant-" not in out["msg"]
    assert "[REDACTED]" in out["msg"]


def test_nested_and_list_redaction():
    r = DefaultRedactor()
    out = r.redact_obj({"a": [{"k": "ghp_" + "a" * 36}]})
    assert "[REDACTED]" in out["a"][0]["k"]


def test_null_redactor_is_noop():
    r = NullRedactor()
    assert r.redact_headers({"Authorization": "x"}) == {"Authorization": "x"}
    assert r.redact_text("sk-ant-secret") == "sk-ant-secret"


def test_custom_extra_header():
    r = DefaultRedactor(extra_headers=["x-secret"])
    assert r.redact_headers({"X-Secret": "v"})["X-Secret"] == "[REDACTED]"


def test_more_auth_headers_masked():
    r = DefaultRedactor()
    out = r.redact_headers({
        "x-api-key": "sk-live-123", "api-key": "abc", "x-goog-api-key": "g",
        "cookie": "session=1", "set-cookie": "session=1", "X-Trace": "keep",
    })
    assert all(out[h] == "[REDACTED]" for h in
               ("x-api-key", "api-key", "x-goog-api-key", "cookie", "set-cookie"))
    assert out["X-Trace"] == "keep"


def test_openai_and_aws_and_google_values_masked():
    r = DefaultRedactor()
    out = r.redact_obj({
        "a": "key sk-proj-" + "A" * 24 + " end",
        "b": "AKIA" + "A" * 16,
        "c": "AIza" + "b" * 35,
    })
    assert "sk-proj-" not in out["a"] and "[REDACTED]" in out["a"]
    assert "AKIA" not in out["b"]
    assert "AIza" not in out["c"]


def test_secret_field_names_masked_regardless_of_value():
    r = DefaultRedactor()
    out = r.redact_obj({
        "password": "hunter2", "client_secret": "plainish", "keep": "hello",
    })
    assert out["password"] == "[REDACTED]"
    assert out["client_secret"] == "[REDACTED]"
    assert out["keep"] == "hello"


def test_custom_field_name_and_pattern():
    r = DefaultRedactor(extra_field_names=["session_token"],
                        extra_patterns=[r"tok_[0-9]{8}"])
    out = r.redact_obj({"session_token": "abc", "note": "id tok_12345678 ok"})
    assert out["session_token"] == "[REDACTED]"
    assert "tok_12345678" not in out["note"]


def test_redaction_is_idempotent():
    r = DefaultRedactor()
    obj = {"password": "hunter2", "msg": "sk-ant-" + "z" * 24, "n": 3, "ok": None}
    once = r.redact_obj(obj)
    assert r.redact_obj(once) == once


def test_benign_text_not_touched():
    r = DefaultRedactor()
    text = "The password is on a sticky note; sketch a skater doing a trick."
    assert r.redact_text(text) == text
    obj = {"note": "sk8ers gonna sk8", "count": 10, "flag": True}
    assert r.redact_obj(obj) == obj


def test_odd_inputs_do_not_crash():
    r = DefaultRedactor()
    assert r.redact_obj({"a": [1, None, {"b": 2.5}], "c": True}) == \
        {"a": [1, None, {"b": 2.5}], "c": True}
    assert r.scan_headers("not a dict") == []
    assert r.scan_obj({"nested": [{"x": None}]}) == []


def test_scan_finds_live_secret():
    r = DefaultRedactor()
    hits = r.scan_obj({"auth": {"api_key": "sk-proj-" + "A" * 24}})
    assert hits and hits[0][0] == "auth.api_key"


def test_scan_clean_after_redaction():
    r = DefaultRedactor()
    obj = {"api_key": "sk-proj-" + "A" * 24, "msg": "sk-ant-" + "z" * 24}
    assert r.scan_obj(r.redact_obj(obj)) == []
