"""Configuration for the app."""

from __future__ import annotations

from importlib.metadata import metadata
from typing import TYPE_CHECKING

from .handlers.external import external_router
from .handlers.internal import internal_router

if TYPE_CHECKING:
    from fastapi import FastAPI

    from ltdproxy.config import Configuration


def add_handlers(*, config: Configuration, app: FastAPI) -> None:
    if config.path_prefix == "/":
        app.include_router(external_router)
    else:
        external_app = FastAPI(
            title="ltd-proxy",
            description=metadata("ltd-proxy").get("Summary", ""),
            version=metadata("ltd-proxy").get("Version", "0.0.0"),
            openapi_url=None,
        )
        external_app.include_router(external_router)

        app.include_router(internal_router)
        app.mount(f"{config.path_prefix}", external_app)
