"""Adaptador CLI genérico con un proceso simulado, para Claude Code y Antigravity."""

import asyncio
import io
import json
import threading
import time

import pytest

from config.settings import ModelSpec
from core.errors import ProviderTimeout
from core.llm_types import LLMRequest, LLMResult, StreamChunk
from core.providers.cli_adapter import CliAdapter
from tests.conftest import FIXTURES


class FakeProc:
    alive = 0
    max_alive = 0
    _guard = threading.Lock()

    def __init__(self, args, lines, *, delay=0.0, hang=False, stderr_data=b"", **kwargs):
        self.args = args
        self.kwargs = kwargs
        self._lines = [line.encode("utf-8") + b"\n" for line in lines]
        self._delay = delay
        self._killed = threading.Event()
        self._hang = hang
        self.returncode = None
        self.stdin = io.BytesIO()
        self.stdin.close = lambda: None  # conservar el contenido para el test
        self.stderr = io.BytesIO(stderr_data)
        with FakeProc._guard:
            FakeProc.alive += 1
            FakeProc.max_alive = max(FakeProc.max_alive, FakeProc.alive)

    @property
    def stdout(self):
        def gen():
            if self._hang:
                self._killed.wait(10)
                return
            for line in self._lines:
                time.sleep(self._delay)
                yield line

        return gen()

    def _finish(self, code):
        if self.returncode is None:
            self.returncode = code
            with FakeProc._guard:
                FakeProc.alive -= 1

    def wait(self, timeout=None):
        self._finish(-9 if self._killed.is_set() else 0)
        return self.returncode

    def kill(self):
        self._killed.set()

    def poll(self):
        return self.returncode


CASES = {
    "claude_cli": (FIXTURES / "claude_stream" / "ok_synthetic.jsonl", "sonnet"),
    "antigravity_cli": (FIXTURES / "agy_stream" / "ok_medium.jsonl", "gemini-3.8-flash-{effort}"),
}


@pytest.fixture
def make_adapter(tmp_path, catalog):
    created = []

    def _make(pid="claude_cli", fixture=None, **proc_kwargs):
        lines = (fixture or CASES[pid][0]).read_text(encoding="utf-8").splitlines()

        def popen(args, **kwargs):
            proc = FakeProc(args, lines, **proc_kwargs, **kwargs)
            created.append(proc)
            return proc

        adapter = CliAdapter(
            pid,
            catalog.providers[pid],
            sandbox_dir=tmp_path / f"sb_{pid}",
            lock_path=tmp_path / f"{pid}.lock",
            exe=f"{pid}.exe",
            popen=popen,
        )
        spec = ModelSpec(provider=pid, model_id=CASES[pid][1], timeout_s=30)
        return adapter, spec, created

    FakeProc.alive = FakeProc.max_alive = 0
    return _make


async def _collect(adapter, spec, prompt="hola", system="sistema", effort="low", schema=None):
    req = LLMRequest(system=system, prompt=prompt, effort=effort, response_schema=schema)
    return [i async for i in adapter.stream(alias="x", spec=spec, request=req)]


async def test_claude_args_and_result(make_adapter):
    adapter, spec, procs = make_adapter("claude_cli")
    items = await _collect(adapter, spec)
    adapter.stop()
    assert [i.text for i in items if isinstance(i, StreamChunk)] == ["hola ", "mundo · ñ"]
    assert isinstance(items[-1], LLMResult) and items[-1].provider == "claude_cli"
    args = procs[0].args
    assert args[:2] == ["claude_cli.exe", "-p"] and args[args.index("--model") + 1] == "sonnet"
    assert args[args.index("--tools") + 1] == "" and "--system-prompt-file" in args
    assert procs[0].stdin.getvalue().decode() == "hola"  # el system va por fichero, no por stdin
    assert procs[0].kwargs["cwd"].endswith("sb_claude_cli")


async def test_agy_ndjson_stdin_inline_system_and_effort_in_model(make_adapter):
    adapter, spec, procs = make_adapter("antigravity_cli")
    items = await _collect(adapter, spec, prompt="consulta", system="eres un jurista", effort="medium")
    adapter.stop()
    args = procs[0].args
    assert args[args.index("--model") + 1] == "gemini-3.8-flash-medium"
    assert args[-1] == "-p=" and "--print-timeout" in args
    msg = json.loads(procs[0].stdin.getvalue().decode("utf-8"))
    assert msg["event"] == "user" and msg["message"]["content"].startswith("eres un jurista")
    assert msg["message"]["content"].endswith("consulta")
    assert isinstance(items[-1], LLMResult) and "caducidad" in items[-1].text


async def test_agy_json_schema_file(make_adapter, tmp_path):
    adapter, spec, procs = make_adapter("antigravity_cli", fixture=FIXTURES / "agy_stream" / "ok_json_schema.jsonl")
    items = await _collect(adapter, spec, schema={"type": "object"})
    adapter.stop()
    args = procs[0].args
    assert "--json-schema" in args
    assert json.loads(items[-1].text)["ganador"]
    assert not list((tmp_path / "sb_antigravity_cli").glob("tmp_*"))  # temporales borrados


@pytest.mark.parametrize("pid", ["claude_cli", "antigravity_cli"])
async def test_prompt_goes_via_stdin_not_argv(make_adapter, pid):
    adapter, spec, procs = make_adapter(pid)
    big = "á" * 100_000
    await _collect(adapter, spec, prompt=big, system="S" * 50_000)
    adapter.stop()
    assert big in procs[0].stdin.getvalue().decode("utf-8")
    assert sum(len(a) for a in procs[0].args) < 1000


@pytest.mark.parametrize("pid", ["claude_cli", "antigravity_cli"])
async def test_serializes_per_provider(make_adapter, pid):
    adapter, spec, procs = make_adapter(pid, delay=0.005)
    results = await asyncio.gather(*[_collect(adapter, spec) for _ in range(8)])
    adapter.stop()
    assert len(procs) == 8 and FakeProc.max_alive == 1
    assert all(isinstance(r[-1], LLMResult) for r in results)


async def test_two_providers_run_in_parallel(make_adapter):
    a1, s1, _ = make_adapter("claude_cli", delay=0.02)
    a2, s2, _ = make_adapter("antigravity_cli", delay=0.02)
    await asyncio.gather(_collect(a1, s1), _collect(a2, s2))
    a1.stop()
    a2.stop()
    assert FakeProc.max_alive == 2


async def test_timeout_kills_process(make_adapter):
    adapter, spec, procs = make_adapter("claude_cli", hang=True)
    spec = spec.model_copy(update={"timeout_s": 0.3})
    with pytest.raises(ProviderTimeout):
        await _collect(adapter, spec)
    adapter.stop()
    assert procs[0].returncode == -9


def test_discover_models_static_and_installed(make_adapter, catalog):
    adapter, _, _ = make_adapter("claude_cli")
    assert adapter.discover_models() == ["haiku", "sonnet", "opus"]
    assert adapter.installed()
