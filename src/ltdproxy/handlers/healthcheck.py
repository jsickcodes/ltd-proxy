"""Handler for the Kubernetes health check."""

from fastapi import APIRouter
from starlette.responses import PlainTextResponse

health_router = APIRouter()


@health_router.get("/__healthz", name="healthz")
def healthy() -> PlainTextResponse:
    return PlainTextResponse("OK", status_code=200)
