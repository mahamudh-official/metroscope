# MetroScope — Monorepo Project Structure

This document outlines the directory structure and responsibilities of each module across the MetroScope codebase.

```text
metroscope/
│
├── frontend/                       # Next.js (App Router) SEO-friendly news portal
│   ├── public/                     # Static assets (official logo.png, icons)
│   ├── src/
│   │   ├── app/                    # Next.js App Router route handlers
│   │   │   ├── about/              # /about - About Us page
│   │   │   ├── article/[slug]/     # /article/[slug] - Normalized article details
│   │   │   ├── category/[slug]/    # /category/[slug] - News category feeds
│   │   │   ├── contact/            # /contact - Contact Editorial Desk
│   │   │   ├── privacy/            # /privacy - Privacy policy
│   │   │   ├── search/             # /search - Archive search interface
│   │   │   ├── terms/              # /terms - Terms & conditions
│   │   │   ├── globals.css         # Broadsheet styling, light/dark design tokens
│   │   │   ├── layout.tsx          # Root layout with masthead, nav & footer
│   │   │   ├── not-found.tsx       # 404 Error page
│   │   │   └── page.tsx            # Front Page / Homepage
│   │   ├── components/             # Reusable UI components
│   │   │   ├── Container.tsx       # Broadsheet grid container
│   │   │   ├── ErrorState.tsx      # Standard error fallback
│   │   │   ├── LoadingState.tsx    # Broadsheet skeleton loader
│   │   │   ├── MainNavigation.tsx  # News desk navigation categories
│   │   │   ├── SiteFooter.tsx      # Editorial footer with newsletter box
│   │   │   ├── SiteHeader.tsx      # Masthead, ticker, search, mobile drawer
│   │   │   └── ThemeToggle.tsx     # Light / Dark theme toggle
│   │   ├── lib/
│   │   │   ├── seo.ts              # OpenGraph, metadata & NewsArticle JSON-LD
│   │   │   └── utils.ts            # Tailwind class merging utility (cn)
│   ├── next.config.mjs             # Next.js configuration (standalone output)
│   ├── package.json                # Frontend dependencies and npm scripts
│   ├── postcss.config.mjs          # PostCSS configuration
│   ├── tailwind.config.ts          # Tailwind tokens derived from Stitch MCP
│   └── tsconfig.json               # TypeScript compiler configuration
│
├── backend/                        # Python FastAPI backend & news worker
│   ├── alembic/                    # Alembic migration management
│   │   ├── versions/               # Versioned migration revision files
│   │   ├── env.py                  # Migration execution environment
│   │   ├── script.py.mako          # Revision template
│   │   └── README                  # Alembic CLI usage guide
│   ├── app/
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── endpoints/      # Version 1 API route controllers
│   │   │       │   └── health.py   # /api/v1/health status endpoint
│   │   │       └── api.py          # Version 1 router aggregator
│   │   ├── core/
│   │   │   ├── config.py           # Pydantic v2 application settings
│   │   │   ├── exceptions.py       # Centralized exception handlers
│   │   │   └── logging.py          # Structured logging configuration
│   │   ├── db/
│   │   │   ├── base.py             # SQLAlchemy 2.0 DeclarativeBase
│   │   │   └── session.py          # Async engine, connection pool & sessionmaker
│   │   ├── integrations/
│   │   │   └── gdelt/
│   │   │       └── client.py       # GDELT DOC 2.0 HTTPX client with retries
│   │   ├── models/
│   │   │   ├── base.py             # TimestampMixin and model foundations
│   │   │   └── __init__.py         # Model package exports
│   │   ├── schemas/
│   │   │   ├── health.py           # Health response Pydantic schema
│   │   │   └── __init__.py         # Schema package exports
│   │   ├── workers/
│   │   │   ├── jobs.py             # Periodic GDELT polling job
│   │   │   ├── main.py             # Standalone news worker process entry point
│   │   │   └── scheduler.py        # APScheduler configuration
│   │   └── main.py                 # FastAPI application factory and ASGI entry
│   ├── tests/
│   │   ├── conftest.py             # Pytest fixtures and test client
│   │   ├── test_gdelt_client.py    # GDELT client unit tests
│   │   ├── test_health.py          # Health endpoint tests
│   │   └── test_scheduler.py       # Worker scheduler tests
│   ├── alembic.ini                 # Alembic configuration file
│   ├── pyproject.toml              # Python project metadata
│   └── requirements.txt            # Python dependencies
│
├── infrastructure/                 # Deployment and infrastructure files
│   ├── docker/
│   │   ├── backend.Dockerfile      # Multi-stage lightweight backend image
│   │   ├── frontend.Dockerfile     # Multi-stage standalone Next.js image
│   │   └── worker.Dockerfile       # Python discovery worker container image
│   └── nginx/
│       ├── conf.d/
│       │   └── metroscope.conf     # Virtual host reverse-proxy rules
│       └── nginx.conf              # Master Nginx configuration (gzip, logs)
│
├── docs/                           # Architectural and operational documentation
│   ├── ARCHITECTURE.md             # High-level architecture and data flows
│   ├── ENVIRONMENT_SETUP.md        # Environment variables and config guide
│   ├── PHASE_1_IMPLEMENTATION_REPORT.md # Deliverables, checks & results
│   └── PROJECT_STRUCTURE.md        # Monorepo directory map (this document)
│
├── .github/
│   └── workflows/
│       └── ci.yml                  # GitHub Actions CI workflow (lint, test, build)
│
├── .env.example                    # Environment configuration template
├── .gitignore                      # Git ignore patterns
├── docker-compose.yml              # Local & production Docker Compose configuration
└── README.md                       # Main repository overview and quickstart
```
