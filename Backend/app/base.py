import settings
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


log = settings.ProjectLoggerFactory.get_for("app")
APP = FastAPI(version=settings.BACKEND_VERSION, root_path=settings.APP_ROOT_PATH)


@APP.middleware("http")
async def log_middleware(request: Request, call_next):
    log.info(f"REQUEST: {request.method} {request.url.path}")
    log.debug(f"Headers raw: {request.headers.raw}")
    log.debug(f"QueryParams raw: {request.query_params}")
    log.debug(f"BodyRaw raw: {await request.body()}")
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
