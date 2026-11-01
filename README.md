# YottaFlex AI — Enterprise HR Service Management & Policy Resolution Platform

> **Candidate Technical Project Submission — YottaFlex AI**

A fully functional, deterministic HR service desk platform. Employees submit HR requests; the system automatically classifies them, detects sensitive cases, retrieves the correct policy version, routes to the right team, tracks SLA deadlines, and records a full audit trail — **with zero LLM or AI at runtime**.

---

## Table of Contents

- [What This Project Does](#what-this-project-does)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Quick Setup (Local — Recommended)](#quick-setup-local--recommended)
- [Quick Setup (Docker)](#quick-setup-docker)
- [Demo Login Accounts](#demo-login-accounts)
- [Running the Tests](#running-the-tests)
- [Generating & Loading Synthetic Data](#generating--loading-synthetic-data)
- [Project Structure](#project-structure)
- [API Documentation](#api-documentation)
- [Key Features](#key-features)
- [Screenshots / Pages](#screenshots--pages)

---

## What This Project Does

| Feature | How it works |
|---|---|
| **Ticket classification** | Weighted keyword + phrase + synonym rules for PAYROLL, LEAVE, BENEFITS, ONBOARDING — no ML, fully explainable |
| **Sensitive case detection** | 14 keywords + 10 regex patterns; harassment/discrimination cases go to a RESTRICTED queue, invisible to regular HR users |
| **Policy validity engine** | Distinguishes latest-created vs latest-published vs currently-effective vs historically-effective policy versions |
| **Knowledge base** | Articles linked to policy versions; search returns policy-backed answers with citations |
| **SLA tracking** | Mon–Fri 09:00–17:00 UTC business hours, holiday exclusion, pause/resume, breach alerts |
| **Clarification workflow** | Vague tickets automatically ask the employee for more info before routing |
| **Audit trail** | Every status change, access denial, and decision is logged in an append-only event table |
| **Analytics & evaluation** | 99.42% category accuracy, 100% sensitive recall measured against a separate ground-truth dataset |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.9+ · FastAPI · SQLAlchemy 2 · Alembic |
| Frontend | React 18 · TypeScript · Vite · Tailwind CSS · Recharts |
| Database | SQLite (local dev) · PostgreSQL (Docker / production) |
| Auth | JWT (python-jose) · bcrypt (passlib) |
| Data generation | Faker · pandas · NumPy (deterministic seed 20261022) |
| Testing | pytest (37 tests) |
| Deployment | Docker · Docker Compose |

---

## Prerequisites

Make sure these are installed before you start:

| Tool | Minimum version | Check |
|---|---|---|
| Python | 3.9+ | `python3 --version` |
| Node.js | 16+ | `node --version` |
| npm | 8+ | `npm --version` |
| Git | any | `git --version` |
| Docker _(optional)_ | 20+ | `docker --version` |

---

## Quick Setup (Local — Recommended)

> Uses SQLite — **no database server needed**. Works on macOS, Linux, and Windows WSL.

### Step 1 — Clone the repository

```bash
git clone https://github.com/your-username/yottaflex-hr-service-management.git
cd yottaflex-hr-service-management
```

---

### Step 2 — Set up the Python environment

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cd ..
```

---

### Step 3 — Generate synthetic data and load the database

```bash
# From the project root — generates 5,000 tickets, 20,000 messages, 150 knowledge articles
backend/.venv/bin/python -m generator.generate --output generator/output

# Load all generated data into SQLite (takes ~30 seconds)
DATABASE_URL=sqlite:///./yottaflex_dev.db \
  SEED_REFERENCE_DATA=false \
  backend/.venv/bin/python -m generator.load_to_db --input generator/output
```

> **Windows users** — replace the `\` line continuation with `^` and set env vars with `set VAR=value &&` before the command, or use Git Bash / WSL.

---

### Step 4 — Start the backend API

Open a **new terminal tab** and run:

```bash
cd backend
DATABASE_URL=sqlite:///../yottaflex_dev.db \
  SEED_REFERENCE_DATA=false \
  SEED_DEMO_USERS=false \
  .venv/bin/uvicorn app.main:app --reload --port 8000
```

✅ You should see:
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

Verify it works:
```bash
curl http://localhost:8000/health
# → {"status":"ok","version":"1.0.0"}
```

---

### Step 5 — Start the frontend

Open another **new terminal tab** and run:

```bash
cd frontend
npm install
npm run dev
```

✅ You should see:
```
  VITE v5.4.8  ready in ~500ms
  ➜  Local:   http://localhost:5173/
```

---

### Step 6 — Open the app

Go to **http://localhost:5173** in your browser and log in with any demo account below.

---

## Quick Setup (Docker)

> Runs everything (PostgreSQL + backend + frontend) with a single command. Requires Docker Desktop.

```bash
git clone https://github.com/your-username/yottaflex-hr-service-management.git
cd yottaflex-hr-service-management

cp .env.example .env          # uses default dev values — fine for local testing
docker compose up --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000/api/v1 |
| Swagger docs | http://localhost:8000/docs |

> On first run Docker will generate the synthetic data and load the database automatically.

---

## Demo Login Accounts

All accounts use the same password: **`ChangeMe123!`**

| Username | Role | What they can access |
|---|---|---|
| `admin` | Admin | Everything — users, rules, all tickets, sensitive cases, analytics |
| `hr_partner` | HR Partner | All standard tickets, resolve, manage, knowledge base |
| `hr_sensitive` | HR Partner (sensitive) | Same as hr_partner + access to restricted/sensitive cases |
| `it_ops` | IT/Ops | IT category tickets |
| `manager` | Manager | Team tickets, can escalate |
| `employee` | Employee | Submit and track own tickets only |
| `employee2` | Employee | Submit and track own tickets only |

> **Tip:** Log in as `employee`, submit a ticket with "harassment" in the description, then log in as `hr_partner` — the ticket is invisible. Log in as `hr_sensitive` or `admin` to see it.

---

## Running the Tests

```bash
cd backend
.venv/bin/python -m pytest tests/ -v
```

Expected result:
```
37 passed in ~3s
```

| Test file | What it covers |
|---|---|
| `tests/test_api.py` | Login, RBAC, ticket creation, sensitive routing, lifecycle, policy, SLA, analytics (15 tests) |
| `tests/test_rules.py` | Classification, sensitive detection, clarification, SLA business-hours arithmetic (17 tests) |
| `tests/test_generator.py` | Row counts, reproducibility (SHA-256), anomaly types, ground-truth separation (5 tests) |

---

## Generating & Loading Synthetic Data

The generator is fully deterministic — the same seed always produces identical output.

```bash
# From project root
backend/.venv/bin/python -m generator.generate --output generator/output
```

This creates (in `generator/output/`):

| File | Records |
|---|---|
| tickets.csv | 5,000 |
| messages.csv | 20,000 |
| knowledge_articles.csv | 150 |
| policy_documents.csv | 24 |
| policy_versions.csv | 54 |
| audit_logs.csv | ~31,900 |
| ground_truth.json | 5,000 labels |
| anomaly_register.csv | 65 injected anomalies (13 types) |

**Prove it is reproducible:**
```bash
backend/.venv/bin/python -m generator.generate --output /tmp/run2
diff -r generator/output /tmp/run2 && echo "IDENTICAL ✅"
```

**Run data validation:**

backend/.venv/bin/python -m validation.report_generator \
  --input generator/output \
  --output reports/DATA_VALIDATION_REPORT.md \
  --reproducibility reports/REPRODUCIBILITY_REPORT.md
```

Expected: `validation: PASS (injected findings=65, missed=0, unintended=0)`

---

## Project Structure


.
├── backend/
│   ├── app/
│   │   ├── api/            REST endpoints (auth, tickets, policies, knowledge, sla, analytics, admin)
│   │   ├── models/         SQLAlchemy database models (29 tables)
│   │   ├── rules/          Deterministic business engines
│   │   │   ├── classification_engine.py     keyword/phrase/synonym scoring
│   │   │   ├── policy_validity_engine.py    effective version selection
│   │   │   ├── sensitive_routing_engine.py  harassment/discrimination detection
│   │   │   ├── clarification_engine.py      missing-info templates
│   │   │   ├── sla_engine.py                business-hours calculations
│   │   │   ├── knowledge_retrieval_engine.py policy-backed answers
│   │   │   └── routing_engine.py            team assignment
│   │   ├── schemas/        Pydantic request/response models
│   │   ├── services/       Business orchestration layer
│   │   ├── security/       JWT, bcrypt, RBAC permissions
│   │   └── repositories/   Database access layer
│   ├── tests/              pytest test suite (37 tests)
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── pages/          10 UI pages (Login, Dashboard, Tickets, Policies, etc.)
│   │   ├── components/     Reusable UI components
│   │   ├── services/       Axios API client wrappers
│   │   ├── hooks/          Custom React hooks
│   │   ├── contexts/       Auth context
│   │   └── types/          TypeScript interfaces
│   ├── package.json
│   └── Dockerfile
│
├── generator/              Synthetic data generator (seed 20261022)
│   ├── master_data/        Departments, employees, categories, policies, knowledge
│   ├── transaction_data/   Tickets, messages, SLAs, resolutions
│   ├── anomaly_injection/  13 labelled anomaly types
│   ├── ground_truth/       Ground-truth label builder
│   └── generate.py         Entry point
│
├── database/
│   └── migrations/         Alembic migration scripts (for PostgreSQL)
│
├── validation/             Data integrity and business-rule checks
├── documentation/          Architecture, data dictionary, business rules, decisions
├── reports/                Test results, validation report, known limitations
│
├── docker-compose.yml
├── .env.example
└── README.md               ← you are here

---

## API Documentation

When the backend is running, visit **http://localhost:8000/docs** for the interactive Swagger UI where you can try every endpoint directly in the browser.

All routes are under `/api/v1`:

| Group | Endpoints |
|---|---|
| Auth | `POST /auth/login` · `POST /auth/logout` · `GET /auth/me` |
| Employees | `GET /employees` · `POST /employees` · `GET /employees/{id}` |
| Tickets | `GET/POST /tickets` · `GET/PATCH /tickets/{id}` · `/assign` · `/escalate` · `/resolve` · `/messages` |
| Policies | `GET/POST /policies` · `GET /policies/{id}/effective` · `/versions` · `/publish` · `/archive` |
| Knowledge | `POST /knowledge/search` · `GET /knowledge/articles` · `GET /knowledge/articles/{id}` |
| SLA | `GET /sla/metrics` · `GET /sla/check-breaches` · `GET /sla/calendar` |
| Analytics | `GET /analytics/overview` · `/tickets` · `/performance` · `/evaluation` |
| Admin | `GET /admin/users` · `/audit-logs` · `/category-rules` · `/routing-rules` |

---

## Key Features

### 1. Ticket Lifecycle

```
NEW → CLASSIFIED → AWAITING_CLARIFICATION → ASSIGNED → IN_PROGRESS → RESOLVED → CLOSED
                                                      ↑ ESCALATED ↓
                                            RESOLVED → REOPENED → IN_PROGRESS
                                            any state → CANCELLED
```

Every transition creates an immutable audit event. Invalid transitions return HTTP 422.

### 2. Role Permissions

| Role | Key permissions |
|---|---|
| EMPLOYEE | Submit tickets, view own tickets, search knowledge base |
| MANAGER | + View team tickets, escalate |
| HR_PARTNER | + View all tickets, resolve, manage knowledge |
| IT_OPS | + Manage IT tickets |
| ADMIN | Everything + manage users, roles, policies, config, view sensitive cases |

### 3. SLA Targets (business hours)

| Category | P1 | P2 | P3 |
|---|---|---|---|
| PAYROLL | 4h | 8h | 24h |
| LEAVE | 8h | 16h | 48h |
| BENEFITS | 8h | 16h | 48h |
| ONBOARDING | 4h | 8h | 24h |
| SENSITIVE | 2h first response | escalated immediately |  |

### 4. Measured Results (on 5,000-ticket dataset)

| Metric | Value |
|---|---|
| Category classification accuracy | 99.42% |
| Sensitive case recall | 100% (zero missed) |
| SLA compliance rate | 84.39% |
| Avg first response time | 7.73 business hours |
| Avg resolution time | 27.15 business hours |

---

## Screenshots / Pages

| Page | URL (when running) |
|---|---|
| Login | http://localhost:5173/login |
| Employee Dashboard | http://localhost:5173/dashboard |
| HR Dashboard | http://localhost:5173/hr-dashboard |
| Ticket Management | http://localhost:5173/tickets |
| Policy Management | http://localhost:5173/policies |
| Knowledge Base | http://localhost:5173/knowledge |
| SLA Dashboard | http://localhost:5173/sla |
| Analytics | http://localhost:5173/analytics |
| Admin Panel | http://localhost:5173/admin |

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'app'`**
→ You ran uvicorn from the project root. Always `cd backend` first.

**`UNIQUE constraint failed: roles.name`**
→ The database already has data. Delete `yottaflex_dev.db` and re-run `load_to_db`.

**Login says "Invalid credentials"**
→ Check the backend is running on port 8000: `curl http://localhost:8000/health`
→ Password is exactly `ChangeMe123!` (capital C, capital M, exclamation mark at end).

**Frontend shows a blank page or network error**
→ The backend must be running on port 8000 before you open the frontend.

**Port already in use**
→ Change the port: `uvicorn app.main:app --port 8001` and update `VITE_API_BASE_URL=http://localhost:8001/api/v1` in your `.env`.

