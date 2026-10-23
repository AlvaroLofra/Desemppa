"""Backend FastAPI local (dossier §2.4–2.5): REST + SSE, solo loopback, con token local por arranque."""

from __future__ import annotations

import asyncio
import hashlib
import json
import secrets
import subprocess
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware

from config.settings import (
    CONFIG_DIR,
    Catalog,
    Settings,
    get_catalog,
    get_settings,
    load_catalog,
    reset_user_profiles,
    save_user_profiles,
)
from connectors.boe_client import BOEClient, BOERepository
from connectors.cendoj_fetcher import CendojRepository
from connectors.convenios_db import ConveniosRepository
from connectors.embeddings import Embedder, GeminiEmbedder
from connectors.pdf_extractor import extract_pdf
from connectors.retriever import HybridRetriever
from core.calendar_engine import CalendarEngine, CalendarioFestivos, PlazoError
from core.circuit_breaker import CircuitBreaker
from core.errors import ModelUnavailable, ProviderError
from core.gemini_client import GeminiClient
from core.llm_types import LLMRequest, LLMResult
from core.normalize import fold
from core.orchestrator import Orchestrator
from core.orchestrator import Services as PipelineServices
from core.providers.cli_adapter import CliAdapter
from core.providers.registry import ProviderAdapter, build_registry
from core.quota_ledger import QuotaLedger
from core.router import ModelRouter
from core.state import TERMINALES, ConsultaStore, Estado, EventBus
from storage.database import open_database
from storage.lance_schema import JurisprudenciaStore

ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
WEB_DIST = Path(__file__).resolve().parents[1] / "web" / "dist"
MAX_UPLOAD = 20 * 1024 * 1024


@dataclass
class Services:
    settings: Settings
    catalog: Catalog
    breaker: CircuitBreaker
    ledger: QuotaLedger
    gemini: GeminiClient
    router: ModelRouter
    providers: dict[str, ProviderAdapter]
    cli_version: Callable[[str], str | None]
    pipeline: PipelineServices | None = None
    tasks: dict[str, asyncio.Task[None]] = field(default_factory=dict)
    token: str = field(default_factory=lambda: secrets.token_urlsafe(24))


@lru_cache(maxsize=16)
def _cli_version(exe: str) -> str | None:
    try:
        out = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=15, check=True)
        return out.stdout.strip().splitlines()[0] if out.stdout.strip() else None
    except (OSError, subprocess.SubprocessError):
        return None


def build_services(settings: Settings | None = None, catalog: Catalog | None = None) -> Services:
    settings = settings or get_settings()
    catalog = catalog or get_catalog()
    assert settings.sqlite_path is not None and settings.claude_sandbox_dir is not None
    assert settings.lancedb_dir is not None
    con = open_database(settings.sqlite_path)
    breaker = CircuitBreaker(con, default_open_minutes=catalog.circuit_breaker.default_open_minutes)
    ledger = QuotaLedger(con)
    gemini = GeminiClient(
        settings.gemini_api_key,
        daily_count=ledger.daily_count,
        max_retries=catalog.circuit_breaker.gemini_max_retries,
    )
    providers = build_registry(catalog, settings, gemini=gemini, exe_overrides={"claude_cli": settings.claude_exe})
    router = ModelRouter(catalog, providers=providers, breaker=breaker, ledger=ledger)
    embedder: Embedder | None = None
    store: JurisprudenciaStore | None = None
    emb_spec = catalog.models.get("gemini_embedding")
    if settings.gemini_api_key and emb_spec and emb_spec.model_id:
        try:
            embedder = GeminiEmbedder(
                settings.gemini_api_key, model=emb_spec.model_id, dim=emb_spec.output_dimensionality or 768
            )
            store = JurisprudenciaStore(settings.lancedb_dir, dim=embedder.dim)
        except ModelUnavailable:
            embedder = None
    cendoj = CendojRepository(con, store=store, embedder=embedder)
    pipeline = PipelineServices(
        router=router,
        boe=BOERepository(con, BOEClient()),
        retriever=HybridRetriever(con, store=store, embedder=embedder),
        cendoj=cendoj,
        convenios=ConveniosRepository(con),
        calendar=CalendarEngine(CalendarioFestivos(con=con)),
        store=ConsultaStore(con),
        bus=EventBus(con),
    )
    return Services(
        settings=settings,
        catalog=catalog,
        breaker=breaker,
        ledger=ledger,
        gemini=gemini,
        router=router,
        providers=providers,
        cli_version=_cli_version,
        pipeline=pipeline,
    )


