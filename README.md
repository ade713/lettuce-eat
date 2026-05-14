# Lettuce Eat

FastAPI backend for uploading a meal or food photo, sending it to an AI vision model, and returning estimated nutrition values. Analyses are stored in Postgres.

Nutrition from a photo is an estimate. The API returns confidence and assumptions so clients can show the result honestly.

## Implementation plan

The staged MVP implementation plan lives in:

- `docs/plans.md`
- `docs/meal-flow-api.md`
- `AGENTS.md`

The PDF in `docs/` is a shareable snapshot, while the Markdown files are the source of truth for implementation.

## Stack

- FastAPI
- Postgres with SQLAlchemy async
- OpenAI Responses API for image analysis
- Pytest with mocked AI service tests

## Run locally

```bash
cp .env.example .env
docker compose up -d postgres
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Open `http://localhost:8000/docs`.

## Run tests locally

Install the development dependencies first if you have not already:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run the test suite:

```bash
pytest
```

Run lint checks:

```bash
ruff check .
```

The tests use an in-memory SQLite database and a mocked AI service, so they do not require Postgres, Docker, or an OpenAI API key.

## Main endpoint

```bash
curl -X POST "http://localhost:8000/api/v1/nutrition/analyze" \
  -F "image=@/path/to/meal.jpg" \
  -F "notes=Lunch portion, restaurant plate"
```

The response includes calories, macros, likely ingredients, assumptions, confidence, and a persisted analysis ID.

## Environment

- `DATABASE_URL`: async SQLAlchemy URL, for example `postgresql+asyncpg://postgres:postgres@localhost:5433/meal_nutrition`
- `OPENAI_API_KEY`: API key for the AI provider
- `OPENAI_MODEL`: model used for image analysis
- `MAX_UPLOAD_MB`: maximum accepted upload size
- `LOCAL_STORAGE_ROOT`: local directory for stored meal images, defaulting to `storage`

## API notes

OpenAI's vision-capable Responses API accepts images as URLs, file IDs, or base64 data URLs. This backend uses a base64 data URL because mobile clients commonly upload image bytes directly. Structured JSON output is requested so the API can validate and store a predictable nutrition payload.
