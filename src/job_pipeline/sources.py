"""Job sources: how to page through each API and how to identify a job.

Each source knows only three things:
  * how to fetch its pages (pagination differs per API),
  * where the list of jobs sits inside a response,
  * which field uniquely identifies a job (the *natural key*).

Everything else (landing, loading, modelling) is source-agnostic, so adding a
new source means adding one class here.
"""

import time
from abc import ABC, abstractmethod
from collections.abc import Iterator

import httpx

USER_AGENT = "job-postings-elt/0.1 (learning project; github.com/AstritJ/job-postings-elt)"
RETRY_STATUS = {429, 500, 502, 503, 504}


def get_json(client: httpx.Client, url: str, params: dict | None = None, attempts: int = 4):
    """GET with retries + exponential backoff on rate limits, server errors and network blips."""
    for attempt in range(1, attempts + 1):
        try:
            resp = client.get(url, params=params)
            if resp.status_code not in RETRY_STATUS:
                resp.raise_for_status()
                return resp.json()
            wait = float(resp.headers.get("Retry-After", 2**attempt))
            reason = f"HTTP {resp.status_code}"
        except httpx.TransportError as exc:
            wait, reason = 2**attempt, type(exc).__name__
        if attempt == attempts:
            raise RuntimeError(f"giving up on {url} after {attempts} attempts ({reason})")
        print(f"    {reason} - retrying in {wait:.0f}s ({attempt}/{attempts})")
        time.sleep(wait)
    raise AssertionError("unreachable")


class Source(ABC):
    name: str
    id_field: str  # natural key of a job within this source
    jobs_key: str  # where the job list sits in a response

    def __init__(self, page_delay: float = 1.0):
        self.page_delay = page_delay  # politeness pause between page requests

    def jobs_in(self, payload: dict) -> list[dict]:
        return payload.get(self.jobs_key) or []

    def job_id(self, job: dict) -> str:
        return str(job[self.id_field])

    @abstractmethod
    def fetch_pages(self, client: httpx.Client, max_pages: int) -> Iterator[dict]:
        """Yield raw API responses (one per page), untouched."""


class Arbeitnow(Source):
    """https://www.arbeitnow.com/api/job-board-api - page-number pagination, newest first."""

    name, id_field, jobs_key = "arbeitnow", "slug", "data"
    url = "https://www.arbeitnow.com/api/job-board-api"

    def fetch_pages(self, client, max_pages):
        url, params = self.url, {"page": 1}
        for page_no in range(1, max_pages + 1):
            payload = get_json(client, url, params)
            if not self.jobs_in(payload):
                return
            yield payload
            next_url = (payload.get("links") or {}).get("next")
            if not next_url or page_no == max_pages:
                return
            url, params = next_url, None  # next_url already contains ?page=N
            time.sleep(self.page_delay)


class Himalayas(Source):
    """https://himalayas.app/jobs/api - cursor pagination (the API's preferred method)."""

    name, id_field, jobs_key = "himalayas", "guid", "jobs"
    url = "https://himalayas.app/jobs/api"
    page_size = 100

    def fetch_pages(self, client, max_pages):
        params = {"limit": self.page_size}
        for page_no in range(1, max_pages + 1):
            payload = get_json(client, self.url, params)
            if not self.jobs_in(payload):
                return
            yield payload
            cursor = payload.get("nextCursor")
            if not cursor or page_no == max_pages:
                return
            params = {"limit": self.page_size, "cursor": cursor}
            time.sleep(self.page_delay)


SOURCES: dict[str, type[Source]] = {s.name: s for s in (Arbeitnow, Himalayas)}


def make_http_client() -> httpx.Client:
    return httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=30, follow_redirects=True)