# ---------- modelos de petición ----------
class NuevaConsulta(BaseModel):
    texto: str = Field(min_length=10, max_length=20000)
    modo: str = "equilibrado"
    municipio_ine: str | None = Field(default=None, pattern=r"^\d{5}$")
    adjuntos: list[str] = Field(default_factory=list, max_length=5)


class Respuesta(BaseModel):
    pregunta: str
    respuesta: str = Field(max_length=2000)
    municipio_ine: str | None = Field(default=None, pattern=r"^\d{5}$")


class Aclaraciones(BaseModel):
    respuestas: list[Respuesta] = Field(min_length=1, max_length=8)


def _estado_proveedor(s: Services, pid: str) -> dict[str, Any]:
    spec = s.catalog.providers[pid]
    adapter = s.providers.get(pid)
    instalado = adapter.installed() if adapter is not None else False
    version = None
    if instalado and isinstance(adapter, CliAdapter):
        version = s.cli_version(adapter.resolve_exe())
    return {
        "etiqueta": spec.etiqueta,
        "tipo": spec.tipo,
        "habilitado": spec.habilitado,
        "instalado": instalado,
        "version": version,
        "ultima_llamada": s.ledger.last_call(pid),
        "breaker": s.breaker.snapshot(pid),
        "uso_ultimas_5h": s.ledger.window_usage(pid),
        "login": spec.login,
        "modelos": [a for a, m in s.catalog.models.items() if m.provider == pid],
    }


