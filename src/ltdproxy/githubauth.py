"""The GitHub OAuth dependency for path operations."""

from __future__ import annotations

from typing import TypeVar

import authlib.integrations.starlette_client.integration
from authlib.integrations.starlette_client import OAuth

from ltdproxy.config import config

GitHubOAuthType = TypeVar(
    "GitHubOAuthType",
    bound=authlib.integrations.starlette_client.integration.StarletteRemoteApp,
)
"""Type alias from the authlib GitHub OAuth client."""


class GitHubOAuth:
    """This class maintains an OAuth instance that is registered for GitHub
    OAuth with the applications configurations.

    The instance of this class, ``github_oauth_dependency`` is a FastAPI
    path operation dependency that provides the configured OAuth instance
    to endpoint handlers.
    """

    def __init__(self) -> None:
        self.oauth = OAuth()
        self.oauth.register(
            name="github",
            client_id=config.github_oauth_client_id,
            client_secret=config.github_oauth_client_secret.get_secret_value(),
            access_token_url="https://github.com/login/oauth/access_token",
            access_token_params=None,
            authorize_url="https://github.com/login/oauth/authorize",
            authorize_params=None,
            api_base_url="https://api.github.com/",
            client_kwargs={"scope": "user:email,read:org"},
        )

    async def __call__(self) -> GitHubOAuthType:
        # This method is async so that FastAPI does not create an extra thread
        # when calling this.
        return self.oauth.github


github_oauth_dependency = GitHubOAuth()
"""Path dependency that returns a configured
`authlib.integrations.starlette_client.OAuth` instance for GitHub OAuth.
"""
