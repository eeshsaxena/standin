import pytest

from standin.exceptions import CassetteError
from standin.models import Interaction, RecordedRequest, RecordedResponse
from standin.storage import JSONCassetteStore


def _interaction():
    return Interaction(
        request=RecordedRequest("POST", "http://x/v1", {"content-type": "application/json"}, {"json": {"a": 1}}),
        response=RecordedResponse(200, {"content-type": "application/json"}, {"json": {"ok": True}}),
    )


def test_save_load_roundtrip(tmp_path):
    store = JSONCassetteStore()
    path = tmp_path / "c.json"
    store.save(path, [_interaction()])
    loaded = store.load(path)
    assert len(loaded) == 1
    assert loaded[0].request.method == "POST"
    assert loaded[0].response.body == {"json": {"ok": True}}


def test_missing_file_is_empty(tmp_path):
    assert JSONCassetteStore().load(tmp_path / "nope.json") == []


def test_bad_json_raises(tmp_path):
    p = tmp_path / "c.json"
    p.write_text("{not json", encoding="utf-8")
    with pytest.raises(CassetteError):
        JSONCassetteStore().load(p)


def test_unsupported_version_raises(tmp_path):
    p = tmp_path / "c.json"
    p.write_text('{"version": 999, "interactions": []}', encoding="utf-8")
    with pytest.raises(CassetteError):
        JSONCassetteStore().load(p)


def test_deeply_nested_json_raises_cassette_error(tmp_path):
    # A hostile cassette with pathological nesting must surface as a clean
    # CassetteError, never an uncaught RecursionError / process crash.
    p = tmp_path / "deep.json"
    depth = 30000
    p.write_text(
        '{"version": 1, "interactions": [{"request": {"method":"GET","url":"http://x",'
        '"headers":{},"body":{"json": %s}}, "response":{"status_code":200,"headers":{},'
        '"body":{"empty":true}}}]}' % ("[" * depth + "]" * depth),
        encoding="utf-8",
    )
    with pytest.raises(CassetteError):
        JSONCassetteStore().load(p)
