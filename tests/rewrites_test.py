"""Tests for the RewriteEngine."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from ltdproxy.rewrites import RewriteEngine


@pytest.mark.asyncio
async def test_rule_matching() -> None:
    http_client = httpx.AsyncClient()
    config_path = Path(__file__).parent / "rewrites.example.yaml"
    engine = RewriteEngine.init_from_file(
        path=config_path, http_client=http_client
    )

    result = engine.find_matching_rule("/")
    assert result is not None
    rule, _ = result
    assert rule.substitution == "http://spherex-doc-portal/"

    assert engine.find_matching_rule("/mydoc/") is None
