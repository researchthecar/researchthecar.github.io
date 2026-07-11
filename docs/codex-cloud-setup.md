# Codex Cloud Setup Notes

## Purpose

Use Codex Cloud to run repo tasks from another machine, let longer jobs continue in hosted environments, and keep future agents grounded in the same repository instructions.

Codex Cloud does not replace Git as the durable source of truth. Commit important context, scripts, schemas, and docs to the repo so local Codex, Codex Cloud, and future machines see the same project state.

## One-Time Setup

1. Open Codex Cloud from ChatGPT/Codex.
2. Connect the GitHub account that owns this repository.
3. Enable this repository for Codex Cloud.
4. Create a cloud environment for the repo.
5. Configure setup commands and environment variables.
6. Start new tasks from the repo/environment when working away from the local machine.

## Suggested Cloud Environment

Start with the default universal image and automatic package installation. If manual setup is needed, use:

```sh
bundle install
```

For future Python pipeline work, once a Python project file exists, extend setup with the chosen dependency manager. For example:

```sh
python -m pip install -U pip
python -m pip install -e ".[dev]"
bundle install
```

Only add that Python block after the repo actually has a Python package or requirements file.

## Environment Variables And Secrets

Likely future variables:

```text
GEMINI_API_KEY
OPENAI_API_KEY
NHTSA_USER_AGENT
REDDIT_CLIENT_ID
REDDIT_CLIENT_SECRET
```

Do not add API keys to the repo. Configure them in Codex Cloud environment settings or local shell secrets.

Prefer provider-specific keys only when a task actually needs them. The first no-LLM ingestion milestone should not require model API keys.

## Shared Context Strategy

Put durable context in:

- `AGENTS.md` for agent instructions and review expectations.
- `docs/reprocessing-plan.md` for the architecture and milestone plan.
- checked-in schemas, prompts, and scripts as they are created.
- GitHub branches and pull requests for work handoff.

Use Codex task/chat history for conversational context, but do not rely on it as the only record of project decisions.

## Recommended Task Pattern

Use small, named tasks:

- "Build NHTSA ingestion cache for 25-vehicle pilot"
- "Define Pydantic report schema and validation rules"
- "Render cited report JSON to Jekyll Markdown"
- "Compare old vs new sample pages"

Avoid asking a fresh cloud task to regenerate the full site until the pilot is reviewed.

## Local To Cloud Handoff Checklist

Before switching machines or starting a cloud task:

1. Commit or push important local changes.
2. Write any decisions into `docs/reprocessing-plan.md` or a relevant issue/PR.
3. Keep API keys out of Git.
4. Tell the cloud task which branch and milestone to work on.
5. Ask the cloud task to read `AGENTS.md` and `docs/reprocessing-plan.md` first.

## Current Site Commands

Build the Jekyll site:

```sh
bundle install
bundle exec jekyll build
```

Run the production build:

```sh
JEKYLL_ENV=production bundle exec jekyll build
```
