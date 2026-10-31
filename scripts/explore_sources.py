"""Source profiling: fetch one small page from each job API and describe its shape.

Run:  python scripts/explore_sources.py

For each source it
  * prints the top-level keys and pagination fields,
  * prints every field of a job object with its type and an example value,
  * saves a 5-job sample to data/samples/<source>_sample.json (committed to git,
    used later as test fixtures).

Profiling a source *before* writing the extractor is a standard data engineering
step: it tells you the grain, the keys, which fields are nullable and how paging works.
Uses only the standard library on purpose, so it runs before any extractor exists.
"""

import json
import time
import urllib.request
from pathlib import Path

SOURCES = {
    "arbeitnow": "https://www.arbeitnow.com/api/job-board-api?page=1",
    "himalayas": "https://himalayas.app/jobs/api?limit=5&offset=0",
}
JOB_LIST_KEYS = ("data", "jobs", "results")  # where each API keeps its list of jobs
USER_AGENT = "job-postings-elt/0.1 (learning project; github.com/AstritJ/job-postings-elt)"
SAMPLES_DIR = Path("data/samples")


def fetch_json(url: str) -> dict | list:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def find_jobs(payload: dict | list) -> tuple[str, list]:
    if isinstance(payload, list):
        return "<root list>", payload
    for key in JOB_LIST_KEYS:
        if isinstance(payload.get(key), list):
            return key, payload[key]
    raise ValueError(f"no job list found; top-level keys: {list(payload)}")


def preview(value, width: int = 70) -> str:
    text = json.dumps(value, ensure_ascii=False)
    return text if len(text) <= width else text[: width - 3] + "..."


def profile(name: str, url: str) -> None:
    print(f"\n{'=' * 80}\nSOURCE: {name}\nURL:    {url}\n{'=' * 80}")
    payload = fetch_json(url)
    jobs_key, jobs = find_jobs(payload)

    if isinstance(payload, dict):
        print("Top-level keys / pagination:")
        for key, value in payload.items():
            shown = f"list[{len(value)}]" if key == jobs_key else preview(value)
            print(f"  {key:<15} {shown}")

    print(f"\nJobs are under '{jobs_key}'. Fields of the first job:")
    for key, value in jobs[0].items():
        print(f"  {key:<22} {type(value).__name__:<6} {preview(value)}")

    # Which fields are sometimes empty? Important for NOT NULL decisions later.
    nullable = sorted({k for job in jobs for k, v in job.items() if v in (None, "", [], {})})
    print(f"\nFields empty in at least one of {len(jobs)} jobs: {nullable or 'none'}")

    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    sample = dict(payload) if isinstance(payload, dict) else {}
    sample[jobs_key] = jobs[:5]
    out = SAMPLES_DIR / f"{name}_sample.json"
    out.write_text(json.dumps(sample, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"\nSaved sample -> {out}")


def main() -> None:
    for i, (name, url) in enumerate(SOURCES.items()):
        if i:
            time.sleep(2)  # be polite between requests
        try:
            profile(name, url)
        except Exception as exc:
            print(f"\n{name}: FAILED - {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
