# Lettuce Eat Implementation Plans

## Plan 1: Server-Owned Correction Loop

### Objective

Build the fastest backend path for `photo -> corrected macros -> logged meal` in under 10 seconds.

Product principle: **Fast estimate -> fast correction -> logged meal**.

The MVP validates the interaction loop, not perfect nutrition accuracy.

### MVP Scope

Included:

- Photo meal capture
- AI food detection
- AI macro estimation
- Quick correction support
- Logged meal storage
- Dataset preservation for later training and evaluation

Not included in MVP:

- Barcode scanning
- Nutrition database integration
- Restaurant database integration
- Apple Health
- Social features
- Coaching

### Locked Decisions

- Original image storage: store files locally for MVP behind an image storage abstraction so S3 or another blob store can replace it later.
- Existing endpoint: keep `/api/v1/nutrition/analyze` during MVP so changes can be introduced step by step.
- First implementation stage: documentation first, then schema-only code, then endpoint behavior.
- Normal automated tests stay mocked and deterministic. Real-image testing is manual/integration-only and outside CI.

### Dataset Requirement

Each completed flow must preserve the full trail needed for future evaluation:

- Original image or durable storage key
- Image metadata: storage provider, storage key, content type, byte size, and SHA-256 hash
- AI raw response exactly as returned by the provider
- Validated JSON using the v1 client response schema
- User corrections, including values and timestamps
- Final saved meal with corrected macros and links back to the original analysis

Do not use this data for training or evaluation until privacy, consent, retention, and deletion policies exist.

### Image Storage Direction

Introduce an `ImageStorageService` abstraction before routes write images.

For MVP, implement local storage:

- `storage_provider`: `local`
- `image_storage_key`: stable relative key such as `meal-images/2026/05/<uuid>.jpg`
- `LOCAL_STORAGE_ROOT`: configurable local root, defaulting to `storage`
- `image_content_type`: upload MIME type
- `image_size_bytes`: uploaded byte count
- `image_sha256`: hash of original bytes

Future S3/blob storage should implement the same service interface without changing API handlers.

### Documentation And Commit Standards

Every implementation stage must document the work as it is done:

- Add or update Python docstrings for every new or materially changed function, method, class, service, schema, and route handler.
- Keep docstrings concise and focused on purpose, behavior, important side effects, and why the object exists in the meal flow.
- Update Markdown docs when public API behavior, data contracts, workflow assumptions, testing strategy, or storage behavior changes.
- Write commits that explain both what changed and why it changed, so future engineers and coding agents can continue the work without relying on chat history.
- Keep commits aligned to the current stage and avoid mixing unrelated implementation stages in one commit.


### Stages

#### Stage 0: Document The Target API Contract

Purpose: lock the backend shape before changing runtime code.

Implementation steps:

1. Create or update `docs/plans.md` with the staged implementation plan, locked decisions, dataset requirements, and commit sequence.
2. Create or update `docs/meal-flow-api.md` with the target endpoint sequence, v1 response schema, response rules, image storage contract, and manual real-image test flow.
3. Create or update `AGENTS.md` so future agents know to follow `docs/plans.md` and `docs/meal-flow-api.md` before implementing.
4. Regenerate the shareable PDF only after the Markdown source is updated.
5. Do not change app runtime code, schemas, models, routes, or tests in this stage.

Acceptance criteria:

- `docs/plans.md`, `docs/meal-flow-api.md`, `AGENTS.md`, and the plan PDF exist.
- The docs state the locked decisions: local image storage behind an abstraction, keep `/api/v1/nutrition/analyze` during migration, docs-first sequencing, mocked tests by default, and manual real-image testing outside CI.
- The v1 client response schema appears in `docs/meal-flow-api.md`.
- `AGENTS.md` points agents to the Markdown docs as the implementation source of truth.
- `git diff` shows documentation-only changes.
- The stage commit explains that this creates the durable implementation contract and why docs-first sequencing matters.

#### Stage 1: Add New Schemas Without New Behavior

Purpose: introduce the data model safely before wiring endpoints.

Implementation steps:

