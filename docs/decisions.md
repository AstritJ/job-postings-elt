# Architecture Decision Log

Short records of *why* the project is built the way it is. Add a new entry whenever a
choice is made that someone reviewing the repo might question.

---

## ADR-001: ELT instead of ETL

**Decision:** Load scraped data into the warehouse untouched (`raw` schema), then transform it with SQL (dbt).

**Why:** Raw data is preserved, so transformation bugs are fixed by re-running SQL instead of re-scraping.
Transformations become version-controlled, testable and documented in one tool.

---

## ADR-002: Fact table grain = one row per job posting

**Decision:** `fct_job_postings` holds one row per posting (accumulating-snapshot style, with first/last seen dates).

**Why:** Simplest grain that answers the main questions (skills in demand, salaries, posting duration).
History of changes (e.g. salary edits) will be added later with dbt snapshots (SCD Type 2) rather than by
increasing the fact table grain.

**Consequence:** Skills are many-to-many, so they live in `bridge_posting_skill`. Aggregate before joining
through the bridge to avoid fan-out (double counting).

---

## ADR-003: SeaweedFS instead of MinIO for local S3 storage

**Decision:** Use SeaweedFS (`weed mini`) as the local S3-compatible object store.

**Why:** MinIO's community edition stopped publishing Docker images in Oct 2025 and its repository was
archived in Apr 2026. SeaweedFS is actively maintained, Apache-2.0 licensed, and exposes the same S3 API,
so pipeline code (boto3) is unchanged and will point at real AWS S3 in Project 2 with only a config change.

---

## ADR-004: PostgreSQL as the warehouse

**Decision:** PostgreSQL 17 in Docker.

**Why:** Free, runs locally, first-class dbt support, and the data volume (thousands to low millions of rows)
is well within its comfort zone. Cloud warehouses come in Project 2.

---

## ADR-005: Public JSON APIs + httpx instead of Scrapy

**Decision:** Source data from the Arbeitnow and Himalayas public job APIs, fetched with `httpx`.

**Why:** The project's focus is the platform (storage, warehouse, modelling, orchestration), so sources
should be stable and legally clean. Both APIs are free, keyless and documented. With JSON APIs there is
no HTML to crawl, so Scrapy would add complexity without benefit. Two sources with different shapes and
pagination styles (page number vs cursor) still exercise multi-source integration.

---

## ADR-006: Raw layer grain = one row per job per source per ingest day

**Decision:** `raw.job_postings` is keyed by `(source, source_job_id, ingest_date)` and stores the job
as untouched JSONB.

**Why:** A daily snapshot of every job keeps history cheaply, so dbt can derive `first_seen` /
`last_seen`, posting duration and SCD Type 2 changes later. Storing JSONB means a schema change at the
source never breaks loading; parsing happens in dbt staging.

---

## ADR-007: Idempotency by partition overwrite

**Decision:** Extract deletes and rewrites the whole `source + ingest_date` prefix in object storage;
load deletes and re-inserts the same partition in Postgres inside one transaction (via `COPY`).
A `_manifest.json` written last marks a partition as complete; the loader refuses partitions without it.

**Why:** Pipelines get re-run (retries, backfills, bug fixes). Overwriting a well-defined partition makes
every re-run safe: same input -> same result, no duplicates, no half-loaded state.
