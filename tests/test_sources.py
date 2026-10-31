import httpx
import pytest
from conftest import arbeitnow_handler, himalayas_handler, load_sample

from job_pipeline import sources
from job_pipeline.sources import Arbeitnow, Himalayas, get_json


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(sources.time, "sleep", lambda s: None)


def test_arbeitnow_follows_links_next_until_last_page(mock_http):
    pages = list(Arbeitnow().fetch_pages(mock_http(arbeitnow_handler(pages=3)), max_pages=10))
    assert len(pages) == 3


def test_himalayas_follows_cursor_until_last_page(mock_http):
    pages = list(Himalayas().fetch_pages(mock_http(himalayas_handler(pages=2)), max_pages=10))
    assert len(pages) == 2


@pytest.mark.parametrize("source", [Arbeitnow(), Himalayas()])
def test_max_pages_caps_the_crawl(source, mock_http):
    handler = arbeitnow_handler(pages=5) if source.name == "arbeitnow" else himalayas_handler(5)
    assert len(list(source.fetch_pages(mock_http(handler), max_pages=2))) == 2


def test_job_ids_are_unique_natural_keys():
    for source, sample in [(Arbeitnow(), "arbeitnow"), (Himalayas(), "himalayas")]:
        jobs = source.jobs_in(load_sample(sample))
        ids = [source.job_id(j) for j in jobs]
        assert all(ids) and len(ids) == len(set(ids))


def test_get_json_retries_on_rate_limit(mock_http):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] < 3:
            return httpx.Response(429)
        return httpx.Response(200, json={"ok": True})

    assert get_json(mock_http(handler), "https://example.test/api") == {"ok": True}
    assert calls["n"] == 3


def test_get_json_gives_up_after_max_attempts(mock_http):
    client = mock_http(lambda r: httpx.Response(503))
    with pytest.raises(RuntimeError, match="giving up"):
        get_json(client, "https://example.test/api", attempts=2)


def test_get_json_does_not_retry_client_errors(mock_http):
    with pytest.raises(httpx.HTTPStatusError):
        get_json(mock_http(lambda r: httpx.Response(404)), "https://example.test/api")
