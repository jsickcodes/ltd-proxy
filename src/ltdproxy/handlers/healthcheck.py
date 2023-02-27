"""Handler for the Kubernetes health check."""

import httpx
from fastapi import APIRouter, Depends
from safir.dependencies.http_client import http_client_dependency
from safir.dependencies.logger import logger_dependency
from starlette.responses import PlainTextResponse
from structlog.stdlib import BoundLogger

from ltdproxy.config import config
from ltdproxy.s3 import Bucket, bucket_dependency

health_router = APIRouter()


@health_router.get("/__healthz", name="healthz")
async def healthy(
    bucket: Bucket = Depends(bucket_dependency),
    logger: BoundLogger = Depends(logger_dependency),
    http_client: httpx.AsyncClient = Depends(http_client_dependency),
) -> PlainTextResponse:
    if config.healthcheck_bucket_key:
        # enter mode for testing S3 streaming
        stream = await bucket.stream_object(
            http_client, config.healthcheck_bucket_key
        )
        if stream.status_code != httpx.codes.OK:
            logger.error(
                "Health check got bad S3 response code",
                status_code=stream.status_code,
            )
            return PlainTextResponse("ERROR", status_code=500)
        async for _ in stream.aiter_bytes():
            pass
        await stream.aclose()

    return PlainTextResponse("OK", status_code=200)