1. Add Pydantic schemas for the v1 analysis response: `MealAnalysisResponse`, `MealItem`, `MacroEstimate`, `MacroDelta`, `Uncertainty`, `Assumption`, and `Suggestion`.
2. Add Pydantic schemas for future correction requests/responses, logged meal responses, and dataset metadata without connecting them to endpoints yet: `MealCorrectionRequest`, `CorrectionEvent`, `MealCorrectionResponse`, `ImageStorageMetadata`, `MealDatasetMetadata`, and `LoggedMealResponse`.
3. Preserve the existing `/api/v1/nutrition/analyze` response and tests unless compatibility aliases are needed.
4. Add schema-focused tests for valid and invalid payloads.
5. Update docs only if schema names or validation rules differ from the contract.

Acceptance criteria:

- Existing API behavior remains unchanged.
- Existing endpoint tests still pass.
- New schema tests cover required top-level v1 fields, item IDs, grams, macros, confidence ranges, suggestions, preview deltas, correction payloads, correction history, image storage metadata, dataset metadata, and logged meal linkage.
- `pytest` and `ruff check .` pass.
- New or changed Python objects have purpose-focused docstrings, and the stage commit explains what changed and why.

#### Stage 2: Extend AI Output Shape

Purpose: make AI analysis produce the v1 food-level response shape.

Implementation steps:

1. Add a new AI service method or internal parsing path that validates provider output into the v1 schema.
2. Update the OpenAI JSON schema and prompt to request detected items, estimated grams, item macro estimates, uncertainty, assumptions, meal totals, overall confidence, and suggestions.
3. Capture provider raw response separately from the validated v1 JSON in service-level return objects or internal structures.
4. Update fake AI test data to include deterministic v1 meal analysis output.
5. Keep endpoint behavior stable unless this stage explicitly introduces an internal-only service test.

Acceptance criteria:

- Mocked AI output validates into the new schemas.
- Invalid or incomplete AI output fails validation in tests.
- Provider raw response and validated JSON are both representable by the service layer.
- No correction or logging endpoint is added in this stage.
- `pytest` and `ruff check .` pass.
- New or changed Python objects have purpose-focused docstrings, and the stage commit explains what changed and why.

#### Stage 3: Add Draft Meal Storage

Purpose: persist analysis drafts separately from final logged meals and preserve dataset inputs.

Implementation steps:

1. Add a new draft meal model/table rather than expanding the existing `NutritionAnalysis` model into the full meal-flow domain.
2. Add fields for status, image storage metadata, validated v1 response JSON, detected items JSON, original meal totals, current corrected totals, correction history, and AI raw response.
3. Add local image storage metadata fields needed for the future `ImageStorageService` integration: provider, key, content type, byte size, and SHA-256.
4. Keep existing endpoint behavior working during this storage addition.
5. Add model/persistence tests using the current in-memory test database pattern.

Acceptance criteria:

- Draft records can be created and retrieved in tests.
- Image metadata, raw AI response, validated v1 JSON, original totals, current totals, and correction history persist correctly.
- Existing `/api/v1/nutrition/analyze` tests still pass.
- `pytest` and `ruff check .` pass.
- New or changed Python objects have purpose-focused docstrings, and the stage commit explains what changed and why.

#### Stage 4: Add `POST /api/v1/meals/analyze-photo`

Purpose: introduce the new MVP entrypoint.

Implementation steps:

1. Add an `ImageStorageService` abstraction and local implementation before routes write uploaded files.
2. Add configuration for local storage root, defaulting to `storage`.
3. Add the `/api/v1/meals/analyze-photo` endpoint in a meal-focused router.
4. Validate upload content type, empty files, and max upload size using behavior consistent with the existing nutrition endpoint.
5. Store the original image through `ImageStorageService`, run AI once, persist raw AI response, validated v1 JSON, and a draft meal analysis.
6. Return the canonical v1 client response schema.
7. Keep `/api/v1/nutrition/analyze` available during transition.

Acceptance criteria:

- Valid mocked image returns a v1 draft analysis response.
- Unsupported upload returns `415`.
- Empty image returns `400`.
- Oversized image returns `413`.
- Draft record and dataset fields are persisted.
- Local image metadata includes storage provider, key, content type, byte size, and SHA-256.
- Automated tests do not call OpenAI.
- Manual real-image curl instructions are documented or updated.
- `pytest` and `ruff check .` pass.
- New or changed Python objects have purpose-focused docstrings, and the stage commit explains what changed and why.

#### Stage 5: Add Deterministic Correction Engine

Purpose: make corrections instant and server-owned without another AI call.

Implementation steps:

1. Add a pure Python correction service that accepts the draft v1 analysis and a correction request.
2. Support MVP controls for portion scale, composition ratio such as rice vs meat, oil level, and suggestion-based corrections using `preview_delta` where applicable.
3. Recalculate item macros and meal totals deterministically.
4. Append each correction request and resulting totals to correction history.
5. Keep correction logic independent from FastAPI routes so it is easy to unit test.

Acceptance criteria:

- Correction math has focused unit tests.
- Tests prove corrections do not call the AI service.
- Corrected totals and correction history persist when connected to storage in later stages.
- Real-image manual test instructions mention that corrections should feel instant once endpoints exist.
- `pytest` and `ruff check .` pass.
- New or changed Python objects have purpose-focused docstrings, and the stage commit explains what changed and why.

#### Stage 6: Add `PATCH /api/v1/meals/{analysis_id}/corrections`

Purpose: expose the correction loop to the UI.

Implementation steps:

1. Add the correction endpoint to the meal router.
2. Accept correction payloads targeting stable item IDs and, where applicable, suggestion IDs from the v1 response.
3. Load the draft analysis and reject missing records with `404`.
4. Reject logged records unless the plan is explicitly changed to allow post-log corrections.
5. Apply the deterministic correction engine, persist updated draft values, and append correction history.
6. Return updated items, meal totals, confidence, and suggestions where appropriate.

Acceptance criteria:

- Valid correction updates macros and persists correction history.
- Missing analysis returns `404`.
- Logged meal correction returns the chosen conflict/error status, expected default `409`.
- Invalid correction values return `422`.
- No AI call occurs during correction.
- `pytest` and `ruff check .` pass.
- New or changed Python objects have purpose-focused docstrings, and the stage commit explains what changed and why.

#### Stage 7: Add `POST /api/v1/meals/{analysis_id}/log`

Purpose: complete `photo -> corrected macros -> logged meal`.

Implementation steps:

1. Add the log endpoint to the meal router.
2. Load the draft analysis and reject missing records with `404`.
3. Prevent duplicate logging by default, returning `409` for already logged drafts.
4. Store final macros, final items, correction history snapshot, and dataset linkage to original image metadata, AI raw response, and validated v1 JSON.
5. Mark the draft as logged or create a separate logged meal record, using the storage model chosen in Stage 3.
6. Return the logged meal ID and final macros.

Acceptance criteria:

- Logging a draft succeeds.
- Logging an already logged draft returns `409`.
- Missing analysis returns `404`.
- Logged meal stores final corrected macros and complete dataset linkage.
- Manual real-image flow can validate photo -> corrected macros -> logged meal under 10 seconds.
- `pytest` and `ruff check .` pass.
- New or changed Python objects have purpose-focused docstrings, and the stage commit explains what changed and why.

#### Stage 8: Retire Or Deprecate Old Nutrition Endpoint

Purpose: simplify the API surface after the new meal flow is working.

Implementation steps:

1. Review usage and tests for `/api/v1/nutrition/analyze` after the meal flow is complete.
2. Decide whether the endpoint remains legacy, maps conceptually to the new flow, or is removed before production.
3. If legacy remains, document whether it writes dataset fields or is excluded from the future training/evaluation dataset.
4. Update README, API docs, tests, and `AGENTS.md` if the migration policy changes.
5. Remove or adjust legacy tests only when the endpoint decision is explicit.

Acceptance criteria:

- Legacy endpoint behavior is clearly documented.
- If kept, legacy endpoint tests still pass.
- If removed, tests focus only on the new meal flow and no docs advertise the removed endpoint.
- Dataset inclusion/exclusion for legacy analyses is explicit.
- `pytest` and `ruff check .` pass.
- New or changed Python objects have purpose-focused docstrings, and the stage commit explains what changed and why.

### Recommended Commit Structure

1. `docs: define meal logging API flow, v1 client schema, and dataset record`
2. `schemas: add meal analysis response, correction, logged meal, and dataset models`
3. `ai: return v1 food-level meal estimates and capture raw responses`
4. `db: persist draft meal analyses and dataset fields`
5. `api: add photo analysis meal endpoint with v1 response`
6. `corrections: add deterministic macro adjustment service`
7. `api: add meal correction endpoint and correction history`
8. `api: add logged meal endpoint with dataset linkage`
9. `tests: document and add optional real-image smoke test workflow`
10. `docs: document full MVP meal logging and dataset flow`