def create_app(services_factory: Callable[[], Services] = build_services) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        services = services_factory()
        if services.pipeline is not None:
            services.pipeline.store.recover_interrupted()
        app.state.services = services
        try:
            yield
        finally:
            for task in services.tasks.values():
                task.cancel()
            for adapter in services.providers.values():
                adapter.stop()

    app = FastAPI(title="Iuris-IA", version="0.2.0", lifespan=lifespan)
    # Protección frente a DNS rebinding: solo se aceptan peticiones dirigidas a loopback (dossier §2.5).
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)

    def svc(request: Request) -> Services:
        return request.app.state.services  # type: ignore[no-any-return]

    def pipe(request: Request) -> PipelineServices:
        s = svc(request)
        if s.pipeline is None:
            raise HTTPException(503, "pipeline no inicializado")
        return s.pipeline

    def require_token(request: Request, x_iuris_token: str | None = Header(default=None)) -> None:
        if not secrets.compare_digest(x_iuris_token or "", svc(request).token):
            raise HTTPException(403, "token local inválido")

    def _launch(s: Services, consulta_id: str) -> None:
        assert s.pipeline is not None
        running = s.tasks.get(consulta_id)
        if running and not running.done():
            raise HTTPException(409, "la consulta ya se está procesando")
        s.tasks[consulta_id] = asyncio.create_task(Orchestrator(s.pipeline).run(consulta_id))

    @app.get("/api/token")
    def token(request: Request) -> dict[str, str]:
        # Sin cabeceras CORS: solo una página del mismo origen (la propia app) puede leer la respuesta.
        return {"token": svc(request).token}

    @app.get("/api/estado")
    def estado(request: Request) -> dict[str, Any]:
        s = svc(request)
        corpus = None
        if s.pipeline is not None:
            corpus = {
                "sentencias": s.pipeline.cendoj.count(),
                "municipios": len(s.pipeline.calendar.festivos.municipios),
                "anios_festivos": sorted(s.pipeline.calendar.festivos.years_nacional),
            }
        return {
            "proveedores": {pid: _estado_proveedor(s, pid) for pid in s.catalog.providers},
            "modo_por_defecto": s.catalog.default_profile(),
            "modos": {
                name: {
                    "label": p.label,
                    "llamadas_claude_por_consulta": p.claude_calls_per_query,
                    "roles": {r: a.model_dump() for r, a in p.roles.items()},
                }
                for name, p in s.catalog.profiles.items()
            },
            "modelos": {
                alias: {"proveedor": m.provider, "id": m.model_id, "etiqueta": m.etiqueta}
                for alias, m in s.catalog.models.items()
            },
            "corpus": corpus,
        }

    # ---------- proveedores y asignación de modelos ----------
    @app.get("/api/proveedores")
    def proveedores(request: Request) -> dict[str, Any]:
        s = svc(request)
        return {pid: _estado_proveedor(s, pid) for pid in s.catalog.providers}

    @app.post("/api/proveedores/{pid}/detectar", dependencies=[Depends(require_token)])
    async def detectar(pid: str, request: Request) -> dict[str, Any]:
        s = svc(request)
        adapter = s.providers.get(pid)
        if adapter is None:
            raise HTTPException(404, "proveedor desactivado o desconocido")
        if not adapter.installed():
            return {"instalado": False, "modelos": []}
        try:
            modelos = await asyncio.to_thread(adapter.discover_models)
        except (OSError, subprocess.SubprocessError) as exc:
            raise HTTPException(502, f"no se pudieron listar los modelos: {exc}") from exc
        return {"instalado": True, "modelos": modelos}

    @app.post("/api/modelos/{alias}/probar", dependencies=[Depends(require_token)])
    async def probar(alias: str, request: Request) -> dict[str, Any]:
        s = svc(request)
        spec = s.catalog.models.get(alias)
        if spec is None:
            raise HTTPException(404, "modelo desconocido")
        adapter = s.providers.get(spec.provider)
        if adapter is None:
            raise HTTPException(409, f"el proveedor {spec.provider} está desactivado")
        req = LLMRequest(prompt="Responde exactamente con la palabra: OK", effort=spec.efforts[0])
        started = time.monotonic()
        texto, ok, error = "", True, None
        try:
            async for item in adapter.stream(alias=alias, spec=spec, request=req):
                if isinstance(item, LLMResult):
                    texto = item.text
        except ProviderError as exc:
            ok, error = False, f"{type(exc).__name__}: {str(exc)[:300]}"
        ms = int((time.monotonic() - started) * 1000)
        s.ledger.record(
            fase="prueba",
            proveedor=spec.provider,
            modelo=spec.resolved_id(req.effort),
            latencia_ms=ms,
            ok=ok,
            error_tipo=error.split(":")[0] if error else None,
        )
        return {"ok": ok, "latencia_ms": ms, "respuesta": texto[:200], "error": error}

    @app.get("/api/ajustes/perfiles")
    def perfiles(request: Request) -> dict[str, Any]:
        s = svc(request)
        defecto = load_catalog(CONFIG_DIR, user_overrides=False)
        return {
            "modos": {n: {r: a.model_dump() for r, a in p.roles.items()} for n, p in s.catalog.profiles.items()},
            "por_defecto": {n: {r: a.model_dump() for r, a in p.roles.items()} for n, p in defecto.profiles.items()},
            "modelos": {
                alias: {
                    "etiqueta": m.etiqueta or alias,
                    "proveedor": m.provider,
                    "efforts": m.efforts,
                    "disponible": m.provider in s.providers and s.providers[m.provider].installed(),
                }
                for alias, m in s.catalog.models.items()
                if alias != "gemini_embedding"
            },
        }

    @app.put("/api/ajustes/perfiles", dependencies=[Depends(require_token)])
    def guardar_perfiles(body: dict[str, dict[str, dict[str, str]]], request: Request) -> dict[str, str]:
        s = svc(request)
        try:
            nuevo = save_user_profiles(body)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        s.catalog = nuevo
        s.router.catalog = nuevo
        return {"estado": "guardado"}

    @app.delete("/api/ajustes/perfiles", dependencies=[Depends(require_token)])
    def restablecer_perfiles(request: Request) -> dict[str, str]:
        s = svc(request)
        reset_user_profiles()
        s.catalog = load_catalog()
        s.router.catalog = s.catalog
        return {"estado": "restablecido"}

    # ---------- consultas ----------
    @app.post("/api/consultas", status_code=201, dependencies=[Depends(require_token)])
    def crear(body: NuevaConsulta, request: Request) -> dict[str, str]:
        s = svc(request)
        p = pipe(request)
        if body.modo not in s.catalog.profiles:
            raise HTTPException(422, f"modo desconocido: {body.modo}")
        consulta_id = p.store.create(body.texto, body.modo, municipio_ine=body.municipio_ine, adjuntos=body.adjuntos)
        _launch(s, consulta_id)
        return {"consulta_id": consulta_id}

    @app.post("/api/consultas/{consulta_id}/aclaraciones", dependencies=[Depends(require_token)])
    def aclarar(consulta_id: str, body: Aclaraciones, request: Request) -> dict[str, str]:
        s, p = svc(request), pipe(request)
        try:
            c = p.store.get(consulta_id)
        except KeyError as exc:
            raise HTTPException(404, "consulta no encontrada") from exc
        if c.estado != Estado.ESPERANDO_ACLARACION:
            raise HTTPException(409, f"la consulta está en estado {c.estado}")
        p.store.add_aclaraciones(consulta_id, [r.model_dump() for r in body.respuestas])
        _launch(s, consulta_id)
        return {"consulta_id": consulta_id, "estado": "reanudada"}

    @app.get("/api/consultas")
    def listar(request: Request) -> list[dict[str, Any]]:
        return pipe(request).store.listar()

    @app.get("/api/consultas/{consulta_id}")
    def detalle(consulta_id: str, request: Request) -> dict[str, Any]:
        p = pipe(request)
        try:
            c = p.store.get(consulta_id)
        except KeyError as exc:
            raise HTTPException(404, "consulta no encontrada") from exc
        return {
            "consulta_id": c.consulta_id,
            "modo": c.modo,
            "estado": c.estado,
            "triage": c.triage,
            "dossier": c.dossier,
            "debate": c.debate,
            "dictamen": c.dictamen,
            "texto": p.store.restore_pii(consulta_id, c.texto_seudonimizado),
            "adjuntos": [{k: a[k] for k in ("adjunto_id", "nombre", "tipo")} for a in c.adjuntos],
        }

    @app.get("/api/consultar/stream/{consulta_id}")
    async def stream(
        consulta_id: str,
        request: Request,
        token: str = Query(default=""),
        after_seq: int = Query(default=0, alias="after", ge=0),
        last_event_id: str | None = Header(default=None),
    ) -> EventSourceResponse:
        s, p = svc(request), pipe(request)
        if not secrets.compare_digest(token, s.token):
            raise HTTPException(403, "token local inválido")
        try:
            c = p.store.get(consulta_id)
        except KeyError as exc:
            raise HTTPException(404, "consulta no encontrada") from exc
        after = max(after_seq, int(last_event_id) if last_event_id and last_event_id.isdigit() else 0)

        async def gen() -> AsyncIterator[dict[str, str]]:
            queue = p.bus.subscribe(consulta_id)
            try:
                last = after
                for seq, tipo, data in p.bus.history(consulta_id, after):
                    last = seq
                    yield {"id": str(seq), "event": tipo, "data": json.dumps(data, ensure_ascii=False, default=str)}
                estado_actual = p.store.get(consulta_id).estado
                if estado_actual in TERMINALES or estado_actual == Estado.ESPERANDO_ACLARACION:
                    task = s.tasks.get(consulta_id)
                    if task is None or task.done():
                        return
                while True:
                    try:
                        seq, tipo, data = await asyncio.wait_for(queue.get(), timeout=15)
                    except TimeoutError:
                        yield {"event": "heartbeat", "data": "{}"}
                        continue
                    if seq <= last and tipo not in ("token", "debate_delta"):
                        continue
                    last = max(last, seq)
                    yield {"id": str(seq), "event": tipo, "data": json.dumps(data, ensure_ascii=False, default=str)}
                    if tipo in ("final", "error", "clarification_needed"):
                        return
            finally:
                p.bus.unsubscribe(consulta_id, queue)

        del c
        return EventSourceResponse(gen(), ping=20)

    # ---------- adjuntos y fuentes ----------
    @app.post("/api/adjuntos", status_code=201, dependencies=[Depends(require_token)])
    async def subir(
        request: Request, archivo: UploadFile = File(...), permitir_envio: bool = Form(default=False)
    ) -> dict[str, Any]:
        p = pipe(request)
        data = await archivo.read(MAX_UPLOAD + 1)
        if len(data) > MAX_UPLOAD:
            raise HTTPException(413, "máximo 20 MB")
        nombre = archivo.filename or "documento"
        if nombre.lower().endswith(".pdf") or data[:4] == b"%PDF":
            ext = extract_pdf(data)
            texto, ocr, pendientes = ext.text, ext.ocr_used, ext.ocr_pending
        elif nombre.lower().endswith((".txt", ".md")):
            texto, ocr, pendientes = data.decode("utf-8", errors="replace"), False, []
        else:
            raise HTTPException(415, "formatos admitidos: PDF o TXT")
        if not texto.strip():
            raise HTTPException(422, "no se ha podido extraer texto (¿PDF escaneado sin OCR instalado?)")
        info = p.store.add_adjunto(
            nombre, hashlib.sha256(data).hexdigest(), texto, ocr_usado=ocr, permitir_envio=permitir_envio
        )
        return {**info, "caracteres": len(texto), "paginas_sin_texto": pendientes, "permitir_envio": permitir_envio}

    @app.get("/api/fuentes")
    async def fuente(
        request: Request, source_id: str, consulta_id: str | None = None, quote: str | None = None
    ) -> dict[str, Any]:
        """Texto completo de una fuente del dossier (o del BOE/corpus) con el rango citado resaltable."""
        p = pipe(request)
        texto, titulo, url = None, source_id, None
        if consulta_id:
            c = p.store.get(consulta_id)
            for grupo in ("articulos_boe", "sentencias", "clausulas_convenio", "extractos_adjuntos"):
                for f in (c.dossier or {}).get(grupo, []):
                    if f["source_id"] == source_id:
                        texto, titulo, url = f["texto_verbatim"], f["titulo"], f.get("url_oficial")
        if texto is None and source_id.startswith("ROJ:"):
            det = p.cendoj.detalle(source_id[4:])
            if det:
                texto, url = det["fundamentos"], det["url"]
        if texto is None and source_id.startswith("BOE:"):
            _, id_norma, id_bloque, *_ = source_id.split(":")
            bloque = await p.boe.get_bloque(id_norma, id_bloque)
            texto, titulo = bloque.versiones[-1].texto, bloque.titulo
            url = f"https://www.boe.es/buscar/act.php?id={id_norma}#{id_bloque}"
        if texto is None:
            raise HTTPException(404, "fuente no encontrada")
        highlight = None
        if quote:
            from core.validators import verify_quote

            chk = verify_quote(quote, texto)
            highlight = {"offsets": chk.offsets, "score": round(chk.score, 1), "ok": chk.ok}
        return {"source_id": source_id, "titulo": titulo, "texto": texto, "url": url, "resaltado": highlight}

    # ---------- calendario, municipios y convenios ----------
    @app.get("/api/calendario/plazo")
    def plazo(
        request: Request, tipo: str, fecha_inicio: date, municipio_ine: str | None = None, foral: str | None = None
    ) -> dict[str, Any]:
        cal = pipe(request).calendar
        try:
            r = cal.compute(tipo, fecha_inicio, municipio_ine=municipio_ine, territorio_foral=foral, hoy=date.today())
        except PlazoError as exc:
            raise HTTPException(422, str(exc)) from exc
        return r.model_dump(mode="json")

    @app.get("/api/calendario/tipos")
    def tipos_plazo(request: Request) -> list[dict[str, str]]:
        return [
            {"id": r.id, "descripcion": r.descripcion, "base_legal": r.base_legal}
            for r in pipe(request).calendar.rules.values()
        ]

    @app.get("/api/municipios")
    def municipios(request: Request, q: str = Query(min_length=2)) -> list[dict[str, str]]:
        target = fold(q)
        out = []
        for m in pipe(request).calendar.festivos.municipios.values():
            if target in fold(m.nombre):
                out.append({"codigo_ine": m.codigo_ine, "nombre": m.nombre, "provincia": m.provincia})
        out.sort(key=lambda m: (not fold(m["nombre"]).startswith(target), len(m["nombre"])))
        return out[:15]

    @app.get("/api/convenios")
    def convenios(request: Request, sector: str | None = None, territorio: str | None = None) -> list[dict[str, Any]]:
        return pipe(request).convenios.listar(sector, territorio)

    @app.post("/api/jurisprudencia/importar", status_code=201, dependencies=[Depends(require_token)])
    async def importar(request: Request, archivo: UploadFile = File(...)) -> dict[str, Any]:
        p = pipe(request)
        data = await archivo.read(MAX_UPLOAD + 1)
        if len(data) > MAX_UPLOAD:
            raise HTTPException(413, "máximo 20 MB")
        try:
            if data[:4] == b"%PDF":
                res = await p.cendoj.import_pdf(data)
            else:
                res = await p.cendoj.import_text(data.decode("utf-8", errors="replace"))
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        return {"roj": res.roj_id, "nueva": res.nueva, "chunks": res.chunks_indexados, "avisos": res.avisos}

    # ---------- frontend ----------
    if (WEB_DIST / "index.html").exists():
        app.mount("/assets", StaticFiles(directory=WEB_DIST / "assets"), name="assets")

        @app.get("/", response_class=HTMLResponse)
        def index(request: Request) -> str:
            html = (WEB_DIST / "index.html").read_text(encoding="utf-8")
            return html.replace("__IURIS_TOKEN__", svc(request).token)

        @app.get("/{path:path}", response_model=None)
        def static_files(path: str, request: Request) -> FileResponse | HTMLResponse:
            target = (WEB_DIST / path).resolve()
            if path.startswith("api/"):
                raise HTTPException(404)
            if path == "index.html":
                return HTMLResponse(index(request))
            if target.is_file() and WEB_DIST.resolve() in target.parents:
                return FileResponse(target)
            return HTMLResponse(index(request))

    return app


app = create_app()
