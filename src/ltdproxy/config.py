"""Configuration definition."""

from __future__ import annotations

import os
from enum import Enum
from typing import Optional

from pydantic import BaseSettings, Field, FilePath, HttpUrl, SecretStr

__all__ = ["Configuration", "config", "Profile", "LogLevel"]


class LogLevel(str, Enum):
    DEBUG = "DEBUG"

    INFO = "INFO"

    WARNING = "WARNING"

    ERROR = "ERROR"

    CRITICAL = "CRITICAL"


class Profile(str, Enum):
    production = "production"

    development = "development"


class Configuration(BaseSettings):
    """Configuration for ltdproxy."""

    name: str = Field("ltdproxy", env="SAFIR_NAME")

    profile: Profile = Field(Profile.production, env="SAFIR_PROFILE")

    log_level: LogLevel = Field(LogLevel.INFO, env="SAFIR_LOG_LEVEL")

    logger_name: str = Field("ltdproxy", env="SAFIR_LOGGER")

    s3_bucket: str = Field("test", env="LTDPROXY_S3_BUCKET")

    s3_bucket_prefix: str = Field("", env="LTDPROXY_S3_PREFIX")

    aws_region: str = Field("us-central-1", env="LTDPROXY_AWS_REGION")

    aws_access_key_id: SecretStr = Field(..., env="LTDPROXY_AWS_ACCESS_KEY_ID")

    aws_secret_access_key: SecretStr = Field(
        ..., env="LTDPROXY_AWS_SECRET_ACCESS_KEY"
    )

    github_oauth_client_id: str = Field(env="LTDPROXY_GITHUB_OAUTH_ID")

    github_oauth_client_secret: SecretStr = Field(
        env="LTDPROXY_GITHUB_OAUTH_SECRET"
    )

    github_oauth_callback_url: HttpUrl = Field(
        env="LTDPROXY_GITHUB_CALLBACK_URL"
    )

    session_key: SecretStr = Field(env="LTDPROXY_SESSION_KEY")

    github_auth_config_path: FilePath = Field(env="LTDPROXY_AUTH_CONFIG")

    path_prefix: str = Field("/", env="LTDPROXY_PATH_PREFIX")

    rewrites_config_path: FilePath = Field(env="LTDPROXY_REWRITES_CONFIG")

    healthcheck_bucket_key: Optional[str] = Field(
        None,
        description=(
            "A key in the bucket that the healthcheck endpoint will attempt "
            "to stream. This is an actual bucket key, and is independent "
            "of the s3_bucket_prefix configuration."
        ),
        env="LTDPROXY_S3_HEALTHCHECK_KEY",
    )


config = Configuration(_env_file=os.getenv("LTD_PROXY_ENV"))
"""Configuration for ltd-proxy."""
