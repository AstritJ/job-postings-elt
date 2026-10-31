"""Smoke test for the local data platform.

Run after `docker compose up -d`:
    python scripts/check_infra.py

Checks that PostgreSQL is reachable and has the `raw` schema, and that object
storage accepts a write/read/delete round-trip in the raw bucket.
Exits with code 1 if anything fails, so it can also be used in CI.
"""

import sys
import uuid

from job_pipeline.clients import get_pg_connection, get_s3_client
from job_pipeline.config import get_settings


def check_postgres() -> None:
    with get_pg_connection() as conn:
        version = conn.execute("SHOW server_version").fetchone()[0]
        has_raw = conn.execute(
            "SELECT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'raw')"
        ).fetchone()[0]
    if not has_raw:
        raise RuntimeError(
            "schema 'raw' missing - was sql/init applied? Reset with: docker compose down -v"
        )
    print(f"  PostgreSQL {version} OK, schema 'raw' present")


def check_object_storage() -> None:
    s3 = get_s3_client()
    bucket = get_settings().s3_bucket_raw
    s3.head_bucket(Bucket=bucket)  # raises if the bucket does not exist

    key = f"_healthcheck/{uuid.uuid4()}.txt"
    s3.put_object(Bucket=bucket, Key=key, Body=b"ok")
    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    s3.delete_object(Bucket=bucket, Key=key)
    if body != b"ok":
        raise RuntimeError("read-back mismatch")
    print(f"  Object storage OK, bucket '{bucket}' read/write works")


def main() -> int:
    failed = False
    for name, check in [("PostgreSQL", check_postgres), ("Object storage", check_object_storage)]:
        print(f"Checking {name}...")
        try:
            check()
        except Exception as exc:  # report every failure, then exit non-zero
            failed = True
            print(f"  FAILED: {type(exc).__name__}: {exc}")
    print("\nAll checks passed." if not failed else "\nSome checks failed.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
