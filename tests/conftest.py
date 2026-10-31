"""Shared fixtures: fake job APIs built from the real samples in data/samples/.

httpx.MockTransport answers HTTP requests in-process, so tests exercise the real
pagination code without touching the internet (fast, deterministic, CI-friendly).
"""

import json
from pathlib import Path

import httpx
import pytest

SAMPLES = Path(__file__).resolve().parents[1] / "data" / "samples"


def load_sample(name: str) -> dict:
    return json.loads((SAMPLES / f"{name}_sample.json").read_text(encoding="utf-8"))


def arbeitnow_handler(pages: int = 2, per_page: int = 2):
    """Serve the sample's jobs as `pages` pages linked via links.next."""
    jobs = load_sample("arbeitnow")["data"]

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params.get("page", 1))
        chunk = jobs[(page - 1) * per_page : page * per_page]
        nxt = f"https://www.arbeitnow.com/api/job-board-api?page={page + 1}"
        return httpx.Response(
            200, json={"data": chunk, "links": {"next": nxt if page < pages else None}}
        )

    return handler


def himalayas_handler(pages: int = 2, per_page: int = 2):
    """Serve the sample's jobs as `pages` pages linked via nextCursor."""
    jobs = load_sample("himalayas")["jobs"]

    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params.get("cursor", "c1")[1:])
        chunk = jobs[(page - 1) * per_page : page * per_page]
        nxt = f"c{page + 1}" if page < pages else None
        return httpx.Response(200, json={"jobs": chunk, "nextCursor": nxt})

    return handler


@pytest.fixture
def mock_http():
    """Factory: mock_http(handler) -> httpx.Client backed by that handler."""
    clients = []

    def make(handler) -> httpx.Client:
        client = httpx.Client(transport=httpx.MockTransport(handler))
        clients.append(client)
        return client

    yield make
    for c in clients:
        c.close()
