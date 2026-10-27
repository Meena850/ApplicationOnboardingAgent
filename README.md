# Application Onboarding Agent

Full-stack app: React + TypeScript + Material UI + React Router (frontend), Python FastAPI (backend).

## Structure

```
application-onboarding-agent/
  backend/
    app/
      api/         REST routes
      services/    business logic
      agents/      AI agents (BaseAgent, OnboardingAgent)
      analyzers/   application analyzers
      models/      Pydantic models
      core/        settings (env vars) and logging
      main.py
    requirements.txt, .env.example
  frontend/
    src/ pages/ components/ services/ diagrams/
  data/            input data
  reports/         generated reports (JSON)
```

Flow: `api -> services -> agents -> analyzers -> models`.

## Run

Backend (PowerShell):
```
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --port 8000
```
Docs: http://localhost:8000/docs

Frontend:
```
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```
App: http://localhost:5173

## API

- `GET /api/health`
- `POST /api/onboardings` `{ "name": "...", "repo_url": "..." }`
- `GET /api/onboardings`
- `GET /api/onboardings/{id}`
- `POST /api/repositories/ingest` `{ "source": "<git url or local path>", "branch": "main" }` – clone or load a repo, store metadata
- `POST /api/repositories/analyze` `{ "base": {source, branch}, "enhancement": {source, branch} }` – ingest both repos
- `GET /api/repositories`, `GET /api/repositories/{id}`
- `POST /api/discovery` `{ "path": "..." }` or `{ "repositoryId": "..." }` – source code inventory (React, .NET, Razor) → `reports/discovery-<app>.json`
- `POST /api/architecture` (same body) – deterministic Architecture Analysis Agent (no AI): `moduleMap`, `routeMap`, `apiMap`, `dependencyMap` → `reports/architecture-<app>.json`
- `POST /api/features` (same body) – Feature Understanding Agent (Azure OpenAI): business capabilities, features, user workflows, functional modules, each with reasoning and a confidence score → `reports/features-<app>.json`. Requires `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT` in `backend/.env` (returns 503 if missing, 502 on model errors). Module names returned by the model are validated against the analyzed data; unknown names are removed and reported in `warnings`.
- `POST /api/comparison` `{ "base": {"path"|"repositoryId"}, "enhancement": {"path"|"repositoryId"} }` – deterministic Repository Comparison Agent (no AI). Compares modules, routes, APIs, services and database entities (EF Core `DbSet`/annotated classes, model classes, SQL tables) and returns `missingComponents` and an ordered `integrationCandidates` list (`add`/`merge`, risk, dependencies, conflicts) → `reports/comparison-<base>-vs-<enhancement>.json`
- `POST /api/recommendation` (same body as comparison) – deterministic Integration Recommendation Agent: the top 3 locations in the base where the enhancement should be integrated, each with `filePath`, `reason`, `confidence` (0-100) and `evidence` → `reports/recommendation-<base>-vs-<enhancement>.json`
- `POST /api/impact` `{ "base": {...}, "enhancement": {...}, "topN": null }` – deterministic Impact Analysis Agent: walks the base's dependency graph from the recommended integration points and returns affected components, routes, APIs, controllers and services, each categorized Low / Medium / High with reasons, plus a Markdown `summaryReport` → `reports/impact-<base>-vs-<enhancement>.json` and `.md`. Scoring: conflicting change 50, additive 25, wiring-only 10, newly added 10; dependents get 60% / 35% / 20% at 1 / 2 / 3 hops (+ fan-in bonus). High ≥ 50, Medium ≥ 20.
- `POST /api/plan` (same body as `/api/impact`) – deterministic Implementation Planning Agent: 3 phases (1 foundation: data/services/wiring, 2 feature surface: controllers/pages/routes, 3 verification). Each task has description, files involved, dependencies and validation steps → `reports/plan-<base>-vs-<enhancement>.json` and `.md`.
- `POST /api/diagrams` `{ "repositoryId": "..." }` or `{ "path": "..." }` – deterministic Mermaid generation from the architecture analysis: `moduleDiagram`, `dependencyDiagram` (injections, DI registrations, top packages) and `apiFlowDiagram` (client call → endpoint → controller action → services; falls back to route → handler → services/view for MVC apps) → `reports/diagrams-<app>.json` and `.md`. The UI page `/diagrams` renders them with Mermaid.
- UI `/dashboard` – enterprise dashboard (Material UI, Fluent-inspired theme in `frontend/src/theme.ts`, responsive grid). Pick a base and an enhancement repository (or local paths) and click **Run analysis**; it calls architecture, features, comparison, recommendation and plan in parallel and shows Repository Status, Architecture Analysis, Feature Analysis, Comparison Results, Recommendations and Implementation Plan. Each card shows its own error (e.g. Feature Analysis needs Azure OpenAI configured).

Repository ingestion uses GitPython (requires `git` installed). Clones go to `data/clones/`, metadata to `data/repositories/` and `data/analyses/`. Errors (bad path, not a git repo, clone failure, unknown branch) return 4xx with a readable `detail`. UI: http://localhost:5173/repositories

## Configuration

Backend `.env`: `APP_NAME`, `ENVIRONMENT`, `LOG_LEVEL`, `CORS_ORIGINS`, `DATA_DIR`, `REPORTS_DIR`, `LLM_API_KEY`.
Frontend `.env`: `VITE_API_URL`.
