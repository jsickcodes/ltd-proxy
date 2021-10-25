"""The GitHub OAuth dependency for path operations."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Dict, List, Tuple, TypeVar

import authlib.integrations.starlette_client.integration
import gidgethub.httpx
from authlib.integrations.starlette_client import OAuth

from ltdproxy.config import config

if TYPE_CHECKING:
    import httpx

__all__ = [
    "GitHubOAuthType",
    "GitHubOAuth",
    "github_oauth_dependency",
    "set_serialized_github_memberships",
]

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


async def set_serialized_github_memberships(
    *,
    http_client: httpx.AsyncClient,
    session: Dict[Any, Any],
    github_token: str,
) -> None:
    """Add JSON-serialized GitHub organization and team memberships to the
    request session.
    """
    # Stubs for configuration of GitHub teams and organizations relevant to
    # authorization settings
    relevant_orgs = ["jsickcodes"]
    relevant_teams = [("jsickcodes", "proxy-team")]

    github_client = gidgethub.httpx.GitHubAPI(
        http_client, "ltd-proxy", oauth_token=github_token
    )

    # Get all relevant organization memberships for the user
    user_orgs: List[str] = []
    async for org in github_client.getiter("/user/memberships/orgs"):
        if org["organization"]["login"] in relevant_orgs:
            user_orgs.append(org["organization"]["login"])

    # Get all relevant team memberships for the user
    user_teams: List[Tuple[str, str]] = []
    async for team in github_client.getiter("/user/teams"):
        team_id = (team["organization"]["login"], team["name"])
        if team_id in relevant_teams:
            user_teams.append(team_id)

    # Serialize memberships to JSON to pack inside the session cookie
    memberships = json.dumps({"orgs": user_orgs, "teams": user_teams})
    session["github_memberships"] = memberships
