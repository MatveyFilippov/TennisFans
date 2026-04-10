def start():
    from .base import APP, log
    log.debug("Starting app")

    from .players import router as players_router
    APP.include_router(players_router)
    log.debug(f"Register {players_router.prefix}")
    from .matches import router as matches_router
    APP.include_router(matches_router)
    log.debug(f"Register {matches_router.prefix}")

    import settings
    import uvicorn
    log.info(f"Start application on http://{settings.APP_HOST}:{settings.APP_PORT}{settings.APP_ROOT_PATH}")
    uvicorn.run(APP, host=settings.APP_HOST, port=settings.APP_PORT, log_level="error", access_log=False)
