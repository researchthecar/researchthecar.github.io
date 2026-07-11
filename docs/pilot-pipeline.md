# Pilot Pipeline

This is the first implementation milestone for the reprocessing project. It intentionally avoids LLM calls.

## Goal

Prove that we can:

1. Match a vehicle against `data/vehicle_registry.json`.
2. Fetch official NHTSA recall and complaint data.
3. Cache raw responses locally.
4. Normalize records into a shared evidence schema.
5. Validate basic source/evidence invariants.
6. Render a readable draft Markdown page outside production `_posts/`.

## Pilot Manifest

The starter manifest is `data/pilot_vehicles.json`. It contains 25 representative vehicles that exist in the current inventory.

The pipeline now treats `assets/cars_parsed.json` as legacy input. Build the curated registry with:

```sh
python3 scripts/build_registry.py
```

Runtime ingestion uses `data/vehicle_registry.json`, where canonical names and source-specific names can be patched once and reused.

When source failures occur, inspect `data/rendered/source_failures.json`, patch `data/vehicle_registry.json`, and rerun the batch. Use deterministic source checks first; LLM calls should be reserved for suggesting likely aliases when source discovery does not give a clear answer.

## Commands

Run the full pipeline for one vehicle:

```sh
python3 scripts/run_vehicle.py --year 2015 --make Kia --model Soul
```

Run the full 25-vehicle pilot manifest:

```sh
python3 scripts/run_pilot.py
```

The batch runner is cache-aware. Existing raw files in `data/raw/nhtsa/` are reused unless `--refresh` is passed.

Write a summary only for the first three vehicles:

```sh
python3 scripts/run_pilot.py --limit 3
```

Use cached raw data and skip NHTSA network calls:

```sh
python3 scripts/run_pilot.py --skip-ingest
```

Write a focused source failure report:

```sh
python3 scripts/report_source_failures.py
```

Write a synthesis readiness report:

```sh
python3 scripts/report_quality.py
```

Generate structured synthesis reports for vehicles marked `ready_for_synthesis`:

```sh
python3 scripts/synthesize_reports.py --provider draft
```

Render one synthesis JSON report to Markdown:

```sh
python3 scripts/render_synthesis.py data/reports/2015-kia-soul.json
```

Render all synthesis reports:

```sh
python3 scripts/render_synthesis.py
```

The `draft` provider is deterministic and does not call an LLM. It validates the pipeline shape before token spend. The optional `gemini` provider requires `GEMINI_API_KEY` and uses Gemini structured output with JSON schema.

Run steps separately:

```sh
python3 scripts/ingest_nhtsa.py --year 2015 --make Kia --model Soul
python3 scripts/normalize_evidence.py --year 2015 --make Kia --model Soul
python3 scripts/validate_report.py data/normalized/vehicles/2015-kia-soul.json
python3 scripts/render_post.py data/normalized/vehicles/2015-kia-soul.json
```

Generated output is ignored by Git:

- `data/raw/`
- `data/normalized/`
- `data/rendered/`
- `data/reports/`

## Current Scope

The first normalizer supports:

- NHTSA recalls
- NHTSA complaints

It does not yet synthesize final issue narratives. The rendered Markdown is an evidence audit view, not a replacement production article.

## Quality Statuses

The quality report writes `data/rendered/pilot_quality_report.json` and assigns each normalized vehicle one status:

- `ready_for_synthesis`: both NHTSA source types are present and evidence volume is sufficient.
- `needs_source_fix`: at least one source failed or is missing.
- `needs_deduping`: evidence is present, but complaint volume is high enough that clustering/deduping should happen before synthesis.
- `needs_review`: evidence exists, but category/component quality looks suspicious.
- `low_evidence`: there are too few records to support a confident generated report.

Initial thresholds are intentionally conservative and should be tuned after reviewing the pilot results.

## Current Pilot Findings

The first 25-vehicle pilot confirmed that most inventory vehicles can be fetched directly from NHTSA. One useful naming/access gap surfaced:

- `2020 Tesla 3` needs the NHTSA query alias `Model 3`.
- `2013 Ford F-150` recall data works, but the NHTSA complaints endpoint returned `400` for the tested model names.

The batch runner treats source-fetch failures as source coverage issues. It still renders partial evidence pages when at least one raw source is available.

## Next Steps

After the NHTSA-only pilot works, add:

- richer validation using `schemas/normalized_vehicle.schema.json`,
- LLM synthesis from normalized evidence,
- final report schema and Jekyll production renderer.
