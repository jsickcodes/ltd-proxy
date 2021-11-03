"""Test the githubauth module."""

from __future__ import annotations

import json
from pathlib import Path

from ltdproxy.githubauth import AuthResult, GitHubAuth, GitHubGroup, PathRule


def test_path_rule() -> None:
    org_group = GitHubGroup(org="jsickcodes")
    rule1 = PathRule(pattern=r"\/a\/", authorized=[org_group])
    assert rule1.path_matches("/a/hello-world.html")
    assert not rule1.path_matches("/b/hello-world.html")


def test_githubauth_example_yaml() -> None:
    """Test GitHubAuth class with the example YAML file,
    tests/githubauth.example.yaml.
    """
    example_path = Path(__file__).parent / "githubauth.example.yaml"
    assert example_path.is_file()

    github_auth = GitHubAuth.parse_yaml(example_path)

    assert github_auth.relevant_orgs == set(["jsickcodes"])
    assert github_auth.relevant_teams == set(
        [
            ("jsickcodes", "Red Team"),
            ("jsickcodes", "Blue Team"),
        ]
    )

    # Testing the default rule
    assert (
        github_auth.is_user_authorized(
            url_path="/xyz", user_orgs=["jsickcodes"], user_teams=[]
        )
        is True
    )

    # Testing the default rule
    assert (
        github_auth.is_user_authorized(
            url_path="/xyz", user_orgs=["jsickwrites"], user_teams=[]
        )
        is False
    )

    # Testing the path rule for /a/
    assert (
        github_auth.is_user_authorized(
            url_path="/a/index.html", user_orgs=["jsickcodes"], user_teams=[]
        )
        is False
    )
    assert (
        github_auth.is_user_authorized(
            url_path="/a/index.html",
            user_orgs=["jsickcodes"],
            user_teams=[("jsickcodes", "Blue Team")],
        )
        is False
    )
    assert (
        github_auth.is_user_authorized(
            url_path="/a/index.html",
            user_orgs=["jsickcodes"],
            user_teams=[
                ("jsickcodes", "Red Team"),
                ("jsickcodes", "Blue Team"),
            ],
        )
        is True
    )

    # Test if the session auth cookie is empty
    assert (
        github_auth.is_session_authorized(path="/xyz", session={})
        is AuthResult.unauthenticated
    )

    # Test if the session auth cookie doesn't have the right membership
    assert (
        github_auth.is_session_authorized(
            path="/xyz",
            session={
                "github_memberships": json.dumps(
                    {"orgs": "acompany", "teams": []}
                )
            },
        )
        is AuthResult.unauthorized
    )

    # Test if the session auth cookie *does* have the right membership
    assert (
        github_auth.is_session_authorized(
            path="/xyz",
            session={
                "github_memberships": json.dumps(
                    {"orgs": "jsickcodes", "teams": []}
                )
            },
        )
        is AuthResult.authorized
    )

    assert (
        github_auth.is_session_authorized(
            path="/a/hello",
            session={
                "github_memberships": json.dumps(
                    {
                        "orgs": "jsickcodes",
                        "teams": [["jsickcodes", "Red Team"]],
                    }
                )
            },
        )
        is AuthResult.authorized
    )

    assert (
        github_auth.is_session_authorized(
            path="/a/hello",
            session={
                "github_memberships": json.dumps(
                    {"orgs": "jsickcodes", "teams": []}
                )
            },
        )
        is AuthResult.unauthorized
    )
