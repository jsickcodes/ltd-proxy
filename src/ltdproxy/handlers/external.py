"""Handlers for the app's external root, ``/ltdproxy/``."""

from typing import Union

import httpx
from authlib.integrations.starlette_client import OAuthError
from fastapi import APIRouter, Depends
from safir.dependencies.http_client import http_client_dependency
from safir.dependencies.logger import logger_dependency
from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.responses import (
    HTMLResponse,
    RedirectResponse,
    StreamingResponse,
)
from structlog.stdlib import BoundLogger

from ltdproxy.config import config
from ltdproxy.githubauth import GitHubOAuthType, github_oauth_dependency
from ltdproxy.s3 import Bucket, bucket_dependency

__all__ = ["get_s3", "external_router"]

external_router = APIRouter()
"""FastAPI router for all external handlers."""


@external_router.get("/")
async def homepage(request: Request) -> HTMLResponse:
    github_token = request.session.get("github_token")
    if github_token:
        html = "<h1>hello!</p>" '<a href="/ltdproxy/logout">logout</a>'
        return HTMLResponse(html)
    return HTMLResponse('<a href="/ltdproxy/login">login</a>')


@external_router.get("/auth")
async def get_oauth_callback(
    request: Request,
    logger: BoundLogger = Depends(logger_dependency),
    github_oauth: GitHubOAuthType = Depends(github_oauth_dependency),
) -> Union[RedirectResponse, HTMLResponse]:
    try:
        token = await github_oauth.authorize_access_token(request)
    except OAuthError as error:
        return HTMLResponse(f"<h1>{error.error}</h1>")
    print(token)
    print(type(token))
    github_token = token.get("access_token")
    logger.info(
        "Got github oauth token", token=token, access_token=github_token
    )
    if github_token:
        request.session["github_token"] = github_token
    return RedirectResponse(url="/ltdproxy/")


@external_router.get("/login")
async def login(
    request: Request,
    logger: BoundLogger = Depends(logger_dependency),
    github_oauth: GitHubOAuthType = Depends(github_oauth_dependency),
) -> RedirectResponse:
    # redirect_uri = request.url_for('get_oauth_callback')
    redirect_uri = "http://127.0.0.1:8000/ltdproxy/auth"
    logger.info("Redirecting to GitHub auth", callback_url=redirect_uri)
    return await github_oauth.authorize_redirect(request, redirect_uri)


@external_router.get("/logout")
async def logout(
    request: Request,
    logger: BoundLogger = Depends(logger_dependency),
) -> RedirectResponse:
    request.session.pop("github_token", None)
    logger.info("Logged out")
    return RedirectResponse(url="/ltdproxy/")


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
