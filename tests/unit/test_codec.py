from standin import _codec


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
