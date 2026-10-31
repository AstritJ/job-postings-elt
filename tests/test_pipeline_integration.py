"""End-to-end extract + load against the real Docker stack, with mocked HTTP.

The key property under test is IDEMPOTENCY: running the same partition twice
must leave exactly the same data as running it once.

Run with: pytest -m integration   (needs `docker compose up -d`)
"""

from datetime import date

import pytest
from conftest import arbeitnow_handler, himalayas_handler

from job_pipeline import sources
from job_pipeline.clients import get_pg_connection, get_s3_client
from job_pipeline.config import get_settings
from job_pipeline.extract import _clear_prefix, partition_prefix, run_extract
from job_pipeline.load import run_load
from job_pipeline.sources import Arbeitnow, Himalayas

pytestmark = pytest.mark.integration
TEST_DATE = date(2000, 1, 1)  # far from real data, cleaned up afterwards


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr(sources.time, "sleep", lambda s: None)


@pytest.fixture(params=["arbeitnow", "himalayas"])
def case(request):
    if request.param == "arbeitnow":
        yield Arbeitnow(), arbeitnow_handler(pages=2, per_page=2)
    else:
        yield Himalayas(), himalayas_handler(pages=2, per_page=2)
    # cleanup: remove test files and rows
    source = Arbeitnow() if request.param == "arbeitnow" else Himalayas()
    _clear_prefix(
        get_s3_client(), get_settings().s3_bucket_raw, partition_prefix(source.name, TEST_DATE)
    )
    with get_pg_connection() as conn:
        conn.execute(
            "DELETE FROM raw.job_postings WHERE source = %s AND ingest_date = %s",
            (source.name, TEST_DATE),
        )


def count_rows(source_name: str) -> int:
    with get_pg_connection() as conn:
        return conn.execute(
            "SELECT count(*) FROM raw.job_postings WHERE source = %s AND ingest_date = %s",
            (source_name, TEST_DATE),
        ).fetchone()[0]


def test_extract_and_load_are_idempotent(case, mock_http):
    source, handler = case

    manifest = run_extract(source, TEST_DATE, max_pages=5, http=mock_http(handler))
    assert manifest["pages"] == 2 and manifest["jobs"] == 4
    assert run_load(source, TEST_DATE) == 4
    assert count_rows(source.name) == 4

    # Second run of the SAME partition: overwrite, never duplicate.
    run_extract(source, TEST_DATE, max_pages=5, http=mock_http(handler))
    run_load(source, TEST_DATE)
    assert count_rows(source.name) == 4


def test_load_refuses_partition_without_manifest():
    with pytest.raises(RuntimeError, match="no manifest"):
        run_load(Arbeitnow(), date(1999, 12, 31))
