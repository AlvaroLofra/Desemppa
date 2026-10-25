"""Adaptador genérico para CLIs con modo no interactivo (Claude Code, Antigravity, Codex…), dossier §1.1.3.

- Un único hilo trabajador y un FileLock por proveedor: nunca hay dos procesos del mismo CLI vivos a la vez
  (ni desde otra instancia del backend o el benchmark). CLIs distintos sí pueden trabajar en paralelo.
- El prompt va por stdin (argv en Windows está limitado a 32.767 caracteres).
- cwd = directorio vacío propio de cada proveedor: el CLI no ve el proyecto ni sus ficheros.
- Independiente del tipo de event loop: los tokens vuelven con `call_soon_threadsafe`.
"""

from __future__ import annotations

import asyncio
import json
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

from config.settings import ModelSpec, ProviderSpec
from core.errors import ModelUnavailable, ProviderTimeout
from core.llm_types import LLMRequest, LLMResult, StreamChunk
from core.providers.parsers import CliFinal, make_parser

_CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0
_DONE = object()


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
    temp_files: list[Path] = field(default_factory=list)
    cancelled: threading.Event = field(default_factory=threading.Event)
    proc: _Proc | None = None


def _fill(template: list[str], values: dict[str, str]) -> list[str]:
    out = []
    for arg in template:
        for key, value in values.items():
            arg = arg.replace("{" + key + "}", value)
        out.append(arg)
    return out


class CliAdapter:
    def __init__(
        self,
        provider_id: str,
        spec: ProviderSpec,
        *,
        sandbox_dir: Path,
        lock_path: Path,
        exe: str | None = None,
        popen: PopenFactory = subprocess.Popen,
    ) -> None:
        assert spec.tipo == "cli" and spec.parser and spec.ejecutable
        self.id = provider_id
        self.spec = spec
        self._sandbox = sandbox_dir
        self._lock = FileLock(str(lock_path))
        self._exe = exe
        self._popen = popen
        self._jobs: queue.Queue[_Job | None] = queue.Queue()
        self._thread: threading.Thread | None = None
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        sandbox_dir.mkdir(parents=True, exist_ok=True)

    # ---------- estado y descubrimiento ----------
    def resolve_exe(self) -> str:
        exe = self._exe or shutil.which(self.spec.ejecutable or "")
        if not exe:
            raise ModelUnavailable(f"No se encuentra el ejecutable `{self.spec.ejecutable}`", provider=self.id)
        return exe

    def installed(self) -> bool:
        try:
            self.resolve_exe()
        except ModelUnavailable:
            return False
        return True

    def discover_models(self, timeout_s: float = 60) -> list[str]:
        """Modelos que ofrece el CLI (`descubrir`) o, si no tiene esa orden, los `modelos_conocidos`."""
        if not self.spec.descubrir:
            return list(self.spec.modelos_conocidos)
        out = subprocess.run(
            [self.resolve_exe(), *self.spec.descubrir],
            capture_output=True,
            timeout=timeout_s,
            cwd=str(self._sandbox),
            creationflags=_CREATE_NO_WINDOW,
        )
        models = []
        for line in out.stdout.decode("utf-8", errors="replace").splitlines():
            first = line.split("\t")[0].strip()
            if first and " " not in first and not first.endswith("..."):
                models.append(first)
        return models or list(self.spec.modelos_conocidos)

    # ---------- ciclo de vida ----------
    def start(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run, name=f"{self.id}-worker", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        if self._thread is not None:
            self._jobs.put(None)
            self._thread.join(timeout=5)
            self._thread = None

    # ---------- construcción de la llamada ----------
    def _temp(self, text: str, suffix: str) -> Path:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", suffix=suffix, prefix="tmp_", dir=self._sandbox, delete=False
        ) as fh:
            fh.write(text)
            return Path(fh.name)

    def build_call(self, model: str, request: LLMRequest, timeout_s: float) -> tuple[list[str], str, list[Path]]:
        """Devuelve (argv, texto para stdin, ficheros temporales a borrar)."""
        values = {"model": model, "effort": request.effort, "timeout_inner": str(max(10, int(timeout_s) - 10))}
        args = [self.resolve_exe(), *_fill(self.spec.args, values)]
        temps: list[Path] = []
        prompt = request.prompt
        system = self.spec.prefijo_sistema + request.system
        if system:
            if self.spec.system_prompt == "file" and self.spec.system_prompt_args:
                path = self._temp(system, ".md")
                temps.append(path)
                args += _fill(self.spec.system_prompt_args, {"system_file": str(path)})
            else:
                prompt = f"{system}\n\n---\n\n{prompt}"
        if request.response_schema and self.spec.json_schema_args:
            path = self._temp(json.dumps(request.response_schema, ensure_ascii=False), ".json")
            temps.append(path)
            args += _fill(self.spec.json_schema_args, {"schema_file": str(path)})
        if self.spec.stdin == "agy_ndjson":
            stdin = json.dumps({"event": "user", "message": {"role": "user", "content": prompt}}, ensure_ascii=False)
            stdin += "\n"
        else:
            stdin = prompt
        return args, stdin, temps

    # ---------- API asíncrona ----------
    async def stream(
        self, *, alias: str, spec: ModelSpec, request: LLMRequest
    ) -> AsyncIterator[StreamChunk | LLMResult]:
        self.start()
        model = spec.resolved_id(request.effort)
        args, stdin, temps = self.build_call(model, request, spec.timeout_s)
        job = _Job(
            args=args,
            stdin_text=stdin,
            timeout_s=spec.timeout_s,
            loop=asyncio.get_running_loop(),
            out=asyncio.Queue(),
            temp_files=temps,
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
                if isinstance(item, tuple):  # (CliFinal, avisos)
                    final, avisos = item
                    yield LLMResult(
                        text=final.text,
                        provider=self.id,
                        alias=alias,
                        model=final.model or model,
                        usage=final.usage,
                        coste_equivalente_usd=final.total_cost_usd,
                        latencia_ms=int((time.monotonic() - started) * 1000),
                        avisos=[f"{self.id}: {a}" for a in avisos],
                    )
                else:
                    yield item
        finally:
            if not finished:
                job.cancelled.set()
                if job.proc is not None and job.proc.poll() is None:
                    job.proc.kill()
            for path in temps:
                path.unlink(missing_ok=True)

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
        parser = make_parser(self.spec.parser or "", self.id)
        try:
            assert proc.stdout is not None
            for raw in proc.stdout:
                if job.cancelled.is_set():
                    proc.kill()
                    break
                chunk = parser.feed(raw.decode("utf-8", errors="replace"))
                if chunk is not None:
                    self._post(job, chunk)
            proc.wait()
        finally:
            timer.cancel()
            if proc.poll() is None:  # salida anticipada por error en el parser
                proc.kill()
                proc.wait()
            for t in threads:
                t.join(timeout=2)
        if timed_out.is_set():
            raise ProviderTimeout(f"{self.id} superó {job.timeout_s:.0f} s", provider=self.id)
        if job.cancelled.is_set():
            return
        parser.finish(b"".join(stderr_buf).decode("utf-8", errors="replace").strip())
        assert parser.final is not None
        final: CliFinal = parser.final
        self._post(job, (final, list(parser.avisos)))


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
