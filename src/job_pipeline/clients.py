"""Factory functions for the storage clients used across the pipeline."""

import boto3
import psycopg
from botocore.config import Config

from job_pipeline.config import Settings, get_settings


def get_s3_client(settings: Settings | None = None):
    """boto3 S3 client pointed at the configured endpoint (local SeaweedFS or real AWS)."""
    s = settings or get_settings()
    return boto3.client(
        "s3",
        endpoint_url=s.s3_endpoint_url,
        aws_access_key_id=s.s3_access_key,
        aws_secret_access_key=s.s3_secret_key.get_secret_value(),
        region_name=s.s3_region,
        # Path-style URLs (http://host/bucket/key) work with any S3-compatible store.
        config=Config(s3={"addressing_style": "path"}, retries={"max_attempts": 3}),
    )


def get_pg_connection(settings: Settings | None = None) -> psycopg.Connection:
    """New psycopg connection to the warehouse. Use it as a context manager."""
    s = settings or get_settings()
    return psycopg.connect(s.postgres_conninfo, connect_timeout=5)
