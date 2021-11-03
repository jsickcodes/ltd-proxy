"""The GitHub OAuth dependency for path operations."""

from __future__ import annotations

import json
from enum import Enum
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    Optional,
    Pattern,
    Set,
    Tuple,
    TypeVar,
)

import authlib.integrations.starlette_client.integration
import gidgethub.httpx
import yaml
from authlib.integrations.starlette_client import OAuth
from pydantic import BaseModel

from ltdproxy.config import config

if TYPE_CHECKING:
    from pathlib import Path

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
    # These orgs and teams are mentioned in the GitHub Auth configuration,
    # and therefore are ones to pay attention to in the cookie.
    relevant_orgs = github_auth.relevant_orgs
    relevant_teams = github_auth.relevant_teams

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


class GitHubGroup(BaseModel):
    """A model for a GitHub group configuration, either an entire organization
    or a team within an organization.
    """

    org: str
    """A GitHub organization's slug."""

    team: Optional[str] = None
    """The name of a team within an organization."""

    @property
    def is_team(self) -> bool:
        if self.team:
            return True
        else:
            return False


class PathRule(BaseModel):
    """A model for a URL path and authorized entities."""

    pattern: Pattern
    """Regular expression pattern that matches a path."""

    authorized: List[GitHubGroup]
    """A list fo GitHub groups (teams and/or organizations) that are
    authorized to access this path.
    """

    def path_matches(self, url_path: str) -> bool:
        """Test if a URL path matches the rule's patten."""
        if self.pattern.match(url_path):
            return True
        else:
            return False

    def is_user_authorized(
        self, *, user_orgs: List[str], user_teams: List[Tuple[str, str]]
    ) -> bool:
        """Test if a user is authorized for this path.

        The parameters come from the ``github_memberships`` attribute of
        the session cookie, after parsing from JSON.
        """
        for authorized_group in self.authorized:
            if authorized_group.is_team:
                authorized_team_id = (
                    authorized_group.org,
                    authorized_group.team,
                )
                if authorized_team_id in user_teams:
                    return True
            else:
                if authorized_group.org in user_orgs:
                    return True

        # no matches
        return False


class AuthResult(str, Enum):
    """The authentication/authorization result."""

    authorized = "authorized"
    unauthorized = "unauthorized"
    unauthenticated = "unauthenticated"


class GitHubAuth(BaseModel):
    """A model for the GitHubAuth configuration file, with methods for
    determining if a requester is authorized to view a given path.
    """

    default: List[GitHubGroup]
    """Default authorized groups if a path does not match."""

    paths: List[PathRule]
    """A list of path expressions and the groups that are authorized to
    access those paths.
    """

    @classmethod
    def parse_yaml(cls, path: Path) -> GitHubAuth:
        """Parse the YAML representation of this configuration model."""
        data = yaml.safe_load(path.read_text())
        return cls.parse_obj(data)

    def is_user_authorized(
        self,
        *,
        url_path: str,
        user_orgs: List[str],
        user_teams: List[Tuple[str, str]],
    ) -> bool:
        for path_rule in self.paths:
            if path_rule.path_matches(url_path):
                if path_rule.is_user_authorized(
                    user_orgs=user_orgs, user_teams=user_teams
                ):
                    return True
                else:
                    return False

        # Fallback to the default authorizations
        for authed_group in self.default:
            if authed_group.is_team:
                authorized_team_id = (authed_group.org, authed_group.team)
                if authorized_team_id in user_teams:
                    return True
            else:
                if authed_group.org in user_orgs:
                    return True

        return False

    def is_session_authorized(
        self, *, path: str, session: Dict[Any, Any]
    ) -> AuthResult:
        try:
            github_memberships_data = session["github_memberships"]
        except KeyError:
            return AuthResult.unauthenticated

        parsed_memberships = json.loads(github_memberships_data)
        user_orgs = parsed_memberships["orgs"]
        # This typechecks/validates the teams data structure
        user_teams = [
            (str(t[0]), str(t[1])) for t in parsed_memberships["teams"]
        ]
        if self.is_user_authorized(
            url_path=path, user_orgs=user_orgs, user_teams=user_teams
        ):
            return AuthResult.authorized
        else:
            return AuthResult.unauthorized

    @property
    def relevant_orgs(self) -> Set[str]:
        """Get all GitHub organizations mentioned in the configuration."""
        all_orgs: Set[str] = set()

        for github_group in self.default:
            if not github_group.is_team:
                all_orgs.add(github_group.org)

        for path_rule in self.paths:
            for github_group in path_rule.authorized:
                if not github_group.is_team:
                    all_orgs.add(github_group.org)

        return all_orgs

    @property
    def relevant_teams(self) -> Set[Tuple[str, str]]:
        """Get all GitHub teams mentioned in the configuration."""
        all_teams: Set[Tuple[str, str]] = set()

        for github_group in self.default:
            if github_group.is_team:
                assert isinstance(github_group.team, str)  # mypy cue
                all_teams.add((github_group.org, github_group.team))

        for path_rule in self.paths:
            for github_group in path_rule.authorized:
                if github_group.is_team:
                    assert isinstance(github_group.team, str)  # mypy cue
                    all_teams.add((github_group.org, github_group.team))

        return all_teams


github_auth = GitHubAuth.parse_yaml(config.github_auth_config_path)
"""FastAPI dependency providing the GitHub auth rules for different paths."""


async def github_auth_dependency() -> GitHubAuth:
    return github_auth
