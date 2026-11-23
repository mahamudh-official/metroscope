# MetroScope

> **Automated, US-Focused Global News Aggregation & Distribution Platform**

MetroScope is an automated news discovery engine engineered to aggregate real-time news intelligence from the Webz.io News API, normalize article metadata in PostgreSQL, and publish an editorial broadsheet digital reading experience built with Next.js and Tailwind CSS.

---

## 1. Technology Stack

- **Frontend:** Next.js (App Router), TypeScript, Tailwind CSS, Playfair Display & Inter typography, next-themes (Light/Dark mode), Lucide Icons.
- **Backend:** Python 3.11+, FastAPI, Pydantic v2 Settings, SQLAlchemy 2.0 (async), Alembic, HTTPX.
- **News Discovery Worker:** Python asyncio, Webz.io News API client, APScheduler (08:00 Sports, 20:00 Business Asia/Dhaka), PostgreSQL budget ledger.
- **Database:** PostgreSQL 16 with persistent volume and connection pooling.
- **Reverse Proxy:** Nginx 1.27 with gzip compression, caching, and Let's Encrypt SSL readiness.
- **Orchestration & CI/CD:** Docker, Docker Compose, GitHub Actions.
- **Target Infrastructure:** Ubuntu Server 24.04 LTS on AWS EC2 `t3.small` (2 vCPU, 2 GB RAM).

---

## 2. Monorepo Architecture

```text
metroscope/
├── frontend/             # Next.js 14 App Router web client
├── backend/              # FastAPI application and Webz.io discovery worker
├── infrastructure/       # Dockerfiles and Nginx reverse proxy configuration
├── docs/                 # Architectural and setup documentation
├── .github/workflows/    # CI/CD validation pipelines
└── docker-compose.yml    # Complete platform orchestration
```

---

## 3. Getting Started

### Prerequisites

- **Node.js:** v20.x or higher and `npm`
- **Python:** v3.11 or higher
- **Docker & Docker Compose:** Docker Desktop or Docker Engine 24+

### Environment Setup

Create your local `.env` configuration file from the template:

```bash
cp .env.example .env
```

Review and update credentials if connecting to an external database.

---

## 4. Local Development

### Option A: Running with Docker Compose (Recommended)

To launch the full stack (PostgreSQL, Backend API, Worker, Next.js Frontend, and Nginx):

```bash
docker compose up -d --build
```

Access the services:
- **Web Portal:** [http://localhost](http://localhost) (via Nginx) or [http://localhost:3000](http://localhost:3000) (direct)
- **Backend API Docs:** [http://localhost:8000/api/v1/docs](http://localhost:8000/api/v1/docs)
- **Health Check:** [http://localhost:8000/health](http://localhost:8000/health)

### Option B: Running Services Individually

#### 1. Backend & News Worker

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start FastAPI API server
uvicorn app.main:app --reload --port 8000

# In a separate terminal, run news worker:
python -m app.workers.main
```

#### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) to view the portal.

---

## 5. Verification & Testing

### Running Backend Tests
```bash
cd backend
pytest -v
```

### Running Frontend Checks
```bash
cd frontend
npm run lint
npm run typecheck
npm run build
```

### Validating Docker Compose
```bash
docker compose config
```

---

## 6. Documentation Index

- [Project Structure Guide](docs/PROJECT_STRUCTURE.md)
- [Architecture & Design Details](docs/ARCHITECTURE.md)
- [Environment Configuration Guide](docs/ENVIRONMENT_SETUP.md)
- [Phase 1 Implementation Report](docs/PHASE_1_IMPLEMENTATION_REPORT.md)

---

## 7. License & Compliance

News metadata indexed via Webz.io News API. Original publisher copyrights and trademarks are acknowledged and protected through strict fair-use metadata summaries and direct original article links. MetroScope operates in a metadata-only publication mode and does not republish full article text or store unauthorized third-party media.
