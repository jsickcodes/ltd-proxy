"""Handlers for the app's external root, ``/ltdproxy/``."""

from typing import Union

import httpx
from authlib.integrations.starlette_client import OAuthError
from fastapi import APIRouter, Depends, HTTPException
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
from ltdproxy.githubauth import (
    AuthResult,
    GitHubAuth,
    GitHubOAuthType,
    github_auth_dependency,
    github_oauth_dependency,
    set_serialized_github_memberships,
)
from ltdproxy.s3 import Bucket, bucket_dependency

__all__ = ["get_s3", "external_router"]

external_router = APIRouter()
"""FastAPI router for all external handlers."""


@external_router.get("/", name="homepage")
async def homepage(request: Request) -> HTMLResponse:
    github_token = request.session.get("github_token")
    if github_token:
        html = (
            "<h1>hello!</p>"
            f'<a href="{request.url_for("logout")}">logout</a>'
        )
        return HTMLResponse(html)
    return HTMLResponse(f'<a href="{request.url_for("login")}">login</a>')


@external_router.get("/auth", name="get_oauth_callback")
async def get_oauth_callback(
    request: Request,
    logger: BoundLogger = Depends(logger_dependency),
    github_oauth: GitHubOAuthType = Depends(github_oauth_dependency),
    http_client: httpx.AsyncClient = Depends(http_client_dependency),
) -> Union[RedirectResponse, HTMLResponse]:
    try:
        token = await github_oauth.authorize_access_token(request)
    except OAuthError as error:
        return HTMLResponse(f"<h1>{error.error}</h1>")
    github_token = token.get("access_token")
    logger.info(
        "Got github oauth token", token=token, access_token=github_token
    )
    if github_token:
        request.session["github_token"] = github_token
    await set_serialized_github_memberships(
        http_client=http_client,
        session=request.session,
        github_token=github_token,
    )
    return RedirectResponse(url=request.url_for("homepage"))


@external_router.get("/login", name="login")
async def login(
    request: Request,
    logger: BoundLogger = Depends(logger_dependency),
    github_oauth: GitHubOAuthType = Depends(github_oauth_dependency),
) -> RedirectResponse:
    redirect_uri = str(config.github_oauth_callback_url)
    logger.info("Redirecting to GitHub auth", callback_url=redirect_uri)
    return await github_oauth.authorize_redirect(request, redirect_uri)


@external_router.get("/logout", name="logout")
async def logout(
    request: Request,
    logger: BoundLogger = Depends(logger_dependency),
) -> RedirectResponse:
    request.session.pop("github_token", None)
    request.session.pop("github_memberships", None)
    logger.info("Logged out")
    return RedirectResponse(url=request.url_for("homepage"))


@external_router.get(
    "/{path:path}", description="The S3 front-end proxy.", name="proxy"
)
async def get_s3(
    path: str,
    request: Request,
    logger: BoundLogger = Depends(logger_dependency),
    bucket: Bucket = Depends(bucket_dependency),
    http_client: httpx.AsyncClient = Depends(http_client_dependency),
    github_auth: GitHubAuth = Depends(github_auth_dependency),
) -> Union[StreamingResponse, RedirectResponse]:
    """The S3 proxy endpoint."""
    github_auth_result = github_auth.is_session_authorized(
        path=f"/{path}", session=request.session
    )
    if github_auth_result == AuthResult.unauthenticated:
        return RedirectResponse(url=request.url_for("login"))
    elif github_auth_result == AuthResult.unauthorized:
        raise HTTPException(status_code=403, detail="Not authorized")
    elif github_auth_result == AuthResult.authorized:
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
    else:
        raise HTTPException(status_code=500, detail="Internal auth error")
