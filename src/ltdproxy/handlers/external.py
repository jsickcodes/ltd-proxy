"""Handlers for the app's external root, ``/ltdproxy/``."""

import posixpath
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
from ltdproxy.rewrites import RewriteEngine, rewrite_dependency
from ltdproxy.s3 import Bucket, bucket_dependency
from ltdproxy.urlmap import map_s3_path

__all__ = ["get_s3", "external_router"]

external_router = APIRouter()
"""FastAPI router for all external handlers."""


@external_router.get("/auth", name="get_oauth_callback", response_model=None)
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
    logger.debug(
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


@external_router.get("/login", name="login", response_model=None)
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

    logger.debug("Redirecting to GitHub auth", callback_url=redirect_uri)
    return await github_oauth.authorize_redirect(request, redirect_uri)


@external_router.get("/logout", name="logout", response_model=None)
async def get_logout(
    request: Request,
    logger: BoundLogger = Depends(logger_dependency),
) -> RedirectResponse:
    request.session.pop("github_token", None)
    request.session.pop("github_memberships", None)
    logger.debug("Logged out")
    return RedirectResponse(url=request.url_for("logged-out"))


@external_router.get("/logged-out", name="logged-out", response_model=None)
async def get_logged_out(
    request: Request,
) -> Union[HTMLResponse, RedirectResponse]:
    if "github_memberships" in request.session:
        # Not actually logged out yet so redirect to /logout first
        return RedirectResponse(url=request.url_for("logout"))
    return HTMLResponse("<h1>You're logged out.</h1>")


@external_router.get(
    "/{path:path}",
    description="The S3 front-end proxy.",
    name="proxy",
    response_model=None,
)
async def get_s3(
    path: str,
    request: Request,
    logger: BoundLogger = Depends(logger_dependency),
    bucket: Bucket = Depends(bucket_dependency),
    http_client: httpx.AsyncClient = Depends(http_client_dependency),
    github_auth: GitHubAuth = Depends(github_auth_dependency),
    rewrite_engine: RewriteEngine = Depends(rewrite_dependency),
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
        # User is authorized; first check rewrites
        response = await rewrite_engine.build_response(f"/{path}")
        if response:
            return response

        # User is authorized; stream from S3.
        bucket_path = map_s3_path(config.s3_bucket_prefix, path)
        logger.debug(
            "computed bucket path",
            bucket_path=bucket_path,
            request_url=str(request.url),
        )
        stream = await bucket.stream_object(http_client, bucket_path)
        if stream.status_code == 404:
            if not path.endswith("/") and posixpath.splitext(path)[1] == "":
                # try a redirect; not sure this is relevant with directory
                # redirect objects
                parsed_url = urlparse(str(request.url))
                parsed_url = parsed_url._replace(path=f"{parsed_url.path}/")
                return RedirectResponse(url=parsed_url.geturl())
            else:
                raise HTTPException(status_code=404, detail="Does not exist.")
        logger.debug("stream headers", headers=stream.headers)

        # Check if it's an LTD directory redirect object with a
        # x-amz-meta-dir-redirect header:
        if stream.headers.get("x-amz-meta-dir-redirect", "false") == "true":
            parsed_url = urlparse(str(request.url))
            parsed_url = parsed_url._replace(path=f"{parsed_url.path}/")
            return RedirectResponse(url=parsed_url.geturl())

        response_headers = {
            "Content-type": stream.headers["Content-type"],
            "Content-length": stream.headers["Content-length"],
            "Etag": stream.headers["Etag"],
        }
        # FIXME hack to override content-type headers
        if bucket_path.endswith(".html"):
            logger.debug("is html")
            response_headers["Content-type"] = "text/html"
        elif bucket_path.endswith(".css"):
            logger.debug("is css")
            response_headers["Content-type"] = "text/css"
        elif bucket_path.endswith(".js"):
            logger.debug("is js")
            response_headers["Content-type"] = "application/javascript"
        elif bucket_path.endswith(".pdf"):
            logger.debug("is pdf")
            response_headers["Content-type"] = "application/pdf"
        elif bucket_path.endswith(".png"):
            logger.debug("is png")
            response_headers["Content-type"] = "image/png"
        else:
            logger.warning(
                "Did not change response content-type",
                response_headers=response_headers,
            )

        logger.debug("response headers", headers=response_headers)

        return StreamingResponse(
            stream.aiter_raw(),
            background=BackgroundTask(stream.aclose),
            headers=response_headers,
        )

    else:
        # Catch-all error
        raise HTTPException(status_code=500, detail="Internal auth error")
