<<<<<<< HEAD
# AutoFix AI v4.0
=======


# AutoFix AI — v4.0.0 Production

> Self-Learning Autonomous Debugging Engine  
> Deterministic before probabilistic. Probabilistic before generative. Always.

---

## Phase Gate Status

| Phase | Gate | Status |
|-------|------|--------|
| 0 | PRD + SLO + Cost | ✅ PASSED |
| 0.5 | Deep Research | ✅ PASSED |
| 1 | Stack + ADRs + CI | ✅ CI passing |
| 2 | GET /health 200 | ✅ Implemented |
| 3 | Rule Engine + FaultLocalizer | ✅ All 6 rules + 40 unit tests |
| 4 | Second Brain + L1 Cache | ✅ Confidence formula + SELECT FOR UPDATE |
| 5 | Core Repair Loop | ✅ 4-layer orchestrator + AtomicRollback + SSE |
| 6 | AI/ML Layer | ✅ Circuit breaker + attempt-aware prompting |
| 7 | Safety + Guardrails | ✅ BASIC/ENDPOINT/TESTS validation |
| 8 | Learning Loop + Wiki | ✅ update_all_layers on every outcome |
| 9 | Testing + Observability | 🔲 Coverage run pending |
| 10 | CI/CD + Hardening | 🔲 Trivy scan pending |

---

## Quickstart

```bash
# 1. Clone and configure
cp .env.example .env
# Set ANTHROPIC_API_KEY in .env

# 2. Run with Docker Compose (recommended)
docker-compose up --build

# 3. Verify Phase 2 gate
curl http://localhost:8000/health
# → {"status": "ok", "db": "ok", "rule_count": 5, "version": "4.0.0"}

# 4. Run tests
pip install -r requirements.txt
pytest tests/unit/ -v                    # 40+ unit tests
pytest tests/integration/ -v             # auth + RBAC + endpoints
pytest tests/concurrency/ -v             # SELECT FOR UPDATE race conditions
=======
<div align="center">
>>>>>>> origin/main

Autonomous Python debugging engine. Four-layer repair stack: Rule Engine → L1 Cache → Second Brain → LLM Agent.

## Quick Start
```bash
cp .env.example .env
# Add ANTHROPIC_API_KEY to .env
docker compose up --build
# Frontend: http://localhost:3000
# API:      http://localhost:8000/docs
```

## Demo (no API credits needed)
```bash
curl -X POST http://localhost:8000/api/v1/repairs \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
<<<<<<< HEAD
  -d '{"stack_trace":"ModuleNotFoundError: No module named sqlalchemy","repo_path":"/tmp/demo_repo","validation_level":"BASIC"}'
# → RULE-001 fires, status: FIXED, llm_cost_usd: 0.0, elapsed_ms: ~30
=======
  -d '{"repo_path": "scenarios/scenario1", "error_description": "app crashes on startup"}'

# 4. Open the dashboard
open http://localhost:5173
>>>>>>> origin/main
>>>>>>> origin/main
```

## Architecture
- **Layer 1**: Rule Engine — deterministic, <5ms, $0
- **Layer 2**: L1 TTLCache — sub-ms, $0  
- **Layer 3**: Second Brain — semantic memory, <50ms, $0
- **Layer 4**: LLM Agent — Claude API, ~30s, ~$0.006

<<<<<<< HEAD
## Stack
FastAPI · PostgreSQL · SQLAlchemy Async 2.0 · Alembic · JWT/Argon2 · Prometheus · Docker
=======
<<<<<<< HEAD
## Four-Layer Architecture

```
POST /api/v1/repairs
        │
        ▼
FaultLocalizerService ── stderr → ErrorSignature(structural)
        │
        ▼
┌─────────────────────────────────┐
│ LAYER 1: Rule Engine ⚡         │  < 5ms   $0.000
│ Deterministic YAML rules        │  6 builtin + org rules
│ Confidence gate: > 0.85         │
└──────── HIT ──────── MISS ──────┘
                          │
              ┌───────────▼──────────┐
              │ LAYER 2: L1 Cache 🚀 │  < 1ms   $0.000
              │ TTLCache(1000, 3600) │
              └──── HIT ─── MISS ───┘
                              │
                  ┌───────────▼──────────┐
                  │ LAYER 3: Second Brain│  < 50ms  $0.000
                  │ Structural hash +    │  confidence-gated > 0.80
                  │ fuzzy similar()      │
                  └──── HIT ─── MISS ───┘
                                  │
                      ┌───────────▼──────────┐
                      │ LAYER 4: LLM Agent   │  < 30s   $0.003–$0.05
                      │ Claude API           │  attempt-aware prompting
                      │ wiki_context always  │  max 5 iterations
                      └──────────────────────┘
                                  │
                  SafetyValidator (BASIC|ENDPOINT|TESTS)
                  AtomicRollback on failure
                  Learning update on every outcome (win + loss)
                  SSE stream → repair_complete + explainability
=======
## SSE Event Reference
>>>>>>> origin/main

# 🚀 AutoFix AI v4.0

