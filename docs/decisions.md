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
