-- Runs once when the Postgres container starts with an empty data volume.
--
-- Layering (ELT):
--   raw      -> data exactly as scraped; loaded by Python, never edited by hand
--   staging  -> cleaned / typed / deduplicated   (built by dbt, Phase 3)
--   marts    -> star schema: facts + dimensions  (built by dbt, Phase 3)
--
-- dbt creates its own schemas, so only `raw` is created here.

CREATE SCHEMA IF NOT EXISTS raw;

COMMENT ON SCHEMA raw IS 'Landing zone: untransformed scraped data. Owned by the loader.';
