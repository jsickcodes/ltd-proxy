"""Configuration for the app."""

from __future__ import annotations

from importlib.metadata import metadata, version
from typing import TYPE_CHECKING

from .handlers.external import external_router
from .handlers.healthcheck import health_router
from .handlers.internal import internal_router

if TYPE_CHECKING:
    from fastapi import FastAPI

    from ltdproxy.config import Configuration


def add_handlers(*, config: Configuration, app: FastAPI) -> None:
    if config.path_prefix == "/":
        app.include_router(health_router)
        app.include_router(external_router)
    else:
        external_app = FastAPI(
            title="ltd-proxy",
            description=metadata("ltd-proxy")["Summary"],
            version=version("ltd-proxy"),
            openapi_url=None,
        )
        external_app.include_router(external_router)

        app.include_router(internal_router)
        app.include_router(health_router)
        app.mount(f"{config.path_prefix}", external_app)
