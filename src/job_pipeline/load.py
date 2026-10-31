"""Load: copy a landed partition from object storage into raw.job_postings.

Idempotency: inside ONE transaction we delete the partition's rows
(source + ingest_date) and insert them again with COPY. If anything fails the
transaction rolls back, so the table is never left half-loaded, and loading the
same day twice gives exactly the same result as loading it once.
"""

import json
from datetime import date
from pathlib import Path

from psycopg.types.json import Jsonb

from job_pipeline.clients import get_pg_connection, get_s3_client
from job_pipeline.config import get_settings
from job_pipeline.extract import MANIFEST, partition_prefix
from job_pipeline.sources import Source

DDL_FILE = Path(__file__).resolve().parents[2] / "sql" / "raw" / "job_postings.sql"


def ensure_raw_table(conn) -> None:
    conn.execute(DDL_FILE.read_text(encoding="utf-8"))


def _get_json(s3, bucket: str, key: str):
    return json.loads(s3.get_object(Bucket=bucket, Key=key)["Body"].read())


def read_partition(source: Source, ingest_date: date, s3=None) -> list[tuple]:
    """Return de-duplicated rows for one partition, ready for COPY."""
    s3 = s3 or get_s3_client()
    bucket = get_settings().s3_bucket_raw
    prefix = partition_prefix(source.name, ingest_date)
    try:
        manifest = _get_json(s3, bucket, prefix + MANIFEST)
    except s3.exceptions.NoSuchKey:
        raise RuntimeError(
            f"no manifest at {prefix} - extract missing or incomplete; run extract first"
        ) from None

    rows, seen = [], set()
    for key in manifest["files"]:
        for job in source.jobs_in(_get_json(s3, bucket, key)):
            job_id = source.job_id(job)
            if job_id in seen:  # paging can return a job twice; keep the first
                continue
            seen.add(job_id)
            rows.append((source.name, job_id, ingest_date, Jsonb(job), key))
    return rows


def run_load(source: Source, ingest_date: date, s3=None) -> int:
    rows = read_partition(source, ingest_date, s3)
    with get_pg_connection() as conn:  # commits on success, rolls back on error
        ensure_raw_table(conn)
        deleted = conn.execute(
            "DELETE FROM raw.job_postings WHERE source = %s AND ingest_date = %s",
            (source.name, ingest_date),
        ).rowcount
        with conn.cursor().copy(
            "COPY raw.job_postings (source, source_job_id, ingest_date, payload, s3_key) FROM STDIN"
        ) as copy:
            for row in rows:
                copy.write_row(row)
    if deleted:
        print(f"  replaced {deleted} existing row(s) for this partition")
    return len(rows)
