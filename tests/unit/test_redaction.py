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


def test_scan_headers_finds_token_in_a_non_sensitive_header():
    # A secret can leak into a header we don't mask by name; scan still catches it
    # by pattern, and a non-string header value is skipped without crashing.
    r = DefaultRedactor()
    hits = r.scan_headers({"x-request-id": 12345, "x-note": "key sk-ant-" + "a" * 24})
    assert len(hits) == 1
    assert hits[0][0] == "x-note"


def test_scan_obj_on_a_bare_string_reports_value_location():
    r = DefaultRedactor()
    hits = r.scan_obj("here is sk-ant-" + "a" * 24 + " oops")
    assert hits and hits[0][0] == "value"


# -- URL redaction (secrets in query params, basic-auth userinfo) --------------
def test_redact_url_masks_secret_query_param_by_name():
    r = DefaultRedactor()
    out = r.redact_url("https://api.example.com/v1?api_key=plainlooking&user=bob")
    assert "plainlooking" not in out
    assert "[REDACTED]" in out
    assert "user=bob" in out  # benign params preserved


def test_redact_url_masks_google_key_and_shaped_tokens():
    r = DefaultRedactor()
    out = r.redact_url("https://gen.googleapis.com/v1?key=AIza" + "b" * 35)
    assert "AIza" + "b" * 35 not in out


def test_redact_url_strips_basic_auth_userinfo():
    r = DefaultRedactor()
    out = r.redact_url("https://alice:s3cr3tPassw0rd@api.example.com/v1/x")
    assert "s3cr3tPassw0rd" not in out
    assert "api.example.com" in out


def test_redact_url_leaves_clean_url_untouched():
    r = DefaultRedactor()
    url = "https://api.example.com/v1/models?model=gpt-4o&stream=true"
    assert r.redact_url(url) == url


def test_redact_url_is_idempotent():
    r = DefaultRedactor()
    once = r.redact_url("https://u:p@api.example.com/v1?api_key=sk-ant-" + "z" * 24)
    assert r.redact_url(once) == once


def test_scan_url_flags_userinfo_and_query_secret():
    r = DefaultRedactor()
    hits = r.scan_url("https://alice:hunter2pw@api.example.com/v1?api_key=plainish")
    locs = {loc for loc, _ in hits}
    assert "url userinfo" in locs
    assert any(loc.startswith("url query") for loc in locs)


def test_scan_url_clean_after_redaction():
    r = DefaultRedactor()
    dirty = "https://u:p@api.example.com/v1?api_key=sk-proj-" + "A" * 24
    assert r.scan_url(r.redact_url(dirty)) == []


# -- form-urlencoded body redaction --------------------------------------------
def test_redact_query_masks_client_secret_by_name():
    r = DefaultRedactor()
    out = r.redact_query("grant_type=client_credentials&client_secret=topsecretvalue&x=1")
    assert "topsecretvalue" not in out
    assert "[REDACTED]" in out


def test_scan_query_flags_and_is_clean_after():
    r = DefaultRedactor()
    body = "grant_type=x&password=hunter2pw"
    assert r.scan_query(body)
    assert r.scan_query(r.redact_query(body)) == []


# -- extended field names / JWT ------------------------------------------------
def test_token_and_id_token_field_names_masked():
    r = DefaultRedactor()
    out = r.redact_obj({"token": "opaqueSessionValue", "id_token": "anything", "keep": "hi"})
    assert out["token"] == "[REDACTED]"
    assert out["id_token"] == "[REDACTED]"
    assert out["keep"] == "hi"


def test_jwt_value_is_redacted():
    r = DefaultRedactor()
    jwt = ("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
           ".eyJzdWIiOiIxMjM0NTY3ODkwIn0"
           ".dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U")
    assert r.redact_text(f"token={jwt}") != f"token={jwt}"
    assert jwt not in r.redact_text(jwt)


def test_shaped_token_in_unlisted_header_is_stripped():
    # A secret-shaped token in a header we don't know by name should still be
    # scrubbed out of the recording (not just flagged by verify).
    r = DefaultRedactor()
    out = r.redact_headers({"X-Custom": "key sk-ant-" + "a" * 24 + " end", "X-Keep": "plain"})
    assert "sk-ant-" not in out["X-Custom"]
    assert out["X-Keep"] == "plain"


def test_jwt_pattern_no_catastrophic_backtracking():
    import time
    r = DefaultRedactor()
    payload = "eyJ" + "A" * 200000  # long run that must not hang the JWT regex
    start = time.perf_counter()
    r.redact_text(payload)
    assert time.perf_counter() - start < 1.0
