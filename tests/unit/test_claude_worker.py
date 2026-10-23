import asyncio
import io
import threading
import time

import pytest

from core.claude_worker import ClaudeWorker
from core.errors import ProviderTimeout
from core.llm_types import LLMRequest, LLMResult, StreamChunk


class FakeProc:
    """Simula `claude -p`: guarda stdin y devuelve las líneas del fixture por stdout."""

    alive = 0
    max_alive = 0
    _guard = threading.Lock()

    def __init__(self, args, lines, *, delay=0.0, hang=False, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self._lines = [line.encode("utf-8") + b"\n" for line in lines]
        self._delay = delay
        self._killed = threading.Event()
        self._hang = hang
        self.returncode = None
        self.stdin = io.BytesIO()
        self.stdin.close = lambda: None  # conservar el contenido para el test
        self.stderr = io.BytesIO(b"")
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


@pytest.fixture
def make_worker(tmp_path, claude_fixture):
    created = []

    def _make(fixture="ok_synthetic.jsonl", **proc_kwargs):
        lines = claude_fixture(fixture)

        def popen(args, **kwargs):
            proc = FakeProc(args, lines, **proc_kwargs, **kwargs)
            created.append(proc)
            return proc

        worker = ClaudeWorker(
            sandbox_dir=tmp_path / "sandbox",
            lock_path=tmp_path / "claude.lock",
            exe="claude.exe",
            popen=popen,
        )
        return worker, created

    FakeProc.alive = FakeProc.max_alive = 0
    return _make


async def _collect(worker, prompt="hola", system="sistema", timeout_s=30):
    items = []
    req = LLMRequest(system=system, prompt=prompt, effort="low")
    async for item in worker.stream(alias="claude_haiku", cli_model="haiku", request=req, timeout_s=timeout_s):
        items.append(item)
    return items


async def test_streams_chunks_then_result(make_worker):
    worker, procs = make_worker()
    items = await _collect(worker)
    worker.stop()
    assert [i.text for i in items if isinstance(i, StreamChunk)] == ["hola ", "mundo · ñ"]
    result = items[-1]
    assert isinstance(result, LLMResult)
    assert result.provider == "claude" and result.model == "claude-haiku-4-5-20251001"
    args = procs[0].args
    assert args[:2] == ["claude.exe", "-p"]
    for flag in ("--include-partial-messages", "--no-session-persistence", "--system-prompt-file"):
        assert flag in args
    assert args[args.index("--tools") + 1] == ""
    assert args[args.index("--effort") + 1] == "low"
    assert procs[0].kwargs["cwd"].endswith("sandbox")


async def test_prompt_goes_via_stdin_not_argv(make_worker):
    worker, procs = make_worker()
    big = "á" * 100_000
    await _collect(worker, prompt=big, system="S" * 50_000)
    worker.stop()
    assert procs[0].stdin.getvalue().decode("utf-8") == big
    assert sum(len(a) for a in procs[0].args) < 1000


async def test_claude_worker_serializes(make_worker):
    worker, procs = make_worker(delay=0.01)
    results = await asyncio.gather(*[_collect(worker) for _ in range(10)])
    worker.stop()
    assert len(procs) == 10
    assert FakeProc.max_alive == 1
    assert all(isinstance(r[-1], LLMResult) for r in results)


async def test_timeout_kills_process(make_worker):
    worker, procs = make_worker(hang=True)
    with pytest.raises(ProviderTimeout):
        await _collect(worker, timeout_s=0.3)
    worker.stop()
    assert procs[0].returncode == -9


async def test_system_prompt_file_removed(make_worker, tmp_path):
    worker, _ = make_worker()
    await _collect(worker)
    worker.stop()
    assert list((tmp_path / "sandbox").glob("sys_*.md")) == []
