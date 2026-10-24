import json

import pytest

from core.errors import EmptyResponse, NotAuthenticated, ProviderError, ProviderTimeout, RateLimited, UsageLimitReached
from core.providers.parsers import (
    AgyStreamParser,
    ClaudeStreamParser,
    CodexJsonlParser,
    classify_error,
    make_parser,
)


def _feed_all(parser, lines):
    return [c.text for line in lines if (c := parser.feed(line)) is not None]


# ---------- Claude Code ----------
def test_claude_partial_text_and_result(claude_fixture):
    parser = ClaudeStreamParser()
    chunks = _feed_all(parser, claude_fixture("ok_synthetic.jsonl"))
    assert chunks == ["hola ", "mundo · ñ"]  # thinking_delta y el mensaje completo no se re-emiten
    parser.finish("")
    assert parser.final.text == "hola mundo · ñ"
    assert parser.final.model == "claude-haiku-4-5-20251001"
    assert parser.final.usage.input_tokens == 9800
    assert parser.final.total_cost_usd == pytest.approx(0.0123)


def test_claude_real_not_logged_in_output(claude_fixture):
    with pytest.raises(NotAuthenticated):
        _feed_all(ClaudeStreamParser(), claude_fixture("error_not_logged_in.jsonl"))


def test_claude_usage_limit(claude_fixture):
    with pytest.raises(UsageLimitReached):
        _feed_all(ClaudeStreamParser(), claude_fixture("usage_limit_synthetic.jsonl"))


def test_claude_without_result_fails():
    parser = ClaudeStreamParser()
    assert parser.feed("") is None and parser.feed("aviso no-json") is None
    with pytest.raises(ProviderError):
        parser.finish("")


# ---------- Antigravity (fixtures reales del spike) ----------
def _agy(name, fixtures_dir):
    return (fixtures_dir / "agy_stream" / name).read_text(encoding="utf-8").splitlines()


@pytest.fixture
def fixtures_dir():
    from tests.conftest import FIXTURES

    return FIXTURES


def test_agy_text_deltas_and_usage(fixtures_dir):
    parser = AgyStreamParser()
    chunks = _feed_all(parser, _agy("ok_medium.jsonl", fixtures_dir))
    parser.finish("")
    assert "".join(chunks).strip() == parser.final.text.strip()
    assert "caducidad" in parser.final.text
    assert parser.final.model == "gemini-3.8-flash-medium"
    assert parser.final.usage.input_tokens > 0 and parser.final.usage.output_tokens > 0


def test_agy_json_schema_uses_structured_output(fixtures_dir):
    parser = AgyStreamParser()
    _feed_all(parser, _agy("ok_json_schema.jsonl", fixtures_dir))
    parser.finish("")
    data = json.loads(parser.final.text)  # el "response" crudo trae el JSON duplicado; structured_output no
    assert data["ganador"] in ("DEFENSA", "CONTRAPARTE") and data["resumen"]


def test_agy_tool_attempt_is_reported_and_empty_answer_fails(fixtures_dir):
    parser = AgyStreamParser()
    _feed_all(parser, _agy("tool_denied.jsonl", fixtures_dir))
    assert any("write_file" in a for a in parser.avisos)
    with pytest.raises(EmptyResponse, match="vacía.*herramienta") as exc:
        parser.finish("")
    assert exc.value.degradable  # el router debe probar el siguiente modelo, no abortar la consulta


def test_agy_print_timeout_is_timeout(fixtures_dir):
    parser = AgyStreamParser()
    _feed_all(parser, _agy("timeout_partial.jsonl", fixtures_dir))
    with pytest.raises(ProviderTimeout):
        parser.finish("[agy] print timeout after 4m0s with turn in progress; returning partial output")


def test_agy_failed_status_is_classified():
    line = json.dumps({"event": "result", "result": {"status": "ERROR", "error": "quota exceeded for this plan"}})
    with pytest.raises(UsageLimitReached):
        AgyStreamParser().feed(line)


# ---------- Codex (experimental, eventos sintéticos) ----------
def test_codex_jsonl():
    parser = CodexJsonlParser()
    lines = [
        json.dumps({"type": "thread.started"}),
        json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "hola"}}),
        json.dumps({"type": "turn.completed", "usage": {"input_tokens": 10, "output_tokens": 2}}),
    ]
    assert _feed_all(parser, lines) == ["hola"]
    parser.finish("")
    assert parser.final.text == "hola" and parser.final.usage.output_tokens == 2
    with pytest.raises(NotAuthenticated):
        CodexJsonlParser().feed(json.dumps({"type": "error", "message": "Not logged in. Run codex login"}))


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
    assert type(classify_error(msg, "x")) is cls


def test_make_parser_unknown():
    with pytest.raises(ValueError):
        make_parser("nope", "x")
