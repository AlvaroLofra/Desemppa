"""Backend FastAPI local (dossier §2.4–2.5): REST + SSE con token local; opcionalmente compartido en la LAN."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
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

from api.red_local import INVITADO_RE, EstadoRed, RedLocalMiddleware, Rol
from config.settings import (
    CONFIG_DIR,
    Catalog,
    Settings,
    get_catalog,
    get_settings,
    load_catalog,
    reset_user_models,
    reset_user_profiles,
    save_user_profiles,
    save_user_provider_or_model,
)
from connectors.boe_client import BOEClient, BOERepository
from connectors.cendoj_fetcher import CendojRepository
from connectors.convenios_db import ConveniosRepository
from connectors.embeddings import Embedder, GeminiEmbedder
from connectors.eurlex_client import EURLexError, EURLexRepository
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
from core.providers.http_adapter import ApiKeyStore
from core.providers.registry import ProviderAdapter, build_registry
from core.quota_ledger import QuotaLedger
from core.router import ModelRouter
from core.state import TERMINALES, ConsultaStore, Estado, EventBus
from storage.database import open_database
from storage.lance_schema import JurisprudenciaStore

# IURIS_WEB_DIST permite servir otra copia del build (lo usan los tests E2E).
WEB_DIST = Path(os.environ.get("IURIS_WEB_DIST") or Path(__file__).resolve().parents[1] / "web" / "dist")
MAX_UPLOAD = 20 * 1024 * 1024
NO_CACHE = {"Cache-Control": "no-cache, no-store, must-revalidate"}
log = logging.getLogger("iuris")


def build_id() -> str | None:
    """Identificador del build de web/dist (lo escribe vite.config.ts en version.json)."""
    try:
        return str(json.loads((WEB_DIST / "version.json").read_text(encoding="utf-8"))["build"])
    except (OSError, ValueError, KeyError):
        return None


def configure_logging(data_dir: Path) -> Path:
    """Log de diagnóstico en <data_dir>/logs/iuris.log (403, errores de consulta, proveedores)."""
    path = data_dir / "logs" / "iuris.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    handler: logging.Handler | None = None
    for name in ("iuris", "core", "connectors"):  # la app y el pipeline; no el ruido de librerías
        logger = logging.getLogger(name)
        if any(isinstance(h, logging.FileHandler) and Path(h.baseFilename) == path for h in logger.handlers):
            continue
        if handler is None:
            handler = logging.FileHandler(path, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return path


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
    key_store: ApiKeyStore | None = None
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


def _load_or_create_token(settings: Settings) -> str:
    if settings.sqlite_path is None:
        return secrets.token_urlsafe(24)
    token_file = Path(settings.sqlite_path).parent / "local_token.txt"
    try:
        if token_file.is_file():
            t = token_file.read_text(encoding="utf-8").strip()
            if len(t) >= 16:
                return t
    except OSError:
        pass
    new_token = secrets.token_urlsafe(24)
    try:
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(new_token, encoding="utf-8")
    except OSError:
        pass
    return new_token


def build_services(settings: Settings | None = None, catalog: Catalog | None = None) -> Services:
    settings = settings or get_settings()
    catalog = catalog or get_catalog()
    assert settings.sqlite_path is not None and settings.claude_sandbox_dir is not None
    assert settings.lancedb_dir is not None
    con = open_database(settings.sqlite_path)
    breaker = CircuitBreaker(con, default_open_minutes=catalog.circuit_breaker.default_open_minutes)
    ledger = QuotaLedger(con)
    key_store = ApiKeyStore(settings.data_dir / "provider_keys.bin")
    gemini_key = key_store.get("gemini_api", None) or settings.gemini_api_key
    gemini = GeminiClient(
        gemini_key,
        daily_count=ledger.daily_count,
        max_retries=catalog.circuit_breaker.gemini_max_retries,
    )
    providers = build_registry(
        catalog, settings, gemini=gemini, exe_overrides={"claude_cli": settings.claude_exe}, key_store=key_store
    )
    router = ModelRouter(catalog, providers=providers, breaker=breaker, ledger=ledger)
    embedder: Embedder | None = None
    store: JurisprudenciaStore | None = None
    emb_spec = catalog.models.get("gemini_embedding")
    if gemini_key and emb_spec and emb_spec.model_id:
        try:
            embedder = GeminiEmbedder(gemini_key, model=emb_spec.model_id, dim=emb_spec.output_dimensionality or 768)
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
        eurlex=EURLexRepository(con),
    )
    local_token = _load_or_create_token(settings)
    return Services(
        settings=settings,
        catalog=catalog,
        breaker=breaker,
        ledger=ledger,
        gemini=gemini,
        router=router,
        providers=providers,
        cli_version=_cli_version,
        key_store=key_store,
        pipeline=pipeline,
        token=local_token,
    )


# ---------- modelos de petición ----------
class NuevaConsulta(BaseModel):
    texto: str = Field(min_length=10, max_length=20000)
    modo: str = "equilibrado"
    municipio_ine: str | None = Field(default=None, pattern=r"^\d{5}$")
    adjuntos: list[str] = Field(default_factory=list, max_length=5)


class AjustesRed(BaseModel):
    activo: bool | None = None
    modos_permitidos: list[str] | None = Field(default=None, max_length=8)
    tope_diario: int | None = Field(default=None, ge=1, le=200)


class Respuesta(BaseModel):
    pregunta: str
    respuesta: str = Field(max_length=2000)
    municipio_ine: str | None = Field(default=None, pattern=r"^\d{5}$")


class Aclaraciones(BaseModel):
    respuestas: list[Respuesta] = Field(min_length=1, max_length=8)


class ConfigurarProveedor(BaseModel):
    habilitado: bool | None = None
    api_key: str | None = Field(default=None, max_length=500)


class NuevoModelo(BaseModel):
    alias: str = Field(min_length=2, max_length=60, pattern=r"^[a-z0-9_]+$")
    proveedor: str = Field(min_length=2, max_length=60)
    model_id: str = Field(min_length=1, max_length=120)
    etiqueta: str = Field(min_length=2, max_length=120)
    efforts: list[str] = Field(default_factory=lambda: ["low", "medium", "high"])


def _estado_proveedor(s: Services, pid: str) -> dict[str, Any]:
    spec = s.catalog.providers[pid]
    adapter = s.providers.get(pid)
    instalado = adapter.installed() if adapter is not None else False
    version = None
    if instalado and isinstance(adapter, CliAdapter):
        version = s.cli_version(adapter.resolve_exe())
    return {
        "etiqueta": spec.etiqueta,
        "compania": spec.compania,
        "modalidad": spec.modalidad or ("plan" if spec.tipo == "cli" else "api"),
        "tipo": spec.tipo,
        "habilitado": spec.habilitado,
        "instalado": instalado,
        "version": version,
        "api_key_env": spec.api_key_env,
        "ultima_llamada": s.ledger.last_call(pid),
        "breaker": s.breaker.snapshot(pid),
        "uso_ultimas_5h": s.ledger.window_usage(pid),
        "login": spec.login,
        "modelos": [a for a, m in s.catalog.models.items() if m.provider == pid and a != "gemini_embedding"],
    }


def _reload_catalog_and_providers(s: Services, nuevo: Catalog) -> None:
    for adapter in s.providers.values():
        adapter.stop()
    s.catalog = nuevo
    s.providers = build_registry(
        nuevo,
        s.settings,
        gemini=s.gemini,
        exe_overrides={"claude_cli": s.settings.claude_exe},
        key_store=s.key_store,
    )
    s.router.catalog = nuevo
    s.router.providers = s.providers


def create_app(services_factory: Callable[[], Services] = build_services) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        services = services_factory()
        configure_logging(services.settings.data_dir)
        log.info("Desemppa arrancada; datos en %s; build %s", services.settings.data_dir, build_id())
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

    app = FastAPI(title="Desemppa", version="0.4.0", lifespan=lifespan)
    # Quién entra y con qué rol (dueño desde este equipo, invitado desde la LAN si se ha activado) y protección
    # frente a DNS rebinding (dossier §2.5). Ver api/red_local.py.
    red = EstadoRed(escucha_red=os.environ.get("IURIS_ESCUCHA_RED") == "1")
    app.state.red = red
    app.add_middleware(RedLocalMiddleware, estado=red)

    def svc(request: Request) -> Services:
        return request.app.state.services  # type: ignore[no-any-return]

    def pipe(request: Request) -> PipelineServices:
        s = svc(request)
        if s.pipeline is None:
            raise HTTPException(503, "pipeline no inicializado")
        return s.pipeline

    def rol(request: Request) -> Rol:
        valor: Rol = getattr(request.state, "rol", "dueno")
        return valor

    def token_de(request: Request) -> str:
        return svc(request).token if rol(request) == "dueno" else red.token_invitado

    def origen_de(request: Request, invitado: str | None = None) -> str:
        """'local' para el dueño; 'lan:<id>' para un invitado (id aleatorio que guarda su navegador)."""
        if rol(request) == "dueno":
            return "local"
        ident = invitado or request.headers.get("x-desemppa-invitado", "")
        if not INVITADO_RE.match(ident):
            raise HTTPException(400, "falta el identificador de invitado; recarga la página")
        return f"lan:{ident}"

    def solo_dueno(request: Request) -> None:
        if rol(request) != "dueno":
            raise HTTPException(403, "solo disponible en el ordenador donde se ejecuta Desemppa")

    def comprobar_acceso(request: Request, consulta_id: str, invitado: str | None = None) -> None:
        """Un invitado solo accede a sus propias consultas (404 para no revelar que existen otras)."""
        if rol(request) == "dueno":
            return
        try:
            propia = pipe(request).store.origen(consulta_id) == origen_de(request, invitado)
        except KeyError:
            propia = False
        if not propia:
            raise HTTPException(404, "consulta no encontrada")

    def require_token(request: Request, x_iuris_token: str | None = Header(default=None)) -> None:
        if not secrets.compare_digest(x_iuris_token or "", token_de(request)):
            motivo = "ausente" if not x_iuris_token else "distinto del actual"
            log.warning(
                "403 token %s en %s %s (navegador: %s)",
                motivo,
                request.method,
                request.url.path,
                request.headers.get("user-agent", "?")[:80],
            )
            # Clear-Site-Data: "cache" purga automáticamente en Chrome/Brave/Edge cualquier bundle antiguo
            # cacheado por un Service Worker previo (como index-fDqGlMOV.js).
            raise HTTPException(
                403,
                f"token local inválido ({motivo}); recarga la página",
                headers={"Clear-Site-Data": '"cache"'},
            )

    def _launch(s: Services, consulta_id: str) -> None:
        assert s.pipeline is not None
        running = s.tasks.get(consulta_id)
        if running and not running.done():
            raise HTTPException(409, "la consulta ya se está procesando")
        s.tasks[consulta_id] = asyncio.create_task(Orchestrator(s.pipeline).run(consulta_id))

    @app.get("/api/version")
    def version() -> dict[str, str | None]:
        """Identificador del build de la interfaz servido; el frontend lo compara con el suyo para detectar
        una copia antigua cacheada por el service worker."""
        return {"build": build_id()}

    @app.get("/api/token")
    def token(request: Request) -> dict[str, str]:
        # Sin cabeceras CORS: solo una página del mismo origen (la propia app) puede leer la respuesta.
        # Un invitado recibe su propio token: el del dueño nunca sale de este ordenador.
        return {"token": token_de(request)}

    @app.get("/api/sesion")
    def sesion(request: Request) -> dict[str, Any]:
        s = svc(request)
        if rol(request) == "dueno":
            return {"rol": "dueno", "modos_permitidos": list(s.catalog.profiles)}
        return {"rol": "invitado", "modos_permitidos": [m for m in s.catalog.profiles if m in red.modos_permitidos]}

    @app.get("/api/red", dependencies=[Depends(solo_dueno)])
    def estado_red(request: Request) -> dict[str, Any]:
        s = svc(request)
        servidor = request.scope.get("server")
        if servidor and servidor[1]:
            red.puerto = int(servidor[1])  # el enlace usa el puerto real en el que escucha uvicorn
        consultas_hoy = s.pipeline.store.contar_hoy_invitados() if s.pipeline else 0
        return {**red.resumen(), "consultas_hoy": consultas_hoy, "modos_disponibles": list(s.catalog.profiles)}

    @app.put("/api/red", dependencies=[Depends(solo_dueno), Depends(require_token)])
    def ajustar_red(body: AjustesRed, request: Request) -> dict[str, Any]:
        s = svc(request)
        if body.modos_permitidos is not None:
            desconocidos = [m for m in body.modos_permitidos if m not in s.catalog.profiles]
            if desconocidos:
                raise HTTPException(422, f"modos desconocidos: {', '.join(desconocidos)}")
            red.modos_permitidos = {"eco", *body.modos_permitidos}  # Eco siempre disponible
        if body.tope_diario is not None:
            red.tope_diario = body.tope_diario
        if body.activo is not None:
            red.activo = body.activo
            log.info("Red local %s (url %s)", "ACTIVADA" if red.activo else "desactivada", red.url())
        return estado_red(request)

    @app.get("/api/estado", dependencies=[Depends(solo_dueno)])
    def estado(request: Request) -> dict[str, Any]:
        s = svc(request)
        corpus = None
        if s.pipeline is not None:
            corpus = {
                "sentencias": s.pipeline.cendoj.count(),
                "convenios": len(s.pipeline.convenios.listar()),
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
                alias: {
                    "proveedor": m.provider,
                    "id": m.model_id,
                    "etiqueta": m.etiqueta,
                    "compania": s.catalog.providers[m.provider].compania,
                    "modalidad": s.catalog.providers[m.provider].modalidad
                    or ("plan" if s.catalog.providers[m.provider].tipo == "cli" else "api"),
                }
                for alias, m in s.catalog.models.items()
            },
            "corpus": corpus,
        }

    # ---------- proveedores y asignación de modelos ----------
    @app.get("/api/proveedores", dependencies=[Depends(solo_dueno)])
    def proveedores(request: Request) -> dict[str, Any]:
        s = svc(request)
        return {pid: _estado_proveedor(s, pid) for pid in s.catalog.providers}

    @app.post("/api/proveedores/{pid}/configurar", dependencies=[Depends(solo_dueno), Depends(require_token)])
    def configurar_proveedor(pid: str, body: ConfigurarProveedor, request: Request) -> dict[str, Any]:
        s = svc(request)
        if pid not in s.catalog.providers:
            raise HTTPException(404, "proveedor desconocido")
        if body.api_key is not None and s.key_store is not None:
            s.key_store.set(pid, body.api_key)
            if pid == "gemini_api":
                s.gemini.set_api_key(body.api_key.strip() or s.settings.gemini_api_key)
        if body.habilitado is not None:
            nuevo = save_user_provider_or_model(provider_overrides={pid: {"habilitado": body.habilitado}})
            _reload_catalog_and_providers(s, nuevo)
        else:
            _reload_catalog_and_providers(s, s.catalog)
        return _estado_proveedor(s, pid)

    @app.post("/api/modelos", status_code=201, dependencies=[Depends(solo_dueno), Depends(require_token)])
    def anadir_modelo(body: NuevoModelo, request: Request) -> dict[str, Any]:
        s = svc(request)
        if body.proveedor not in s.catalog.providers:
            raise HTTPException(422, f"proveedor desconocido: {body.proveedor}")
        efforts = [e for e in body.efforts if e in ("low", "medium", "high")] or ["medium"]
        try:
            nuevo = save_user_provider_or_model(
                model_overrides={
                    body.alias: {
                        "provider": body.proveedor,
                        "model_id": body.model_id,
                        "etiqueta": body.etiqueta,
                        "efforts": efforts,
                        "timeout_s": 240,
                        "fallbacks": ["agy_gemini_flash"],
                    }
                }
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        _reload_catalog_and_providers(s, nuevo)
        return {"ok": True, "alias": body.alias, "estado": "creado"}

    @app.post("/api/proveedores/{pid}/detectar", dependencies=[Depends(solo_dueno), Depends(require_token)])
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

    @app.post("/api/modelos/{alias}/probar", dependencies=[Depends(solo_dueno), Depends(require_token)])
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

    @app.get("/api/ajustes/perfiles", dependencies=[Depends(solo_dueno)])
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
                    "compania": s.catalog.providers[m.provider].compania,
                    "modalidad": s.catalog.providers[m.provider].modalidad
                    or ("plan" if s.catalog.providers[m.provider].tipo == "cli" else "api"),
                    "model_id": m.model_id,
                    "efforts": m.efforts,
                    "disponible": m.provider in s.providers and s.providers[m.provider].installed(),
                }
                for alias, m in s.catalog.models.items()
                if alias != "gemini_embedding"
            },
        }

    @app.put("/api/ajustes/perfiles", dependencies=[Depends(solo_dueno), Depends(require_token)])
    def guardar_perfiles(body: dict[str, dict[str, dict[str, str]]], request: Request) -> dict[str, str]:
        s = svc(request)
        try:
            nuevo = save_user_profiles(body)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        _reload_catalog_and_providers(s, nuevo)
        return {"estado": "guardado"}

    @app.delete("/api/ajustes/perfiles", dependencies=[Depends(solo_dueno), Depends(require_token)])
    def restablecer_perfiles(request: Request) -> dict[str, str]:
        s = svc(request)
        reset_user_profiles()
        nuevo = load_catalog()
        _reload_catalog_and_providers(s, nuevo)
        return {"estado": "restablecido"}

    @app.delete("/api/ajustes/modelos", dependencies=[Depends(solo_dueno), Depends(require_token)])
    def restablecer_modelos(request: Request) -> dict[str, str]:
        """Borra los modelos personalizados y las activaciones de proveedores (user_models.toml)."""
        s = svc(request)
        reset_user_models()
        _reload_catalog_and_providers(s, load_catalog())
        return {"estado": "restablecido"}

    # ---------- consultas ----------
    @app.post("/api/consultas", status_code=201, dependencies=[Depends(require_token)])
    async def crear(body: NuevaConsulta, request: Request) -> dict[str, str]:
        s = svc(request)
        p = pipe(request)
        if body.modo not in s.catalog.profiles:
            raise HTTPException(422, f"modo desconocido: {body.modo}")
        origen = origen_de(request)
        if origen != "local":
            if body.modo not in red.modos_permitidos:
                raise HTTPException(403, f"El modo «{body.modo}» no está permitido para invitados. Usa Eco.")
            if any(not t.done() and p.store.origen(cid) == origen for cid, t in s.tasks.items()):
                raise HTTPException(429, "Ya tienes una consulta en curso: espera a que termine.")
            if p.store.contar_hoy(origen) >= red.tope_diario:
                raise HTTPException(429, f"Has alcanzado el límite de {red.tope_diario} consultas por hoy.")
        consulta_id = p.store.create(
            body.texto, body.modo, municipio_ine=body.municipio_ine, adjuntos=body.adjuntos, origen=origen
        )
        _launch(s, consulta_id)
        return {"consulta_id": consulta_id}

    @app.post("/api/consultas/{consulta_id}/aclaraciones", dependencies=[Depends(require_token)])
    async def aclarar(consulta_id: str, body: Aclaraciones, request: Request) -> dict[str, str]:
        s, p = svc(request), pipe(request)
        comprobar_acceso(request, consulta_id)
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
        if rol(request) == "dueno":
            return pipe(request).store.listar()
        return pipe(request).store.listar(origen=origen_de(request))

    @app.get("/api/consultas/{consulta_id}")
    def detalle(consulta_id: str, request: Request) -> dict[str, Any]:
        p = pipe(request)
        comprobar_acceso(request, consulta_id)
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
        invitado: str | None = Query(default=None, max_length=64),
        last_event_id: str | None = Header(default=None),
    ) -> EventSourceResponse:
        s, p = svc(request), pipe(request)
        if not secrets.compare_digest(token, token_de(request)):
            raise HTTPException(403, "token local inválido", headers={"Clear-Site-Data": '"cache"'})
        comprobar_acceso(request, consulta_id, invitado)
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
                        # «fin»: el historial está completo; el navegador cierra aquí (y no al ver una aclaración
                        # antigua, que dejaba sin mostrar el dictamen de una consulta reabierta).
                        yield {"event": "fin", "data": "{}"}
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
                        yield {"event": "fin", "data": "{}"}
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
            comprobar_acceso(request, consulta_id)
            c = p.store.get(consulta_id)
            for grupo in ("articulos_boe", "articulos_ue", "sentencias", "clausulas_convenio", "extractos_adjuntos"):
                for f in (c.dossier or {}).get(grupo, []):
                    if f["source_id"] == source_id:
                        texto, titulo, url = f["texto_verbatim"], f["titulo"], f.get("url_oficial")
        if texto is None and source_id.startswith("ROJ:"):
            det = p.cendoj.detalle(source_id[4:])
            if det:
                texto, url = det["fundamentos"], det["url"]
        if texto is None and source_id.startswith("CONV:"):
            det_conv = p.convenios.detalle_clausula(source_id)
            if det_conv:
                titulo, texto, url = det_conv["titulo"], det_conv["texto"], det_conv["url"]
        if texto is None and source_id.startswith("EUR:") and p.eurlex is not None:
            _, celex, art = source_id.split(":", 2)
            try:
                ue = await p.eurlex.get_articulo(celex, art.removeprefix("art"))
                titulo, texto, url = f"Art. {ue.articulo} ({ue.titulo})", ue.texto, ue.url
            except EURLexError:
                texto = None
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

    @app.post(
        "/api/jurisprudencia/importar", status_code=201, dependencies=[Depends(solo_dueno), Depends(require_token)]
    )
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
        def index() -> HTMLResponse:
            # El HTML no lleva el token (el frontend lo pide a /api/token) y nunca se cachea: así una copia
            # antigua no puede dejar a la app con un token caducado.
            return HTMLResponse((WEB_DIST / "index.html").read_text(encoding="utf-8"), headers=NO_CACHE)

        @app.get("/{path:path}", response_model=None)
        def static_files(path: str) -> FileResponse | HTMLResponse:
            target = (WEB_DIST / path).resolve()
            if path.startswith("api/"):
                raise HTTPException(404)
            if path == "index.html":
                return index()
            if target.is_file() and WEB_DIST.resolve() in target.parents:
                headers = NO_CACHE if target.name in ("sw.js", "version.json", "manifest.webmanifest") else None
                return FileResponse(target, headers=headers)
            return index()

    return app


app = create_app()
