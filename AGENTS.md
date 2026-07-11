# Research the Car Agent Guide

## Project Goal

Research the Car is a static vehicle reliability site. The current `_posts/` corpus was generated from `assets/cars_parsed.json` with older LLM prompts and should be treated as legacy content until reprocessed.

The next phase is to build a cited, evidence-first pipeline that ingests public vehicle data, normalizes it into structured records, uses LLMs only for grounded synthesis, validates every report, and renders consistent Jekyll-compatible pages.

## Repository Shape

- `assets/cars_parsed.json` is legacy vehicle inventory input.
- `data/vehicle_registry.json` is the curated canonical/source-specific vehicle list once generated.
- `_posts/<Make>/<Model>/...md` contains legacy generated Jekyll posts.
- `_layouts/`, `_includes/`, `_sass/`, `_tabs/`, and `_config.yml` are the current Chirpy/Jekyll site.
- `docs/reprocessing-plan.md` describes the target data pipeline.
- `docs/pilot-pipeline.md` describes the current no-LLM NHTSA pilot implementation.
- `docs/codex-cloud-setup.md` describes recommended Codex Cloud setup for this repo.

## Working Agreements

- Keep data accuracy above frontend polish.
- Prefer structured data and schemas over prose-only generation.
- Do not make uncited reliability claims in generated content.
- Preserve source identifiers, URLs, retrieval timestamps, and confidence signals.
- Keep generated output reproducible from checked-in scripts and cached raw inputs.
- Treat Reddit, forums, Facebook, and similar community sources as corroborating evidence, not authoritative sources by themselves.
- Avoid large unrelated refactors while building the reprocessing pipeline.
- Do not overwrite or mass-regenerate `_posts/` without a small reviewed pilot batch first.

## Implementation Preferences

- Use Python for ingestion, normalization, synthesis, validation, and rendering scripts unless there is a clear reason not to.
- Start with plain scripts and explicit inputs/outputs before adding orchestration frameworks.
- Use Pydantic or JSON Schema for report and evidence models.
- Use SQLite or DuckDB for local caches/run metadata when persistence is needed.
- Keep the LLM provider behind a small adapter so Gemini, OpenAI, or local models can be swapped later.
- Render static pages from validated JSON rather than letting the model write final Markdown directly.

## Validation Expectations

Before accepting generated vehicle reports, check that:

- Required sections are present.
- Each issue has at least one supporting source.
- "No major issues" is not emitted when evidence exists for that category.
- Confidence language matches the strength of the evidence.
- Costs are omitted or clearly caveated unless grounded in a source.
- The final page remains readable and does not bury citations in the main narrative.

## Useful Commands

Current site build:

```sh
bundle install
bundle exec jekyll build
```

Production-like build:

```sh
JEKYLL_ENV=production bundle exec jekyll build
```

Run HTML checks if dependencies are installed:

```sh
bundle exec htmlproofer _site --disable-external=true
```

## Review Guidelines

- Prioritize correctness, repeatability, and source traceability.
- Flag any content generation path that can publish uncited model claims.
- Flag schema changes that make old evidence or reports ambiguous.
- Flag broad rewrites of legacy posts unless they are part of an approved pilot or batch migration.
