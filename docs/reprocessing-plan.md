# Vehicle Report Reprocessing Plan

## Objective

Rebuild the vehicle report generation system around structured evidence and validation. The website can remain Jekyll/GitHub Pages while the data pipeline is rebuilt; a frontend migration should happen only if it improves readability, source presentation, or maintainability.

## Current State

- The repo contains roughly 12.7k generated Markdown posts under `_posts/`.
- Vehicle inventory lives in `assets/cars_parsed.json`.
- Existing pages are prose-first and do not retain citations, source IDs, confidence scores, or validation artifacts.
- The old content should be considered useful for page inventory and layout examples, not as trusted reliability data.

## Target Architecture

```text
assets/
  cars_parsed.json        # legacy inventory input
data/
  vehicle_registry.json   # curated canonical/source-specific registry
  raw/
    nhtsa/
    web/
    reddit/
  normalized/
    evidence/
    vehicles/
  reports/
    2015-kia-soul.json
scripts/
  ingest_nhtsa.py
  ingest_web.py
  normalize_evidence.py
  synthesize_report.py
  validate_report.py
  render_post.py
  run_vehicle.py
ai/
  providers/
    base.py
    gemini.py
    openai.py
    ollama.py
```

This structure is intentionally script-oriented. Add LangGraph or another orchestrator only after the basic pipeline is reliable.

## Source Strategy

Use sources in tiers:

1. Official and structured sources: NHTSA recalls, complaints, investigations, manufacturer communications, and safety ratings.
2. Reputable secondary sources: public TSB summaries, repair publications, manufacturer pages, trusted automotive media.
3. Community sources: forums, Reddit, public owner discussions, YouTube comments, and similar material.

Community evidence can reveal recurring symptoms, but it should not be the only support for high-confidence claims.

## Report Schema Direction

Each generated report should keep:

- `vehicle`: year, make, model, slug, optional trim/engine context.
- `sources`: source type, URL/API endpoint, source ID, retrieval timestamp, license/terms notes when relevant.
- `issues`: category, component, title, symptoms, affected configurations, evidence references, severity, frequency signal, confidence.
- `summary`: short readable overview grounded in issue data.
- `validation`: pass/fail, warnings, validator version, generation model, generated timestamp.

## Pipeline Steps

1. Inventory
   - Read `assets/cars_parsed.json` as legacy input.
   - Build `data/vehicle_registry.json` as the curated source list.
   - Normalize make/model names and URL slugs.
   - Reconcile mismatches between inventory and `_posts/`.

2. Ingest
   - Fetch official API data first.
   - Cache raw responses before transformation.
   - Store enough request metadata to reproduce the run.

3. Normalize
   - Convert recalls, complaints, investigations, and web evidence into a common evidence schema.
   - Deduplicate near-identical complaints and recurring issue descriptions.
   - Categorize into stable vehicle systems: engine, transmission, drivetrain, suspension, steering, brakes, electrical, interior, exterior, HVAC, safety, body/paint, and other.

4. Synthesize
   - Feed the LLM only normalized evidence and a strict report schema.
   - Require JSON output.
   - Ask for cautious language when evidence is weak or mixed.

5. Validate
   - Reject missing required sections.
   - Reject uncited issue claims.
   - Warn on overconfident language with weak evidence.
   - Warn on "No major issues" when category evidence exists.
   - Record validation output with the report.

6. Render
   - Render Markdown/Jekyll pages from validated report JSON.
   - Keep citations readable: compact references near issue bullets and a source table near the end.
   - Do not let the model directly write final production Markdown.

7. Pilot
   - Start with 25 representative vehicles.
   - Include high-volume common models, low-volume niche models, older vehicles, newer vehicles, and at least one vehicle with known recalls/complaints.
   - Review quality, cost, runtime, and source coverage before bulk processing.

## Recommended First Milestone

Build a no-LLM pilot that ingests and normalizes NHTSA data for 25 vehicles, writes structured JSON, and renders a source table. This proves vehicle matching, caching, repeatability, and page rendering before adding model synthesis.

## Frontend Notes

Keep Jekyll initially. Consider Astro later if:

- citation tables and structured issue components become awkward in Markdown,
- build times become painful,
- client-side search needs richer filtering,
- or the site needs a stronger vehicle comparison/search experience.
