"""The main application factory for the ltd-proxy service.

Notes
-----
Be aware that, following the normal pattern for FastAPI services, the app is
constructed when this module is loaded and is not deferred until a function is
called.
"""

import structlog
from fastapi import FastAPI
from safir.dependencies.http_client import http_client_dependency
from safir.logging import configure_logging
from safir.metadata import get_metadata
from safir.middleware.x_forwarded import XForwardedMiddleware
from starlette.middleware.sessions import SessionMiddleware

from .appsetup import add_handlers
from .config import config
from .rewrites import rewrite_dependency

__all__ = ["app", "config"]

configure_logging(
    profile=config.profile,
    log_level=config.log_level,
    name=config.logger_name,
)

app = FastAPI(openapi_url=None)
"""The main FastAPI application for ltd-proxy."""

add_handlers(app=app, config=config)

app.add_middleware(
    SessionMiddleware, secret_key=config.session_key.get_secret_value()
)
app.add_middleware(XForwardedMiddleware)


@app.on_event("startup")
async def startup_event() -> None:
    logger = structlog.get_logger(config.logger_name)
    metadata = get_metadata(
        package_name="ltd-proxy",
        application_name=config.name,
    )
    logger.info("Starting up", version=metadata.version)
    await rewrite_dependency.initialize(await http_client_dependency())


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await http_client_dependency.aclose()
