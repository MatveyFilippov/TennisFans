import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial
from importlib.metadata import version
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import delete, text
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from tennisfans.api import accounts, competition, media
from tennisfans.api.context import Environment, Runtime
from tennisfans.api.contracts import ErrorBody
from tennisfans.core.config import Settings
from tennisfans.core.errors import Problem
from tennisfans.db.accounts import LoginSession, RateBucket
from tennisfans.db.base import now
from tennisfans.db.runtime import engine_for, migrate, session_factory
from tennisfans.modules.auth import rate_limit
from tennisfans.modules.storage import LocalStorage, cleanup_pending, sweep_orphans
from tennisfans.modules.tournaments import reconcile_due

logger = logging.getLogger("tennisfans")
MUTATIONS = {"POST", "PUT", "PATCH", "DELETE"}
PUBLIC_PREFIX = "/api/v1/public/"


class Structured(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        value = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            value["exception"] = self.formatException(record.exc_info)
        return json.dumps(value)


def configure_logs(settings: Settings) -> None:
    level = settings.log_level or ("INFO" if settings.environment == "production" else "DEBUG")
    handler = logging.StreamHandler()
    formatter = (
        Structured()
        if settings.environment == "production"
        else logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    handler.setFormatter(formatter)
    logger.handlers[:] = [handler]
    logger.setLevel(level)
    logger.propagate = False
    for name in ("uvicorn", "uvicorn.error"):
        logging.getLogger(name).setLevel(level)


def error(request_id: str, problem: Problem) -> JSONResponse:
    body = ErrorBody(
        code=problem.code,
        detail=problem.detail,
        request_id=request_id,
        context=jsonable_encoder(problem.context),
    )
    headers = {"Cache-Control": "no-store"}
    if problem.status == 429 and "retry_after" in problem.context:
        headers["Retry-After"] = str(problem.context["retry_after"])
    return JSONResponse(status_code=problem.status, content=body.model_dump(), headers=headers)


class RequestPolicy:
    def __init__(self, app: ASGIApp, runtime: Runtime) -> None:
        self.app = app
        self.runtime = runtime

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope)
        request_id = uuid4().hex
        scope.setdefault("state", {})["request_id"] = request_id
        path = request.url.path
        settings = self.runtime.settings
        mutates = request.method in MUTATIONS
        public = request.method == "GET" and path.startswith(PUBLIC_PREFIX)
        maximum = settings.upload_request_bytes if path.startswith("/api/v1/media/") else 1024**2
        received = 0
        overflow = False
        sent = False
        status = 500
        started = time.monotonic()

        async def guarded_receive() -> Message:
            nonlocal received, overflow
            message = await receive()
            received += len(message.get("body", b""))
            if received > maximum:
                overflow = True
                return {"type": "http.disconnect"}
            return message

        async def send_policy(message: Message) -> None:
            nonlocal status, sent
            if overflow:
                return
            if message["type"] == "http.response.start":
                sent = True
                status = message["status"]
                headers = list(message.get("headers", []))
                headers.extend(
                    [
                        (b"x-request-id", request_id.encode()),
                        (b"x-content-type-options", b"nosniff"),
                        (b"referrer-policy", b"same-origin"),
                        (b"x-frame-options", b"DENY"),
                    ]
                )
                if public and status == 200:
                    if not any(name == b"cache-control" for name, _ in headers):
                        headers.append((b"cache-control", b"public, max-age=0, must-revalidate"))
                    headers.append((b"x-tennisfans-public", b"1"))
                if not public and not any(name == b"cache-control" for name, _ in headers):
                    headers.append((b"cache-control", b"no-store"))
                message["headers"] = headers
            await send(message)

        try:
            if mutates:
                origin = request.headers.get("Origin")
                if origin not in {*settings.allowed_origins, settings.public_url}:
                    raise Problem(403, "invalid_origin", "The request origin is not allowed")
                size = request.headers.get("Content-Length", "")
                if size and (not size.isdecimal() or len(size) > 12 or int(size) > maximum):
                    raise Problem(
                        413, "request_too_large", "The request exceeds the body size limit"
                    )
                limits = {
                    "/api/v1/auth/login": ("login", 12, 60),
                    "/api/v1/auth/register": ("register", 8, 3600),
                    "/api/v1/matches/friendly": ("friendly", 30, 60),
                }
                bucket = limits.get(path)
                if path.startswith("/api/v1/media/"):
                    bucket = ("media", 20, 60)
                elif path.endswith(("/result", "/disputes")):
                    bucket = ("result", 60, 60)
                if bucket:
                    address = request.client.host if request.client else "unknown"
                    category, limit, window = bucket
                    await run_in_threadpool(
                        rate_limit, self.runtime.db, category, address, limit, window
                    )
            await self.app(scope, guarded_receive, send_policy)
        except Problem as problem:
            await error(request_id, problem)(scope, receive, send_policy)
        except Exception:
            if sent:
                raise
            logger.exception("Unhandled request failure id=%s", request_id)
            await error(request_id, Problem(500, "internal_error", "An unexpected error occurred"))(
                scope, receive, send_policy
            )
        finally:
            if overflow and not sent:
                overflow = False
                await error(
                    request_id,
                    Problem(413, "request_too_large", "The request exceeds the body size limit"),
                )(scope, receive, send_policy)
            route = scope.get("route")
            logger.info(
                "%s %s status=%s duration_ms=%d environment=%s request_id=%s",
                request.method,
                getattr(route, "path", "<unmatched>"),
                status,
                (time.monotonic() - started) * 1000,
                settings.environment,
                request_id,
            )


def _maintenance(runtime: Runtime, housekeeping: bool) -> None:
    reconcile_due(runtime.db)
    cleanup_pending(runtime.db, runtime.storage)
    if housekeeping:
        sweep_orphans(runtime.db, runtime.storage)
        with runtime.db.begin() as db:
            db.execute(delete(LoginSession).where(LoginSession.expires_at <= now()))
            db.execute(delete(RateBucket).where(RateBucket.expires_at <= now()))


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_logs(settings)
    engine = engine_for(settings)
    runtime = Runtime(
        settings, session_factory(engine), LocalStorage(settings.media_root.resolve())
    )
    state = {"ready": False}

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        await run_in_threadpool(partial(migrate, engine, replay_k=runtime.settings.elo_k))
        await run_in_threadpool(runtime.storage.check)
        await run_in_threadpool(_maintenance, runtime, True)
        state["ready"] = True
        stop = asyncio.Event()

        async def work() -> None:
            next_cleanup = time.monotonic() + 3600
            while not stop.is_set():
                try:
                    await asyncio.wait_for(stop.wait(), timeout=runtime.settings.reconcile_seconds)
                except TimeoutError:
                    try:
                        housekeeping = time.monotonic() >= next_cleanup
                        await run_in_threadpool(_maintenance, runtime, housekeeping)
                        if housekeeping:
                            next_cleanup = time.monotonic() + 3600
                    except Exception:
                        logger.exception("Background maintenance failed")

        task = asyncio.create_task(work())
        try:
            yield
        finally:
            state["ready"] = False
            stop.set()
            await task
            await run_in_threadpool(engine.dispose)

    app = FastAPI(
        title="TennisFans API",
        version=version("tennisfans"),
        lifespan=lifespan,
        description="Public competition and rating views with session-protected mutations.",
        responses={
            code: {"model": ErrorBody} for code in (400, 401, 403, 404, 409, 413, 422, 429, 503)
        },
    )
    app.state.runtime = runtime
    app.add_middleware(RequestPolicy, runtime=runtime)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Content-Type", "X-CSRF-Token", "Idempotency-Key"],
        expose_headers=["X-Request-Id", "X-TennisFans-Public", "Retry-After"],
    )

    @app.exception_handler(Problem)
    async def domain_problem(request: Request, exc: Problem) -> JSONResponse:
        return error(request.state.request_id, exc)

    @app.exception_handler(RequestValidationError)
    async def validation_problem(request: Request, exc: RequestValidationError) -> JSONResponse:
        fields = [".".join(map(str, item["loc"])) for item in exc.errors()]
        return error(
            request.state.request_id,
            Problem(422, "validation", "Some fields are invalid", fields=fields),
        )

    @app.exception_handler(HTTPException)
    async def http_problem(request: Request, exc: HTTPException) -> JSONResponse:
        return error(
            request.state.request_id,
            Problem(exc.status_code, "http_error", "The request could not be processed"),
        )

    @app.exception_handler(IntegrityError)
    async def integrity(request: Request, _: IntegrityError) -> JSONResponse:
        return error(
            request.state.request_id,
            Problem(409, "database_conflict", "This request conflicts with existing data"),
        )

    @app.exception_handler(OperationalError)
    async def operational(request: Request, _: OperationalError) -> JSONResponse:
        logger.warning("Database unavailable for request %s", request.state.request_id)
        return error(
            request.state.request_id,
            Problem(503, "database_unavailable", "The database is unavailable"),
        )

    @app.get("/health/live", tags=["system"])
    def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready", tags=["system"])
    def ready(env: Environment) -> dict[str, str]:
        try:
            if not state["ready"]:
                raise OSError("Starting")
            with env.db() as db:
                db.execute(text("SELECT 1"))
            env.storage.check()
        except (SQLAlchemyError, OSError) as exc:
            raise Problem(503, "not_ready", "The application is not ready") from exc
        return {"status": "ready"}

    @app.get("/api/v1/version", tags=["system"])
    def build_info() -> dict[str, Any]:
        return {"version": version("tennisfans"), "commit": runtime.settings.build_sha}

    for router in (accounts.router, competition.router, media.router):
        app.include_router(router, prefix="/api/v1")
    return app
