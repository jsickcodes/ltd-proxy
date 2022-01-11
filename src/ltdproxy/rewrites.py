"""Engine for rewriting request URLs to other servers than the S3 bucket."""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Pattern, Tuple

import httpx
import yaml
from pydantic import BaseModel
from starlette.background import BackgroundTask
from starlette.responses import StreamingResponse


class RewriteRule(BaseModel):
    """A single request URL rewrite rule."""

    pattern: Pattern

    substitution: str


class RewriteConfigModel(BaseModel):
    """Model parsing and validating the rewrite rules file."""

    rewrites: List[RewriteRule]

    @classmethod
    def parse_yaml(cls, path: Path) -> RewriteConfigModel:
        """Parse the YAML representation of this configuration model."""
        data = yaml.safe_load(path.read_text())
        return cls.parse_obj(data)


class RewriteEngine:
    """This class holds the URL rewrite configuration and is used by handlers
    to determine if a request should be re-written to another HTTP server
    rather than S3.
    """

    def __init__(
        self,
        *,
        rewrite_rules: List[RewriteRule],
        http_client: httpx.AsyncClient,
    ) -> None:
        self._rewrite_rules = rewrite_rules
        self._http_client = http_client

    @classmethod
    def init_from_file(
        cls, *, path: Path, http_client: httpx.AsyncClient
    ) -> RewriteEngine:
        config_data = RewriteConfigModel.parse_yaml(path)
        return cls(rewrite_rules=config_data.rewrites, http_client=http_client)

    def find_matching_rule(
        self, path: str
    ) -> Optional[Tuple[RewriteRule, re.Match]]:
        for rule in self._rewrite_rules:
            m = rule.pattern.match(path)
            if m:
                return rule, m
        return None

    async def build_stream(self, path: str) -> Optional[httpx.Response]:
        _match = self.find_matching_rule(path)
        if _match is None:
            return None  # no matching rule

        rule, match = _match
        new_url = rule.substitution

        request = self._http_client.build_request("GET", new_url)
        stream = await self._http_client.send(request, stream=True)
        return stream

    async def build_response(self, path: str) -> Optional[StreamingResponse]:
        stream = await self.build_stream(path)
        if stream is None:
            return None

        stream_headers = stream.headers
        response_headers = {}
        copy_headers = ("Content-Type", "Content-length")
        for key in copy_headers:
            if key in stream_headers:
                response_headers[key] = stream_headers[key]

        return StreamingResponse(
            stream.aiter_raw(),
            background=BackgroundTask(stream.aclose),
            headers=response_headers,
        )
