# Oannes

**Team flow metrics, inspired by Troy Magennis ideas.**

Connect Jira, Trello, Azure DevOps, GitLab, Linear, Shortcut or CSV — and get interactive charts for throughput, cycle time, lead time, WIP, CFD, aging WIP, flow efficiency, and Monte Carlo forecasting. No spreadsheets. No YAML files. Everything runs locally on your machine.

> **Oannes is a full reengineering of [Seshat](https://github.com/goncalovalverde/seshat)** — the original CLI-based flow metrics tool. Seshat required manual YAML configuration, had no GUI, and produced static charts. Oannes replaces that with a modern web UI, a REST API backend, multi-platform connectors, and persistent project storage.

---

## Architecture & Diagrams

The full architecture is documented in [`ARCHITECTURE.md`](ARCHITECTURE.md). UML diagrams (Mermaid) are in [`docs/diagrams/`](docs/diagrams/):

| Diagram | What it shows |
|---|---|
| [System Components](docs/diagrams/system-component.md) | All components in the Docker container + external platforms |
| [Data Model](docs/diagrams/data-model.md) | ER diagram of all database tables |
| [Sync Flow](docs/diagrams/sync-flow-sequence.md) | How a sync runs from trigger to DB write |
| [Metrics Request](docs/diagrams/metrics-request-sequence.md) | How a metrics page fetches and renders data |
| [Project Creation](docs/diagrams/project-creation-sequence.md) | Wizard → validate → encrypt → save |
| [Work Item Stages](docs/diagrams/work-item-stage-state.md) | Stage state machine (queue → in_flight → review → done) |
| [Encryption Flow](docs/diagrams/encryption-flow.md) | How credentials are encrypted/decrypted |
| [Connector Classes](docs/diagrams/connector-classes.md) | Class hierarchy for all platform connectors |
| [Connector Config Models](docs/diagrams/connector-config-models.md) | Pydantic validation models per connector |

---

## What Changed from Seshat

| | Seshat (original) | Oannes (this project) |
|---|---|---|
| **Interface** | CLI + YAML config files | Web GUI (React) |
| **Backend** | Python scripts | FastAPI REST API |
| **Storage** | No persistence | SQLite (local) |
| **Platforms** | Jira, Trello,GitLab, CSV| Jira, Trello, Azure DevOps, GitLab, CSV |
| **Deployment** | Run manually | Single Docker container |
| **Credentials** | Plaintext config files | AES-encrypted at rest |
| **Forecasting** | Monte Carlo (basic) | Monte Carlo with seed control + vectorised simulation |
| **Charts** | Static PNGs | Interactive Plotly charts |

---

## Docker Images

Images are published to the GitHub Container Registry:

| Tag | Source | Use when |
|---|---|---|
| `stable` | Published on every GitHub Release | Production / daily use |
| `latest` | Built on every push to `main` | Testing the newest changes |

### Run stable (recommended)

```bash
docker run -d \
  -p 8000:8000 \
  -v oannes-data:/app/data \
  --name oannes \
  ghcr.io/goncalovalverde/oannes:stable

open http://localhost:8000
```

An encryption key for connector credentials is **generated automatically** on first run and stored in the volume. This protects against accidental exposure of the database file alone (e.g. a stray backup), but **not** against someone who obtains the entire volume — the key and database would be in the same place. See [Encryption key](#encryption-key) below for the secure setup.

### Run latest

```bash
docker run -d \
  -p 8000:8000 \
  -v oannes-data:/app/data \
  --name oannes \
  ghcr.io/goncalovalverde/oannes:latest

open http://localhost:8000
```

### Options

| Option | Description |
|---|---|
| `-p 8000:8000` | Expose the app on port 8000 |
| `-v oannes-data:/app/data` | Named volume — Docker manages it automatically and data persists across restarts |
| `--name oannes` | Container name for easier management (stop, restart, update) |

> **Bind mount alternative:** If you prefer direct access to the SQLite file on your host, create the directory first then mount it:
> ```bash
> mkdir -p ~/.oannes
> docker run -d -p 8000:8000 -v ~/.oannes:/app/data --name oannes ghcr.io/goncalovalverde/oannes:stable
> ```
> Docker Desktop on macOS does **not** auto-create host directories — omitting the `mkdir` step will cause the mount to silently fail.

### Encryption key

Connector credentials (API tokens, passwords) are encrypted at rest with AES-128. How you manage the key determines the actual security:

| Setup | How | Protection |
|---|---|---|
| **Auto-generated** (default) | Key stored alongside DB in the volume | Protects the `.db` file in isolation only. If someone gets the whole volume, they get both. |
| **Explicit key** (recommended) | You set `OANNES_SECRET_KEY`, store it in a password manager | DB and key are separate — volume exposure alone is not enough to decrypt credentials. |

**Recommended setup:**
```bash
# 1. Generate a key
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# 2. Save it in your password manager (1Password, Bitwarden, etc.)

# 3. Pass it at runtime
docker run -d \
  -p 8000:8000 \
  -v oannes-data:/app/data \
  -e OANNES_SECRET_KEY=<your-key-from-password-manager> \
  --name oannes \
  ghcr.io/goncalovalverde/oannes:stable
```

> ⚠️ Always use the **same key** on every restart — changing it makes stored connector credentials unreadable.

### Updating

```bash
docker pull ghcr.io/goncalovalverde/oannes:stable
docker stop oannes && docker rm oannes
# re-run the docker run command above
```

---

## Data & Privacy

All data stays local. The SQLite database is stored in the `oannes-data` Docker volume (or in `~/.oannes` if you use a bind mount). No telemetry. No cloud sync. Connector credentials are encrypted at rest using AES-128 (Fernet) — set `OANNES_SECRET_KEY` to your own 32-byte base64 key, or one is generated automatically on first run.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS, Plotly.js, TanStack Query |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2, Pydantic v2 |
| Storage | SQLite (single file, no server) |
| Connectors | Jira (v2 + v3), Trello, Azure DevOps, GitLab (python-gitlab), CSV |
| Packaging | Single Docker image (multi-stage build — Node → Python) |
| Testing | Pytest + pytest-cov (≥80% enforced), Vitest + React Testing Library |

---

## Development

### Prerequisites
- Python 3.12+
- Node.js 20+
- Docker (optional)

### Run locally

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
DATA_DIR=../data uvicorn main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev   # → http://localhost:5173 (proxies /api to :8000)
```

### Build & run with Docker

```bash
docker build -t oannes .
docker run -p 8000:8000 -v oannes-data:/app/data oannes
```

### Dev with docker-compose (hot reload)

```bash
docker-compose up
# Backend: http://localhost:8000
# Frontend: http://localhost:5173
```

### Run tests

```bash
# Backend
cd backend && pytest

# Frontend
cd frontend && npm test
```

---

## Supported Platforms

| Platform | Status |
|---|---|
| Jira Cloud (API v3) | ✅ |
| Jira Server / Data Center (API v2) | ✅ |
| Trello | ✅ |
| Azure DevOps | ✅ |
| GitLab | ✅ |
| Linear | 🔜 Coming soon |
| Shortcut | 🔜 Coming soon |
| CSV / Excel | ✅ |

---

## Metrics (Troy Magennis Method)

| Metric | Description |
|---|---|
| **Throughput** | Items completed per week, with trend line |
| **Cycle Time** | Start → Done per item, with 50/85/95th percentile lines |
| **Lead Time** | Created → Done per item |
| **WIP** | Work in progress per stage over time |
| **CFD** | Cumulative Flow Diagram — reveals bottlenecks |
| **Aging WIP** | Items in flight vs historical percentile benchmark |
| **Flow Efficiency** | Active work time vs total elapsed time |
| **Monte Carlo** | Probability-based delivery forecasting |

---

## Acknowledgements

- **[Seshat](https://github.com/goncalovalverde/seshat)** — the original tool this project reimagines.
- **[Troy Magennis](https://www.focusedobjective.com/)** — for the flow metrics and Monte Carlo forecasting methodology.
