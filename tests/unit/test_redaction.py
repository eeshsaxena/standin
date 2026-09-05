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
