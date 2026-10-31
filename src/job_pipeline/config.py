"""Central configuration, read from environment variables / the .env file.

Every component (loader, scrapers, Airflow tasks) imports settings from here,
so connection details live in exactly one place.
"""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # PostgreSQL
    postgres_user: str
    postgres_password: SecretStr
    postgres_db: str
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # S3-compatible object storage
    s3_endpoint_url: str = "http://localhost:8333"
    s3_access_key: str
    s3_secret_key: SecretStr
    s3_region: str = "us-east-1"
    s3_bucket_raw: str = "raw-job-postings"

    @property
    def postgres_conninfo(self) -> str:
        """libpq connection string for psycopg."""
        return (
            f"host={self.postgres_host} port={self.postgres_port} "
            f"dbname={self.postgres_db} user={self.postgres_user} "
            f"password={self.postgres_password.get_secret_value()}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