Self-learning autonomous debugging engine.

## 🔥 Features

- ⚡ Rule-based instant fixes (<5ms, $0 cost)
- 🧠 Second Brain (memory + confidence scoring)
- 🤖 LLM fallback (mock-enabled, zero cost demo)
- 🔁 Autonomous repair loop (run → fix → validate)
- 🐳 Docker sandbox execution

---

## 🌐 Live API

👉 https://your-render-url.onrender.com/docs

---

<<<<<<< HEAD
## 🧪 Demo (No API Key Needed)
=======
## Database Schema

```sql
CREATE TABLE memory_entries (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    error_hash    TEXT    NOT NULL UNIQUE,  -- SHA256(type + ':' + file + ':' + line)
    error_type    TEXT    NOT NULL,          -- 'ModuleNotFoundError'
    fix           TEXT    NOT NULL,          -- unified diff that passed validation
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    confidence    REAL    DEFAULT 0.7,       -- instant reuse threshold: > 0.80
    last_used     TIMESTAMP,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
>>>>>>> origin/main
```

---

<<<<<<< HEAD
## SLO Targets (from PRD §5)

| Operation | p50 | p95 | p99 |
|-----------|-----|-----|-----|
| Rule hit (full repair) | < 500ms | < 1s | < 2s |
| Memory hit (full repair) | < 1s | < 2s | < 5s |
| LLM repair (2-iter avg) | < 30s | < 60s | < 90s |
| Rule Engine evaluate | < 5ms | < 10ms | < 20ms |
| L1 Cache lookup | < 1ms | < 2ms | < 5ms |

---

## API

```
POST   /api/v1/repairs              Submit repair (SSE stream)
GET    /api/v1/repairs              List repairs (paginated)
GET    /api/v1/repairs/{id}         Repair detail + explainability

POST   /api/v1/auth/register
POST   /api/v1/auth/login
POST   /api/v1/auth/refresh
POST   /api/v1/auth/logout

GET    /api/v1/rules                List rules
POST   /api/v1/rules                Create rule [SRE|ADMIN]
PATCH  /api/v1/rules/{id}           Update rule [SRE|ADMIN]
DELETE /api/v1/rules/{id}           Soft delete [ADMIN]

GET    /api/v1/memory               List memory entries
GET    /api/v1/memory/stats         Hit rates + avg confidence
DELETE /api/v1/memory/{id}          Evict entry [SRE|ADMIN]

GET    /api/v1/wiki                 List wiki pages
GET    /api/v1/wiki/{slug}          Get wiki page

GET    /health                      Subsystem health check
GET    /metrics                     Prometheus metrics
=======
## Wiki File Format

```markdown
# ModuleNotFoundError

## Description
Raised when Python cannot find a required module at import time.

## Common Causes
- Package missing from requirements.txt
- Wrong virtual environment activated
- Package name differs from import name (e.g., `pip install Pillow` vs `import PIL`)

## Fix Patterns
1. Add missing package to requirements.txt
2. Run pip install -r requirements.txt inside the container
3. Verify package name matches PyPI distribution name

## Seen Cases

### [2026-04-08 14:23:11] — sqlalchemy
Error: `ModuleNotFoundError: No module named 'sqlalchemy'`
Fix: Added `sqlalchemy` to requirements.txt
Result: PASSED (1 iteration, 12.4s → memory confidence: 0.75)
>>>>>>> origin/main
```

---

<<<<<<< HEAD
## Critical Patterns Implemented

1. **Audit BEFORE execute** — `REPAIR_STARTED` written inside same transaction before first sandbox run
2. **SELECT FOR UPDATE** — `memory_repository.update_outcome()` prevents concurrent confidence race
3. **Zero-trust RBAC** — `require_role()` dependency on every route, org_id always from JWT
4. **AtomicRollback** — snapshot before patch, restore on failure, CRITICAL log if rollback fails
5. **Confidence gating** — > 0.80 auto-use, 0.60–0.80 warn, < 0.60 → LLM always called
6. **Attempt-aware LLM** — failed strategies injected into prompt, patch hash guard detects loops
7. **N+1 prevention** — `get_by_error_type()` returns all candidates in single query
8. **Idempotent memory updates** — `update_outcome()` uses SELECT FOR UPDATE, safe to retry
=======
## Confidence Learning

```
Initial store    → confidence = 0.70
Successful reuse → confidence = MIN(prev + 0.05, 1.00)
Failed reuse     → confidence = MAX(prev − 0.20, 0.00)
Auto-use gate    → confidence > 0.80 required

After 3 successes on same error: confidence = 0.85 → instant fix enabled
After 1 failure: confidence drops to 0.65 → falls back to LLM
```

---

## Environment Variables
>>>>>>> origin/main

```bash
curl -X POST https://your-render-url.onrender.com/api/v1/repairs \
-H "Content-Type: application/json" \
-d '{"stack_trace":"ModuleNotFoundError: No module named sqlalchemy","repo_path":"/tmp/demo","validation_level":"BASIC"}'
