import settings
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


log = settings.ProjectLoggerFactory.get_for("app")
APP = FastAPI(version=settings.BACKEND_VERSION)


@APP.middleware("http")
async def log_middleware(request: Request, call_next):
    log.info(f"REQUEST: {request.method} {request.url.path}")
    response = await call_next(request)
    log.info(f"RESPONSE: {response.status_code}")
    return response


@APP.exception_handler(Exception)
async def global_exception_handler(request: Request, ex: Exception):
    log.error("Faced with unhandled exception", exc_info=True)
    log.info("RESPONSE: 500")
    return JSONResponse(
        content={"detail": "Internal server error"},
        status_code=500,
    )
