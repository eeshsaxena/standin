from standin import _codec
from standin.redaction import DefaultRedactor


def test_json_roundtrip():
    enc = _codec.encode_body(b'{"a": 1}', "application/json")
    assert enc == {"json": {"a": 1}}
    assert _codec.decode_body(enc) == b'{"a": 1}'


def test_json_without_content_type_is_sniffed():
    assert "json" in _codec.encode_body(b'{"a":1}', "")


def test_text_roundtrip():
    enc = _codec.encode_body(b"hello", "text/plain")
    assert enc == {"text": "hello"}
    assert _codec.decode_body(enc) == b"hello"


def test_empty_body():
    assert _codec.encode_body(b"", "application/json") == {"empty": True}
    assert _codec.decode_body({"empty": True}) == b""


def test_binary_falls_back_to_base64():
    raw = b"\xff\xfe\x00\x01"
    enc = _codec.encode_body(raw, "application/octet-stream")
    assert "b64" in enc
    assert _codec.decode_body(enc) == raw


def test_canonical_live_matches_stored_regardless_of_key_order():
    live = _codec.canonical_live(b'{"b": 2, "a": 1}', "application/json")
    stored = _codec.canonical_stored({"json": {"a": 1, "b": 2}})
    assert live == stored


def test_invalid_json_with_json_content_type_falls_back_to_text():
    # The content-type claims JSON but the bytes don't parse: keep them as text
    # rather than losing the body.
    enc = _codec.encode_body(b"{not valid json", "application/json")
    assert enc == {"text": "{not valid json"}
    assert _codec.canonical_live(b"{not valid json", "application/json") == "{not valid json"


def test_decode_unrecognized_body_is_empty_bytes():
    assert _codec.decode_body({}) == b""
    assert _codec.decode_body({"surprise": 1}) == b""


def test_canonical_empty_bodies_are_the_empty_string():
    assert _codec.canonical_live(b"", "application/json") == ""
    assert _codec.canonical_stored({}) == ""
    assert _codec.canonical_stored({"empty": True}) == ""


def test_binary_body_canonicalizes_the_same_live_and_stored():
    # A non-UTF-8, non-JSON body must produce the same canonical form on record
    # (stored) and on replay (live), or a binary upload could never re-match.
    raw = b"\xff\xfe\x00\x01binary"
    stored = _codec.canonical_stored(_codec.encode_body(raw, "application/octet-stream"))
    live = _codec.canonical_live(raw, "application/octet-stream")
    assert live == stored
    assert live  # base64, non-empty


def test_canonical_stored_unrecognized_is_empty_string():
    assert _codec.canonical_stored({"surprise": 1}) == ""


def test_form_urlencoded_body_redacts_secret_by_key_name():
    # A form-encoded OAuth token exchange must not leave client_secret in the clear;
    # field-name redaction (not just token shapes) has to reach form bodies.
    r = DefaultRedactor()
    raw = b"grant_type=client_credentials&client_secret=plainsecretvalue&client_id=abc"
    enc = _codec.encode_body(raw, "application/x-www-form-urlencoded", r)
    assert "plainsecretvalue" not in enc["text"]
    assert "[REDACTED]" in enc["text"]
    assert "client_id=abc" in enc["text"]


def test_form_urlencoded_live_and_stored_canonicalize_the_same():
    # Record and replay must produce the same canonical form for a form body that
    # carried a secret, or a redacted recording could never re-match.
    r = DefaultRedactor()
    raw = b"client_secret=plainsecretvalue&x=1"
    stored = _codec.canonical_stored(_codec.encode_body(raw, "application/x-www-form-urlencoded", r))
    live = _codec.canonical_live(raw, "application/x-www-form-urlencoded", r)
    assert live == stored
    assert "plainsecretvalue" not in live
