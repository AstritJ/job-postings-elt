from job_pipeline.config import Settings


def make_settings(**overrides) -> Settings:
    values = {
        "postgres_user": "u",
        "postgres_password": "pg-pw-123",
        "postgres_db": "db",
        "s3_access_key": "ak",
        "s3_secret_key": "s3-pw-456",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_conninfo_contains_all_parts():
    s = make_settings(postgres_host="pg", postgres_port=6543)
    info = s.postgres_conninfo
    for part in ("host=pg", "port=6543", "dbname=db", "user=u", "password=pg-pw-123"):
        assert part in info


def test_secrets_are_hidden_in_repr():
    """Passwords must never leak into logs via repr()/print()."""
    s = make_settings()
    assert "pg-pw-123" not in repr(s)
    assert "s3-pw-456" not in repr(s)


def test_defaults():
    s = make_settings()
    assert s.postgres_port == 5432
    assert s.s3_bucket_raw == "raw-job-postings"
