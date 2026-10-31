"""Integration tests: require the Docker stack. Run with `pytest -m integration`."""

import pytest

from scripts.check_infra import check_object_storage, check_postgres

pytestmark = pytest.mark.integration


def test_postgres_reachable_with_raw_schema():
    check_postgres()


def test_object_storage_round_trip():
    check_object_storage()
