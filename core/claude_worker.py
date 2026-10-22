"""Cola serializada de `claude -p` (dossier §1.1.3).

- Un único hilo trabajador: nunca hay dos procesos `claude` vivos desde este backend.
- FileLock inter-proceso: tampoco con otra instancia del backend o con el benchmark.
- El prompt va por stdin (argv en Windows está limitado a 32.767 caracteres) y el system
  prompt por fichero (`--system-prompt-file`).
- Independiente del tipo de event loop: los tokens vuelven con `call_soon_threadsafe`.
"""

from __future__ import annotations

import asyncio
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO, Any, Protocol

from filelock import FileLock

from core.errors import ModelUnavailable, ProviderError, ProviderTimeout
from core.llm_types import LLMRequest, LLMResult, StreamChunk
from core.stream_json import ClaudeFinal, StreamJsonParser

_CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


class _Proc(Protocol):
    stdin: IO[bytes] | None
    stdout: IO[bytes] | None
    stderr: IO[bytes] | None

    def wait(self, timeout: float | None = ...) -> int: ...
    def kill(self) -> None: ...
    def poll(self) -> int | None: ...


PopenFactory = Callable[..., _Proc]


@dataclass
class _Job:
    args: list[str]
    stdin_text: str
    timeout_s: float
    loop: asyncio.AbstractEventLoop
    out: asyncio.Queue[Any]
    cancelled: threading.Event = field(default_factory=threading.Event)
    proc: _Proc | None = None


_DONE = object()


def build_args(exe: str, cli_model: str, effort: str, system_prompt_file: Path | None) -> list[str]:
    args = [
        exe, "-p",
        "--model", cli_model,
        "--effort", effort,
        "--output-format", "stream-json",
        "--verbose",
        "--include-partial-messages",
        "--tools", "",
        "--no-session-persistence",
    ]
    if system_prompt_file is not None:
        args += ["--system-prompt-file", str(system_prompt_file)]
    return args


class ClaudeWorker:
    def __init__(
        self,
        *,
        sandbox_dir: Path,
        lock_path: Path,
        exe: str | None = None,
        popen: PopenFactory = subprocess.Popen,
    ) -> None:
        self._sandbox = sandbox_dir
        self._lock = FileLock(str(lock_path))
        self._exe = exe
        self._popen = popen
        self._jobs: queue.Queue[_Job | None] = queue.Queue()
        self._thread: threading.Thread | None = None
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        sandbox_dir.mkdir(parents=True, exist_ok=True)

    # ---------- ciclo de vida ----------
    def resolve_exe(self) -> str:
        exe = self._exe or shutil.which("claude")
        if not exe:
            raise ModelUnavailable("No se encuentra el ejecutable `claude` en el PATH", provider="claude")
        return exe

    def start(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run, name="claude-worker", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        if self._thread is not None:
            self._jobs.put(None)
            self._thread.join(timeout=5)
            self._thread = None

    # ---------- API asíncrona ----------
    async def stream(
        self, *, alias: str, cli_model: str, request: LLMRequest, timeout_s: float
    ) -> AsyncIterator[StreamChunk | LLMResult]:
        self.start()
        exe = self.resolve_exe()
        system_file = self._write_system_prompt(request.system) if request.system else None
        job = _Job(
            args=build_args(exe, cli_model, request.effort, system_file),
            stdin_text=request.prompt,
            timeout_s=timeout_s,
            loop=asyncio.get_running_loop(),
            out=asyncio.Queue(),
        )
        started = time.monotonic()
        self._jobs.put(job)
        finished = False
        try:
            while True:
                item = await job.out.get()
                if item is _DONE:
                    finished = True
                    return
                if isinstance(item, BaseException):
                    finished = True
                    raise item
                if isinstance(item, ClaudeFinal):
                    yield LLMResult(
                        text=item.text,
                        provider="claude",
                        alias=alias,
                        model=item.model or cli_model,
                        usage=item.usage,
                        coste_equivalente_usd=item.total_cost_usd,
                        latencia_ms=int((time.monotonic() - started) * 1000),
                    )
                else:
                    yield item
        finally:
            if not finished:
                job.cancelled.set()
                if job.proc is not None and job.proc.poll() is None:
                    job.proc.kill()
            if system_file is not None:
                system_file.unlink(missing_ok=True)

    def _write_system_prompt(self, text: str) -> Path:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", suffix=".md", prefix="sys_", dir=self._sandbox, delete=False
        ) as fh:
            fh.write(text)
            return Path(fh.name)

    # ---------- hilo trabajador ----------
    def _run(self) -> None:
        while True:
            job = self._jobs.get()
            if job is None:
                return
            if job.cancelled.is_set():
                continue
            try:
                with self._lock:
                    self._execute(job)
                self._post(job, _DONE)
            except BaseException as exc:  # noqa: BLE001 — se reenvía al consumidor
                self._post(job, exc)

    @staticmethod
    def _post(job: _Job, item: object) -> None:
        job.loop.call_soon_threadsafe(job.out.put_nowait, item)

    def _execute(self, job: _Job) -> None:
        proc = self._popen(
            job.args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(self._sandbox),
            creationflags=_CREATE_NO_WINDOW,
        )
        job.proc = proc
        timed_out = threading.Event()

        def _on_timeout() -> None:
            timed_out.set()
            proc.kill()

        timer = threading.Timer(job.timeout_s, _on_timeout)
        stderr_buf: list[bytes] = []
        threads = [
            threading.Thread(target=_write_stdin, args=(proc, job.stdin_text), daemon=True),
            threading.Thread(target=_drain, args=(proc.stderr, stderr_buf), daemon=True),
        ]
        timer.start()
        for t in threads:
            t.start()
        parser = StreamJsonParser()
        try:
            assert proc.stdout is not None
            for raw in proc.stdout:
                if job.cancelled.is_set():
                    proc.kill()
                    break
                chunk = parser.feed(raw.decode("utf-8", errors="replace"))
                if chunk is not None:
                    self._post(job, chunk)
            code = proc.wait()
        finally:
            timer.cancel()
            if proc.poll() is None:  # salida anticipada por error en el parser
                proc.kill()
                proc.wait()
            for t in threads:
                t.join(timeout=2)
        if timed_out.is_set():
            raise ProviderTimeout(f"claude -p superó {job.timeout_s:.0f} s", provider="claude")
        if job.cancelled.is_set():
            return
        if parser.final is None:
            err = b"".join(stderr_buf).decode("utf-8", errors="replace").strip()
            raise ProviderError(f"claude -p terminó (código {code}) sin evento result: {err[:500]}",
                                provider="claude")
        self._post(job, parser.final)


def _write_stdin(proc: _Proc, text: str) -> None:
    assert proc.stdin is not None
    try:
        proc.stdin.write(text.encode("utf-8"))
    except (BrokenPipeError, OSError):
        pass
    finally:
        try:
            proc.stdin.close()
        except OSError:
            pass


def _drain(stream: IO[bytes] | None, sink: list[bytes]) -> None:
    if stream is not None:
        sink.append(stream.read())
