# Oannes Architecture & Business Logic

**Last updated: 2026-04-13**

This document describes the core architecture, design decisions, business logic, and key technical patterns in Oannes. **Read this before modifying the codebase.**

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Business Logic: Troy Magennis Flow Metrics](#business-logic-troy-magennis-flow-metrics)
3. [Technical Architecture](#technical-architecture)
4. [Platform Connectors](#platform-connectors)
5. [Data Model](#data-model)
6. [Key Design Decisions](#key-design-decisions)
7. [Testing Strategy](#testing-strategy)
8. [Deployment](#deployment)
9. [UML Diagrams](#uml-diagrams)

---

## System Overview

Oannes is a **flow metrics tool** that connects to issue tracking platforms (Jira, Trello, Azure DevOps, GitLab, CSV) and generates interactive charts showing team throughput, cycle time, lead time, WIP, CFD, aging WIP, flow efficiency, and Monte Carlo forecasting.

**Stack:**
- **Frontend**: React 18 + TypeScript + Vite + Tailwind CSS + Plotly.js
- **Backend**: FastAPI (Python 3.12) + SQLAlchemy 2 + Pydantic v2
- **Storage**: SQLite (single-file, no server)
- **Deployment**: Single Docker container (multi-stage: Node→Python)
- **Scheduling**: APScheduler (background sync jobs)
- **Security**: AES-128 (Fernet) encryption for connector credentials

**User Flow:**
1. User opens web UI (http://localhost:5173)
2. Creates a **Project** (connects to Jira, Trello, etc.)
3. Enters platform credentials (encrypted at rest)
4. Oannes syncs work items automatically or on-demand
5. User views interactive metrics dashboards

---

## Business Logic: Troy Magennis Flow Metrics

Oannes implements the **Troy Magennis forecasting methodology** — a data-driven approach to predicting delivery timelines based on historical flow patterns.

### Core Concepts

Each synced work item has these fields:
- **`created_at`**: When the item was created (defines "lead time" start)
- **`started_at`**: When work began (defines "cycle time" start)
- **`completed_at`**: When marked Done (end of both metrics)
- **`stage`**: Current workflow stage (`queue`, `in_flight`, `review`, `done`)

### Metrics (Calculated in `backend/calculator/flow.py`)

| Metric | Formula | Purpose |
|---|---|---|
| **Throughput** | Items completed per week (avg + trend) | Predict how many items/features per sprint |
| **Cycle Time** | `completed_at - started_at` (days) | How long does work take once started? (50th, 85th, 95th percentiles) |
| **Lead Time** | `completed_at - created_at` (days) | How long from idea to Done? |
| **WIP (Work in Progress)** | Count of items in `in_flight` stage per day | Is the team overloaded? (should be stable) |
| **CFD (Cumulative Flow Diagram)** | Cumulative count by stage over time | Reveals bottlenecks (flat lines = blockage) |
| **Aging WIP** | Days an item has been in flight vs 85th percentile benchmark | Items stuck longer than historical norm |
| **Flow Efficiency** | (Sum of cycle time) / (Lead time) | Ratio of productive work to total elapsed time |
| **Monte Carlo** | Simulate N iterations of random throughput draws | Probabilistic delivery forecast (70%/85%/95% confidence) |

### Key Business Rules

1. **Cycle Time vs Lead Time**: 
   - `cycle_time = completed_at - started_at` (assumes work doesn't start until explicitly begun)
   - `lead_time = completed_at - created_at` (includes wait-in-queue time)
   - If `started_at` is missing, `cycle_time = lead_time`

2. **Stages** (defined by platform mapping):
   - **`queue`**: Created but not started (waiting in backlog)
   - **`in_flight`**: Actively being worked (in progress)
   - **`review`**: In review/QA (before done)
   - **`done`**: Completed/shipped

3. **Percentile Calculation** (85th is standard benchmark):
   - 50th percentile = median (typical case)
   - 85th percentile = optimistic-but-realistic (plan for this)
   - 95th percentile = worst-case planning

4. **Monte Carlo Simulation**:
   - Draw N random samples from historical throughput distribution
   - For each sample, count how many items can be done in X weeks
   - Plot probability distribution: "70% confident we'll deliver 40+ items in 4 weeks"
   - **Vectorised implementation**: Use `np.random.choice()` on entire matrix instead of per-item loops

5. **Aging WIP Alert**:
   - Items in `in_flight` stage longer than the 85th percentile of historical cycle time are flagged
   - Example: "This story has been in progress 15 days, but typical cycle time is 5 days (85th %ile)"

---

## Technical Architecture

### Layering

See [`docs/diagrams/system-component.md`](docs/diagrams/system-component.md) for the full C4 component diagram.

```
┌─────────────────────────────────────────┐
│        Frontend (React/Vite)            │
│  Dashboards, charts, project config UI  │
└────────────────┬────────────────────────┘
                 │ /api/* (HTTP/HTTPS)
┌────────────────▼────────────────────────┐
│  Backend (FastAPI)                      │
│  ├─ API routes (api/*.py)               │
│  ├─ Calculator (calculator/*.py)        │
│  ├─ Connectors (connectors/*.py)        │
│  ├─ Services (services/*.py)            │
│  └─ Scheduler (scheduler.py)            │
└────────────────┬────────────────────────┘
                 │ SQLAlchemy ORM
┌────────────────▼────────────────────────┐
│  Data Layer                             │
│  ├─ Models (models/*.py)                │
│  └─ SQLite (oannes.db via EncryptedJSON)│
└─────────────────────────────────────────┘
```

### API Routes

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/projects/` | POST | Create new project (platform + credentials) |
| `/api/projects/{id}` | GET, PUT, DELETE | View/edit/remove project |
| `/api/projects/{id}/sync` | POST | Trigger manual sync of work items |
| `/api/metrics/{id}/summary` | GET | Summary KPIs (throughput, CT, LT, WIP, etc.) |
| `/api/metrics/{id}/throughput` | GET | Weekly throughput trend |
| `/api/metrics/{id}/cycle-time` | GET | Cycle time histogram + percentiles |
| `/api/metrics/{id}/lead-time` | GET | Lead time histogram + percentiles |
| `/api/metrics/{id}/cfd` | GET | Cumulative flow diagram data |
| `/api/metrics/{id}/wip` | GET | WIP trend over time |
| `/api/metrics/{id}/aging-wip` | GET | Aging WIP alerts |
| `/api/metrics/{id}/flow-efficiency` | GET | Flow efficiency trend |
| `/api/metrics/{id}/monte-carlo` | GET | Monte Carlo forecast simulation |
| `/api/metrics/{id}/raw-data` | GET | Raw items (for inspection) |
| `/api/connectors` | GET | List available connectors |

All endpoints require:
- `project_id` (path param) or filter by current user's projects (future auth feature)
- Optional: `weeks` query param (default: 12 weeks lookback)

### Database Models

See [`docs/diagrams/data-model.md`](docs/diagrams/data-model.md) for the full ERD.

```python
Project(id, name, platform, credentials, sync_frequency, last_synced_at, created_at)
  ├─ platform: 'jira' | 'trello' | 'azure_devops' | 'gitlab' | 'csv'
  └─ credentials: JSON (AES-encrypted)

WorkItem(id, project_id, key, title, created_at, started_at, completed_at, stage, url)
  ├─ stage: 'queue' | 'in_flight' | 'review' | 'done'
  └─ timestamps: datetime (required: created_at, completed_at; optional: started_at)

SyncJob(id, project_id, started_at, completed_at, status, error_message)
  └─ tracks background sync attempts for debugging
```

---

## Platform Connectors

Each platform (Jira, Trello, etc.) has its own connector implementing the `BaseConnector` interface.

### Connector Interface

```python
class BaseConnector(ABC):
    def authenticate(self, credentials: dict) -> bool
        """Verify credentials are valid"""
    
    def get_boards(self) -> list[dict]
        """List available boards/projects/sprints"""
    
    def get_items(self, board_id: str) -> list[WorkItemData]
        """Fetch all work items from board"""
```

### WorkItemData (Standardized Output)

```python
@dataclass
class WorkItemData:
    key: str              # Unique ID (e.g., "PROJ-123")
    title: str            # Display name
    url: str              # Link to item in platform
    created_at: datetime  # When item was created
    started_at: Optional[datetime]  # When work started
    completed_at: Optional[datetime]  # When item was marked done
    stage: str            # 'queue' | 'in_flight' | 'review' | 'done'
```

### Platform-Specific Mappings

| Platform | Board Model | Stage Mapping |
|---|---|---|
| **Jira** | Project → Sprints | Status field → stage |
| **Trello** | Board → Lists | List name → stage |
| **Azure DevOps** | Project → Iterations | State field → stage |
| **GitLab** | Project → Issues | Labels/state → stage |
| **CSV** | File upload | Columns → fields |

### Connector Implementation Pattern

Each connector:
1. Takes platform credentials (API key, workspace ID, etc.)
2. Queries platform API or parses CSV
3. Maps platform's "stages" to Oannes's 4 stages
4. Extracts timestamps (or uses heuristics if missing)
5. Returns list of `WorkItemData` in standard format

**Example: Jira Connector**
- Auth: API token
- Stages: `map Jira status (To Do, In Progress, In Review, Done) → (queue, in_flight, review, done)`
- Timestamps: Use Jira changelog to infer `started_at` (first transition to In Progress)

---

## Data Model

### Datetime Handling

- **All times are UTC** (no timezone conversion at sync time)
- **Pandas datetime type**: `datetime64[ns]`
- **Missing times**:
  - `started_at = None` → treat as "not started yet" (exclude from cycle time)
  - `completed_at = None` → exclude from completed metrics (WIP only)

### Credential Storage

Credentials are stored encrypted using **Fernet (AES-128-CBC)**:
1. On create: `plaintext → encrypt(plaintext, key) → store base64 blob`
2. On use: `load blob → decrypt(blob, key) → plaintext`
3. **Key source**: Environment variable `OANNES_SECRET_KEY` (32-byte base64) or auto-generated

See `backend/utils/crypto.py` for implementation. **Never log credentials.**

### Time Window (lookback)

Metrics endpoints default to **last 12 weeks** of data. Query param `weeks=N` overrides.
- Why 12 weeks? Typical sprint cycle (2-3 weeks × 4-5 sprints) + buffer for trend visibility
- Metrics are *windowed*: only items with `created_at >= (now - weeks*7 days)` are included
- CFD and WIP trend lines may include older data for context

---

## Key Design Decisions

### 1. Single Docker Container (Not Microservices)

**Decision**: FastAPI + React frontend compiled into a single Docker image.

**Why**:
- No coordination complexity (Kubernetes, load balancing)
- Easier credential management (single `OANNES_SECRET_KEY`)
- Runs on a laptop or small server
- Faster local development (docker-compose hot reload)
- Smaller operational footprint

**Trade-off**: Less horizontal scalability, but Oannes is single-user/small-team focused.

### 2. SQLite (Not PostgreSQL/MySQL)

**Decision**: File-based SQLite database.

**Why**:
- Zero setup (no separate database server)
- Single-user/team tool (no concurrent write conflicts)
- Easy backups (just copy file)
- Runs on any machine (laptop, NAS, VPS)
- Sufficient for 10K+ work items per project

**Trade-off**: Not suitable for massive scale (>100K items), but that's not the use case.

### 3. APScheduler (Background Sync)

**Decision**: Background job scheduler for automatic syncs.

**Why**:
- Keep data fresh without user intervention
- No external service dependency (vs. cron on host)
- Runs inside the same container
- Can pause/resume in UI (future feature)

**Trade-off**: If container restarts, scheduled jobs restart too. Fine for small teams.

### 4. Encryption at Rest (Not End-to-End)

**Decision**: Credentials encrypted in database, but API/frontend use plaintext (HTTPS only).

**Why**:
- Backend needs plaintext to call platform APIs
- No user-to-user sharing (single user or small team)
- Protects accidental data exposure (DB dump)

**Trade-off**: If backend is compromised, credentials are accessible. Mitigation: HTTPS only, rotate API tokens regularly.

### 5. Savepoint-Based Test Isolation (Not Mocks)

**Decision**: Real database (in-memory SQLite) for integration tests, with savepoint rollback.

**Why**:
- Tests exercise real ORM behavior, not mocks
- Catches off-by-one errors in queries
- Ensures database migrations work
- Faster than creating/dropping tables per test

**How**: Each test runs inside a savepoint. After each `db.commit()`, a new savepoint begins. On teardown, the entire transaction rolls back.

See `backend/tests/conftest.py` for implementation.

### 6. Lazy Imports in Scheduler

**Decision**: `scheduler.py` imports services/models inside functions, not at module level.

**Why**:
- Avoids circular imports (scheduler imports database, database imports models)
- Allows testing without full app context

**Trade-off**: Must remember to patch the *source* module (`database.SessionLocal`, not `scheduler.SessionLocal`).

### 7. Vectorised Monte Carlo Simulation

**Decision**: Use NumPy matrix operations instead of per-item loops.

**Why**:
- 100x faster for 10K+ items
- Enables large confidence intervals (N=10K simulations)
- Scales well

See `backend/calculator/monte_carlo.py::simulate_how_many()` for details.

### 8. Implicit Workflow Stage Inference

**Decision**: If `started_at` is missing, infer it from the item's stage history.

**Why**:
- Not all platforms record explicit "started" timestamps
- Can be inferred: "first transition to In Progress"
- Improves data completeness without platform-specific hacks

See `backend/connectors/jira.py` for example.

---

## Testing Strategy

### Coverage Target: ≥80%

**Backend**: Pytest + pytest-cov
- Unit tests (calculator, utils)
- Integration tests (API endpoints, database)
- Mock-based tests (connectors, scheduler)
- **Threshold**: `--cov-fail-under=80` in `pytest.ini`
- **Excludes**: Network connector stubs (jira, trello, etc. are 0% since they're not fully implemented)

**Frontend**: Vitest + React Testing Library
- Component tests (ProjectWizard, charts)
- Hook tests (useMetrics, useSync)
- **No E2E tests yet** (future: Playwright)

### Test Isolation

**Key Pattern: Savepoints**
```python
# conftest.py
@pytest.fixture
def db():
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    
    @event.listens_for(Session, 'after_transaction_end')
    def restart_savepoint(session, transaction):
        if not session.is_active:
            session.begin_nested()
    
    yield session
    session.rollback()
    transaction.rollback()
    connection.close()
```

This ensures:
1. Each test starts with fresh data (no cross-pollution)
2. Tests can commit without affecting others
3. Fast (no table drops/recreates)

### Bug Prevention

**No Flaky Tests**:
- No `time.sleep()` waits (use mocks/fixtures instead)
- No real API calls (mock all connectors)
- Deterministic random seeds (`seed=42` in Monte Carlo tests)

**Mutation Testing**:
- `compute_cycle_and_lead()` now does `df = df.copy()` to prevent in-place mutation
- Proved by `TestComputeCycleAndLeadNoMutation` tests

---

## Deployment

### Docker

**Single-stage build**:
1. Build React frontend (`npm run build` → `dist/`)
2. Install Python deps
3. Copy frontend build to `/app/static/`
4. Serve React from FastAPI (static files)

**Run**:
```bash
docker build -t oannes .
docker run -p 8000:8000 -v ~/.oannes:/app/data oannes
```

### docker-compose (Development)

```bash
docker-compose up
# Backend: http://localhost:8000
# Frontend: http://localhost:5173 (hot reload)
```

### Environment Variables

| Var | Purpose | Default |
|---|---|---|
| `DATA_DIR` | Where SQLite DB is stored | `/app/data` |
| `OANNES_SECRET_KEY` | AES encryption key (base64) | Auto-generated (not secure for prod) |
| `PYTHONUNBUFFERED` | Unbuffered output (Docker) | `1` |

### Production Notes (Future)

- Use persistent volume for `DATA_DIR`
- Set `OANNES_SECRET_KEY` to a stable, strong value (keep in secrets manager)
- Enable HTTPS (reverse proxy like nginx)
- Add authentication (JWT, OAuth2) — currently assumes single user
- Back up SQLite file regularly

---

## Common Pitfalls & How to Avoid Them

### 1. Mutating Input DataFrames

**Problem**: `compute_cycle_and_lead(df)` used to modify `df` in-place.
**Solution**: Always do `df = df.copy()` at function entry if you'll assign to columns.
**Test**: `TestComputeCycleAndLeadNoMutation`

### 2. Comparing Empty Series with Floats

**Problem**: Empty `pd.Series` with dtype `datetime64[ns]` can't be compared to a float.
**Solution**: Check `if not series.empty:` before `.apply()` or comparison.
**Test**: `TestEmptyDataFrameGuards`

### 3. Test Isolation with Mutable Singletons

**Problem**: `crypto.py` has a module-level `_fernet` singleton. If one test sets a bad key, all subsequent tests fail.
**Solution**: Use `monkeypatch.setenv()` (not `os.environ[]=`) and reset the singleton in an `autouse` fixture.
**Test**: `test_crypto.py::isolated_fernet`

### 4. Patching Lazy Imports

**Problem**: `scheduler.py` does `from database import SessionLocal` inside functions. Patching `scheduler.SessionLocal` fails.
**Solution**: Patch the source module: `patch('database.SessionLocal', ...)`.
**Test**: `test_scheduler.py`

### 5. Non-Deterministic Random Behavior

**Problem**: Monte Carlo tests can flake if they use `np.random` without a seed.
**Solution**: Always pass `seed=42` to functions that randomize.
**Test**: `test_monte_carlo.py::test_simulate_when_done_with_seed`

### 6. Missing Data Handling

**Problem**: If platform doesn't provide `started_at`, cycle time is undefined.
**Solution**: Infer from stage history or treat as missing. Never assume.
**Code**: Connectors implement heuristics; calculator skips null values.

---

## Future Improvements

1. **User Authentication** (JWT + OAuth2) — currently single-user
2. **Playwright E2E Tests** — full flow testing (create project → sync → view metrics)
3. **Linear & Shortcut Connectors** — implement stubbed connectors
4. **Webhooks** — platform-triggered syncs (Jira webhooks, GitLab events)
5. **Multi-tenant** — support multiple teams/accounts
6. **Performance** — add query caching, async DB drivers for 100K+ items
7. **Export** — CSV/PDF reports for presentations

---

## Quick Reference: Key Files

| File | Purpose |
|---|---|
| `backend/calculator/flow.py` | All metric calculations (throughput, CT, LT, CFD, WIP, etc.) |
| `backend/calculator/monte_carlo.py` | Probabilistic forecasting |
| `backend/api/metrics.py` | GET endpoints for all metrics (calls calculator) |
| `backend/connectors/base.py` | Abstract connector interface |
| `backend/connectors/*.py` | Platform-specific implementations (Jira, Trello, etc.) |
| `backend/services/sync_service.py` | Bulk insert/update of work items |
| `backend/scheduler.py` | Background job for periodic syncs |
| `backend/utils/crypto.py` | Credential encryption/decryption |
| `backend/tests/conftest.py` | Shared fixtures (database, savepoint isolation) |
| `frontend/src/api/hooks/useMetrics.ts` | React hooks for fetching metrics |
| `frontend/src/components/charts/` | Plotly chart components |
| `frontend/src/components/config/ProjectWizard.tsx` | Multi-step project setup UI |

---

## Questions?

- **Architecture**: See this file
- **Specific implementation**: Read the docstrings in `backend/calculator/flow.py` and `backend/connectors/base.py`
- **Testing**: See `backend/tests/conftest.py` and test files for patterns
- **Business logic**: See "Business Logic: Troy Magennis Flow Metrics" section above

---

## UML Diagrams

All diagrams are stored in [`docs/diagrams/`](docs/diagrams/) as Mermaid source files. They render natively in GitHub, GitLab, and VS Code with the Mermaid extension.

| Diagram | File | Type | What it shows |
|---|---|---|---|
| System Components | [system-component.md](docs/diagrams/system-component.md) | C4 Component | Full component map: browser, Docker container, SQLite, external platforms |
| Data Model (ERD) | [data-model.md](docs/diagrams/data-model.md) | ER Diagram | All DB tables and their relationships |
| Connector Classes | [connector-classes.md](docs/diagrams/connector-classes.md) | Class Diagram | `BaseConnector` hierarchy — Jira, Trello, Azure, GitLab, CSV, Linear, Shortcut |
| Connector Config Models | [connector-config-models.md](docs/diagrams/connector-config-models.md) | Class Diagram | Pydantic validation models for all connector types |
| Sync Flow | [sync-flow-sequence.md](docs/diagrams/sync-flow-sequence.md) | Sequence Diagram | User-triggered + scheduled sync: API → SyncService → Connector → DB |
| Metrics Request | [metrics-request-sequence.md](docs/diagrams/metrics-request-sequence.md) | Sequence Diagram | Metrics endpoint → Calculator → Plotly chart render |
| Project Creation | [project-creation-sequence.md](docs/diagrams/project-creation-sequence.md) | Sequence Diagram | Wizard → validate → encrypt → save → first sync |
| Work Item Stages | [work-item-stage-state.md](docs/diagrams/work-item-stage-state.md) | State Machine | Stage transitions: queue → in_flight → review → done, with metric annotations |
| Credential Encryption | [encryption-flow.md](docs/diagrams/encryption-flow.md) | Sequence Diagram | Key loading (env var / auto-generate) and encrypt/decrypt lifecycle |

> **Keep diagrams in sync.** If you change a model, connector, or API route, update the relevant diagram(s) and note the change in your commit message.

---

**Last updated**: 2026-04-29
