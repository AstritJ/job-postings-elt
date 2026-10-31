-- Raw landing table for job postings from every source.
--
-- Grain: one row per job, per source, per ingest day (a daily snapshot).
-- Keeping a row per day is what later lets dbt derive first_seen / last_seen
-- and track changes over time (SCD Type 2).
--
-- payload holds the job exactly as the API returned it (JSONB). No cleaning
-- happens here - that is dbt's job in the staging layer (ELT, not ETL).

CREATE TABLE IF NOT EXISTS raw.job_postings (
    source         text        NOT NULL,
    source_job_id  text        NOT NULL,   -- natural key within the source (slug / guid)
    ingest_date    date        NOT NULL,
    payload        jsonb       NOT NULL,
    s3_key         text        NOT NULL,   -- lineage: which landed file this row came from
    loaded_at      timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (source, source_job_id, ingest_date)
);

COMMENT ON TABLE raw.job_postings IS
    'Untransformed job postings. Grain: source + source_job_id + ingest_date.';
