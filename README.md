# AutoFix AI v4.0

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
  -d '{"stack_trace":"ModuleNotFoundError: No module named sqlalchemy","repo_path":"/tmp/demo_repo","validation_level":"BASIC"}'
# → RULE-001 fires, status: FIXED, llm_cost_usd: 0.0, elapsed_ms: ~30
```

## Architecture
- **Layer 1**: Rule Engine — deterministic, <5ms, $0
- **Layer 2**: L1 TTLCache — sub-ms, $0  
- **Layer 3**: Second Brain — semantic memory, <50ms, $0
- **Layer 4**: LLM Agent — Claude API, ~30s, ~$0.006

## Stack
FastAPI · PostgreSQL · SQLAlchemy Async 2.0 · Alembic · JWT/Argon2 · Prometheus · Docker
