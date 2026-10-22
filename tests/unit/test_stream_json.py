import pytest

from core.errors import NotAuthenticated, ProviderError, RateLimited, UsageLimitReached
from core.stream_json import StreamJsonParser, classify_error


def _feed_all(parser, lines):
    return [c.text for line in lines if (c := parser.feed(line)) is not None]


def test_partial_text_and_result(claude_fixture):
    parser = StreamJsonParser()
    chunks = _feed_all(parser, claude_fixture("ok_synthetic.jsonl"))
    assert chunks == ["hola ", "mundo · ñ"]  # thinking_delta y el mensaje completo no se re-emiten
    final = parser.final
    assert final is not None
    assert final.text == "hola mundo · ñ"
    assert final.model == "claude-haiku-4-5-20251001"
    assert final.usage.input_tokens == 9800
    assert final.total_cost_usd == pytest.approx(0.0123)


def test_real_not_logged_in_output(claude_fixture):
    parser = StreamJsonParser()
    with pytest.raises(NotAuthenticated):
        _feed_all(parser, claude_fixture("error_not_logged_in.jsonl"))


def test_usage_limit_maps_to_usage_limit_reached(claude_fixture):
    with pytest.raises(UsageLimitReached):
        _feed_all(StreamJsonParser(), claude_fixture("usage_limit_synthetic.jsonl"))


def test_garbage_lines_ignored():
    parser = StreamJsonParser()
    assert parser.feed("") is None
    assert parser.feed("warning: algo no-json") is None


@pytest.mark.parametrize(
    ("msg", "cls"),
    [
        ("API Error: 529 Overloaded", RateLimited),
        ("You've hit your weekly limit", UsageLimitReached),
        ("Invalid API key · Please run /login", NotAuthenticated),
        ("algo raro", ProviderError),
    ],
)
def test_classify_error(msg, cls):
    assert type(classify_error(msg)) is cls
