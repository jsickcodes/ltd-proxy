"""Handlers for the app's external root, ``/ltdproxy/``."""

from typing import Optional, Union
from urllib.parse import urlencode, urlparse

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


@external_router.get("/auth", name="get_oauth_callback")
async def get_oauth_callback(
    ref: Optional[str],
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

    # Compute redirect URL
    if ref:
        # The original callback URL included the "ref" query parameter with
        # the referring page's URL. We'll redirect to that.
        redirect_url = ref
    else:
        # Default redirect.
        redirect_url = request.url_for("/")

    return RedirectResponse(url=redirect_url)


@external_router.get("/login", name="login")
async def get_login(
    ref: Optional[str],
    request: Request,
    logger: BoundLogger = Depends(logger_dependency),
    github_oauth: GitHubOAuthType = Depends(github_oauth_dependency),
) -> RedirectResponse:
    """Log a user in by redirecting to GitHub OAuth."""
    redirect_uri = str(config.github_oauth_callback_url)
    if ref:
        # The ref query string can be set to point to the page that
        # asked for the login.
        # Make sure return return url is in same domain as this request
        # (i.e., only redirect when on same site)
        if urlparse(ref).netloc == request.url.netloc:
            redirect_uri = (
                urlparse(redirect_uri)
                ._replace(query=urlencode({"ref": ref}, doseq=True))
                .geturl()
            )

    logger.info("Redirecting to GitHub auth", callback_url=redirect_uri)
    return await github_oauth.authorize_redirect(request, redirect_uri)


@external_router.get("/logout", name="logout")
async def get_logout(
    request: Request,
    logger: BoundLogger = Depends(logger_dependency),
) -> RedirectResponse:
    request.session.pop("github_token", None)
    request.session.pop("github_memberships", None)
    logger.info("Logged out")
    return RedirectResponse(url=request.url_for("logged-out"))


@external_router.get("/logged-out", name="logged-out")
async def get_logged_out(
    request: Request,
) -> Union[HTMLResponse, RedirectResponse]:
    if "github_memberships" in request.session:
        # Not actually logged out yet so redirect to /logout first
        return RedirectResponse(url=request.url_for("logout"))
    return HTMLResponse("<h1>You're logged out.</h1>")


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
        # User is not authenticated so redirect to the login page with
        # this page's URL as the ref query string so they'll get redirect
        # back here after login.
        login_url = request.url_for("login")
        ref_qs = urlencode({"ref": request.url}, doseq=True)
        login_url = urlparse(login_url)._replace(query=ref_qs).geturl()
        return RedirectResponse(url=login_url)

    elif github_auth_result == AuthResult.unauthorized:
        # User is not authorized.
        raise HTTPException(status_code=403, detail="Not authorized")

    elif github_auth_result == AuthResult.authorized:
        # User is authorized; stream from S3.
        if path == "" or path.endswith("/"):
            # redwrite "*/" as "*/index.html" for static sites in S3
            bucket_path = f"{config.s3_bucket_prefix}{path}index.html"
        else:
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
        # Catch-all error
        raise HTTPException(status_code=500, detail="Internal auth error")
