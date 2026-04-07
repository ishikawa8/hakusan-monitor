"""Basic API tests."""

import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_root(client):
    async with client as ac:
        resp = await ac.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == "2.2.0"


@pytest.mark.asyncio
async def test_health(client):
    async with client as ac:
        resp = await ac.get("/api/v1/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_public_weather(client):
    async with client as ac:
        resp = await ac.get("/api/v1/public/weather")
    assert resp.status_code == 200
    data = resp.json()
    assert "mountain_top" in data
    assert "grade" in data


@pytest.mark.asyncio
async def test_public_current(client):
    async with client as ac:
        resp = await ac.get("/api/v1/public/current")
    assert resp.status_code == 200
    assert "locations" in resp.json()


@pytest.mark.asyncio
async def test_admin_requires_auth(client):
    async with client as ac:
        resp = await ac.get("/api/v1/admin/dashboard")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_device_requires_api_key(client):
    async with client as ac:
        resp = await ac.post("/api/v1/sensor/count", json={
            "device_id": "test_device",
            "timestamp": "2026-07-15T10:00:00+09:00",
            "up_count": 5,
            "down_count": 2,
        })
    assert resp.status_code == 401
