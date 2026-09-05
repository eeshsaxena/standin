from standin.cassette import Cassette
from standin.models import Interaction, RawRequest, RecordedRequest, RecordedResponse


def _make(content_id):
    return Interaction(
        request=RecordedRequest("POST", "http://x", {}, {"json": {"q": content_id}}),
        response=RecordedResponse(200, {}, {"json": {"id": content_id}}),
    )


def _matches_q(qval):
    def m(live, stored):
        return stored.body["json"]["q"] == qval
    return m


LIVE = RawRequest("POST", "http://x", {}, b"")


def test_append_marks_dirty_and_counts_preexisting():
    c = Cassette(path="x", interactions=[_make("a")])
    assert c.preexisting == 1
    assert c.dirty is False
    c.append(_make("b"))
    assert c.dirty is True
    assert len(c.interactions) == 2


def test_find_unplayed_consumes_in_order():
    c = Cassette(path="x", interactions=[_make("same"), _make("same")])
    m = _matches_q("same")
    first = c.find_unplayed(m, LIVE)
    second = c.find_unplayed(m, LIVE)
    third = c.find_unplayed(m, LIVE)
    assert first is not None and second is not None
    assert first is not second
    assert third is None  # exhausted


def test_find_unplayed_no_match():
    c = Cassette(path="x", interactions=[_make("a")])
    assert c.find_unplayed(_matches_q("missing"), LIVE) is None
