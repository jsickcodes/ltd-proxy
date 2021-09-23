"""Handlers for the app's external root, ``/ltdproxy/``."""

import httpx
from fastapi import APIRouter, Depends
from safir.dependencies.http_client import http_client_dependency
from safir.dependencies.logger import logger_dependency
from starlette.background import BackgroundTask
from starlette.responses import StreamingResponse
from structlog.stdlib import BoundLogger

from ltdproxy.config import config
from ltdproxy.s3 import Bucket, bucket_dependency

__all__ = ["get_s3", "external_router"]

external_router = APIRouter()
"""FastAPI router for all external handlers."""


@external_router.get(
    "/{path:path}",
    description="The S3 front-end proxy.",
)
async def get_s3(
    path: str,
    logger: BoundLogger = Depends(logger_dependency),
    bucket: Bucket = Depends(bucket_dependency),
    http_client: httpx.AsyncClient = Depends(http_client_dependency),
) -> StreamingResponse:
    """The S3 proxy endpoint."""
    bucket_path = f"{config.s3_bucket_prefix}{path}"
    stream = await bucket.stream_object(http_client, bucket_path)
    logger.info("stream headers", headers=stream.headers)
    response_headers = {
        "Content-type": stream.headers["Content-type"],
        "Content-length": stream.headers["Content-length"],
        "Etag": stream.headers["Etag"],
    }
    return StreamingResponse(
        stream.aiter_raw(),
        background=BackgroundTask(stream.aclose),
        headers=response_headers,
    )
