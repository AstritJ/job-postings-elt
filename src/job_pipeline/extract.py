"""Extract: fetch raw API pages and land them, untouched, in object storage.

Layout (Hive-style partitions, the same convention S3/Athena/Spark use):

    s3://raw-job-postings/source=<name>/ingest_date=<YYYY-MM-DD>/page-0001.json
                                                                 page-0002.json
                                                                 _manifest.json

Idempotency: a run *overwrites its whole partition* (source + ingest_date).
Re-running the same day replaces that day's files instead of adding duplicates.
The manifest is written last; the loader refuses partitions without one, so a
crashed half-finished extract can never be loaded.
"""

import json
from datetime import UTC, date, datetime

from job_pipeline.clients import get_s3_client
from job_pipeline.config import get_settings
from job_pipeline.sources import Source, make_http_client

MANIFEST = "_manifest.json"


def partition_prefix(source_name: str, ingest_date: date) -> str:
    return f"source={source_name}/ingest_date={ingest_date.isoformat()}/"


def _clear_prefix(s3, bucket: str, prefix: str) -> int:
    """Delete every object under prefix (so a re-run never leaves stale pages behind)."""
    deleted = 0
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
        keys = [{"Key": obj["Key"]} for obj in page.get("Contents", [])]
        if keys:
            s3.delete_objects(Bucket=bucket, Delete={"Objects": keys})
            deleted += len(keys)
    return deleted


def _put_json(s3, bucket: str, key: str, obj) -> None:
    body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
    s3.put_object(Bucket=bucket, Key=key, Body=body, ContentType="application/json")


def run_extract(source: Source, ingest_date: date, max_pages: int, s3=None, http=None) -> dict:
    s3 = s3 or get_s3_client()
    bucket = get_settings().s3_bucket_raw
    prefix = partition_prefix(source.name, ingest_date)

    removed = _clear_prefix(s3, bucket, prefix)
    if removed:
        print(f"  overwriting partition: removed {removed} old object(s)")

    files, job_count = [], 0
    own_http = http is None
    http = http or make_http_client()
    try:
        for page_no, payload in enumerate(source.fetch_pages(http, max_pages), start=1):
            key = f"{prefix}page-{page_no:04d}.json"
            _put_json(s3, bucket, key, payload)
            n = len(source.jobs_in(payload))
            files.append(key)
            job_count += n
            print(f"  page {page_no}: {n} jobs -> s3://{bucket}/{key}")
    finally:
        if own_http:
            http.close()

    manifest = {
        "source": source.name,
        "ingest_date": ingest_date.isoformat(),
        "extracted_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "pages": len(files),
        "jobs": job_count,
        "files": files,
    }
    _put_json(s3, bucket, prefix + MANIFEST, manifest)  # written last = "partition complete"
    return manifest
