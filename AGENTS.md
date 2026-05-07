# Agents Guide For Lettuce Eat

This repo is a FastAPI backend for Lettuce Eat.

## Product Objective

Build the fastest way to log calories and macros from a meal photo.

Success metric: `photo -> corrected macros -> logged meal` in under 10 seconds.

Product principle: **Fast estimate -> fast correction -> logged meal**.

The MVP validates the interaction loop, not perfect nutrition accuracy.

## Source Of Truth

Before implementing staged work, read:

- `docs/plans.md`
- `docs/meal-flow-api.md`

The PDF in `docs/` is a shareable snapshot. The Markdown docs are the implementation source of truth.

## Scope Guardrails

Do not add these during MVP unless the user explicitly changes scope:

- Barcode scanning
- Nutrition database integration
- Restaurant database integration
- Apple Health
- Social features
- Coaching

## Implementation Rules

- Implement one stage at a time.
- Follow the implementation steps and acceptance criteria for that stage in `docs/plans.md`.
- Keep each stage separately testable and separately committable.
- Update documentation with each stage when behavior or contracts change.
- Preserve the existing `/api/v1/nutrition/analyze` endpoint until the plan explicitly retires or deprecates it.
- Do not implement corrections or logging while working on analysis-only stages.
- Do not write image files directly from routes; use an image storage service abstraction.

## API Contract Rules

The target analysis response is the v1 schema in `docs/meal-flow-api.md`.

Important invariants:

- `analysis_id` identifies a persisted draft analysis.
- `version` is `v1`.
- `items[].id` stays stable across analyze, correction, and log steps.
- `meal_totals` uses `calories`, `protein_g`, `carbs_g`, and `fat_g`.
- `suggestions[].preview_delta` uses the same macro field names.

## Dataset Requirement

Preserve the trail needed for future training/evaluation:

- Original image or storage key
- Image metadata, including provider, key, content type, byte size, and SHA-256
- AI raw response
- Validated JSON
- User corrections
- Final saved meal

Do not add training/evaluation use of this data until privacy, consent, retention, and deletion policy exists.


## Documentation Standards

- Add or update Python docstrings for every new or materially changed function, method, class, service, schema, and route handler.
- Docstrings should explain purpose, behavior, important side effects, and why the object exists in the meal flow.
- Update Markdown docs whenever API behavior, data contracts, workflow assumptions, testing strategy, or storage behavior changes.
- Do not rely on chat history for implementation context; preserve important decisions in repo docs.

## Testing Rules

- Default tests must be deterministic and should not call OpenAI.
- Use fake AI services in automated tests.
- Real-image testing is manual or opt-in integration testing only.
- Run `pytest` and `ruff check .` before reporting implementation complete.

## Commit Guidance

Commits must explain both what changed and why it changed. Prefer commits that map to the staged plan, for example:

- `docs: define meal logging API flow, v1 client schema, and dataset record`
- `schemas: add meal analysis response, correction, logged meal, and dataset models`
- `ai: return v1 food-level meal estimates and capture raw responses`
- `db: persist draft meal analyses and dataset fields`
- `api: add photo analysis meal endpoint with v1 response`
- `corrections: add deterministic macro adjustment service`
- `api: add meal correction endpoint and correction history`
- `api: add logged meal endpoint with dataset linkage`
