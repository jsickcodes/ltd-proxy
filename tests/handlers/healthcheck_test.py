"""Test the healthcheck endpoint."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_healthz(client: AsyncClient) -> None:
    """Test ``GET /__healthz``"""
    response = await client.get("/__healthz")
    assert response.status_code == 200
