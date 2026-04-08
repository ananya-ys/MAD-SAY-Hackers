<div align="center">

```
█████╗ ██╗   ██╗████████╗ ██████╗ ███████╗██╗██╗  ██╗     █████╗ ██╗
██╔══██╗██║   ██║╚══██╔══╝██╔═══██╗██╔════╝██║╚██╗██╔╝    ██╔══██╗██║
███████║██║   ██║   ██║   ██║   ██║█████╗  ██║ ╚███╔╝     ███████║██║
██╔══██║██║   ██║   ██║   ██║   ██║██╔══╝  ██║ ██╔██╗     ██╔══██║██║
██║  ██║╚██████╔╝   ██║   ╚██████╔╝██║     ██║██╔╝ ██╗    ██║  ██║██║
╚═╝  ╚═╝ ╚═════╝    ╚═╝    ╚═════╝ ╚═╝     ╚═╝╚═╝  ╚═╝    ╚═╝  ╚═╝╚═╝
```

**Self-Learning Autonomous Debugging Engine**

*Your code breaks. It fixes itself. Then it never makes the same mistake twice.*

---

[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python)](https://python.org)
[![Docker](https://img.shields.io/badge/Docker-isolated%20sandbox-2496ED?style=flat-square&logo=docker)](https://docker.com)
[![Claude](https://img.shields.io/badge/Claude-sonnet--4-CC785C?style=flat-square)](https://anthropic.com)
[![License](https://img.shields.io/badge/License-MIT-22C55E?style=flat-square)](LICENSE)
[![PRD](https://img.shields.io/badge/PRD-v3.0.0-6366F1?style=flat-square)](docs/PRD_v3.md)

</div>

---

## The Problem

Debugging is a loop:

```
read error → form hypothesis → patch → redeploy → pray → repeat
```

This loop consumes **30–40% of every developer's working week.** Not because bugs are hard — most aren't. Because the loop has no memory. Every bug is solved from scratch. The knowledge dies in a Slack thread nobody will ever search again.

**80% of runtime errors fall into patterns that are structurally identical.** `ModuleNotFoundError`, `SyntaxError`, missing env vars, type mismatches. Engineers solve these manually. Every time. For their entire careers.

---

## The Solution

AutoFix AI closes the loop autonomously:

```
broken repo → [sandbox] → [fault localizer] → [Second Brain 🧠] → [LLM Wiki 📚] → [repair agent] → [patch] → [validate] → fixed repo
```

**No human in the loop. Under 90 seconds.**

And the second time it sees the same error:

```
broken repo → [sandbox] → [fault localizer] → [Second Brain: HIT] → fixed repo
```

**0.3 seconds. No AI call. The system remembered.**

---

## Architecture: Three-Layer Intelligence

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AUTOFIX AI v3                                 │
├───────────────────┬─────────────────────┬───────────────────────────┤
│  ⚙️  Engine         │  🧠  Second Brain    │  📚  LLM Wiki             │
│                   │                     │                           │
│  Execute          │  SQLite memory      │  /debug_wiki/errors/      │
│  Fault-localize   │  Confidence scoring │  Append-only .md files    │
│  Patch            │  Instant fix cache  │  Self-updating knowledge  │
│  Validate         │  Hash-based lookup  │  Enriches LLM prompts     │
│  Stream (SSE)     │  < 50ms lookup      │  < 20ms read              │
└───────────────────┴─────────────────────┴───────────────────────────┘
         │                   │                         │
         └───────────────────┴─────────────────────────┘
                    Unified lookup in repair_loop.py
              (memory + wiki queried together, always)
```

### The Integration Rule
> **Memory and Wiki are never queried separately.** Every repair: check memory first, fetch wiki context always, inject wiki into LLM prompt if agent is called, update both on completion.

```python
# repair_loop.py — the integration point
memory_hit  = await memory_service.get_fix(session, error_hash)
wiki_ctx    = await wiki_service.get_context(fault.error_type)   # always

if memory_hit and memory_hit.confidence > 0.80:
    await emit(SSEEvent('memory_hit', {
        'confidence': memory_hit.confidence,
        'wiki_pages': wiki_ctx.pages_used,      # shown in KnowledgePanel
    }))
    result = await patch_applier.apply(memory_hit.fix)
else:
    repair = await repair_agent.generate(fault, wiki_ctx)   # wiki always injected
    result = await patch_applier.apply(repair.patch_diff)

# always update both — never skip this
await memory_service.update(error_hash, success=result.passed)
await wiki_service.update_wiki(fault.error_type, result)
```

---

## How It Works

### 1. Sandbox Execution
Code runs in an isolated Docker container: `--network=none`, `--memory=512m`, 30-second hard kill. Captures stdout, stderr, exit code. Streams the first event within 500ms.

### 2. Fault Localization
Parses stderr with regex patterns for the 6 most common Python error types. Extracts `error_type`, `file_path`, and `line_number`. Reads the suspect file content from disk.

### 3. Second Brain (Memory Layer)
Before every LLM call, queries SQLite for a matching `error_hash = SHA256(type + file + line)`. If `confidence > 0.8`: instant fix, no API call. After every repair: `success → +0.05 confidence`, `failure → −0.20 confidence`. System self-corrects.

```
Confidence algorithm:
  First store:  0.70
  Each success: MIN(confidence + 0.05, 1.0)
  Each failure: MAX(confidence − 0.20, 0.0)
  Auto-use:     only if confidence > 0.80
```

### 4. LLM Wiki (Knowledge Layer)
Reads `/debug_wiki/errors/{error_type}.md` before every LLM call. Injects the content into the repair prompt as context. After a successful repair, appends a new `## Seen Case` entry to the file. The wiki grows with every repair and makes future fixes more accurate.

```
debug_wiki/errors/ModuleNotFoundError.md
─────────────────────────────────────────
## Description
Occurs when Python cannot find a required module...

## Common Fix Patterns
- Add missing package to requirements.txt
- Verify virtual environment is activated

## Seen Cases
### [2026-04-08 14:23] — sqlalchemy
Fix: Added `sqlalchemy` to requirements.txt
Result: PASSED (1 iteration, 12.4s)
```

### 5. Repair Loop
Orchestrates: sandbox → localize → [memory+wiki] → [agent] → patch → sandbox. Max 5 iterations. 5-minute timeout. Duplicate patch guard (SHA256). Every state transition emits an SSE event to the React dashboard.

---

## The Three Demo Moments

| # | What Happens | What It Proves |
|---|---|---|
| **Autonomy** | Broken FastAPI app → fixed → tests pass. 12 seconds. Zero human input. | You execute. Everyone else suggests. |
| **Learning** | Same broken app again → 0.3 seconds. `🧠 Second Brain: Learned Fix (94%)` | System gets faster every run. |
| **Knowledge** | Open `debug_wiki/log.md` live — new entry just appended. | Builds its own runbook in real time. |

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| API | FastAPI 0.115+ (async) | Native SSE, Pydantic v2 |
| AI | Claude API (`claude-sonnet-4-20250514`) | Best structured JSON output for diffs |
| Sandbox | Docker SDK for Python | Isolated, networked-none, hard-killed |
| Second Brain | SQLite (`memory_entries` table) | Hash lookup. NOT a vector DB. |
| LLM Wiki | Markdown files (`/debug_wiki/errors/`) | Plain files. Git-trackable. No infra. |
| Frontend | React + Vite + TailwindCSS | SSE via EventSource API |
| Streaming | Server-Sent Events | Native FastAPI EventSourceResponse |
| **Rejected** | LangChain, vector DB, Celery, embeddings | Overengineering. Added zero demo value. |

---

## Project Structure

```
autofix-ai/
├── app/
│   ├── main.py                      # FastAPI + lifespan
│   ├── core/
│   │   ├── config.py                # Settings — CLAUDE_API_KEY, DOCKER_TIMEOUT
│   │   └── database.py              # async SQLite engine (aiosqlite)
│   ├── models/memory.py             # MemoryEntry ORM model
│   ├── schemas/repair.py            # RepairRequest, SSEEvent, RepairResult
│   └── services/
│       ├── sandbox_service.py       # Docker execution engine
│       ├── fault_localizer.py       # stderr regex parser
│       ├── memory_service.py        # Second Brain 🧠 — get/store/update
│       ├── wiki_service.py          # LLM Wiki 📚 — get_context/update_wiki
│       ├── repair_agent_service.py  # Claude API — receives wiki_ctx always
│       ├── patch_applier.py         # Apply unified diff to /tmp/ copy
│       └── repair_loop.py           # ← Integration point: memory + wiki unified
├── app/api/v1/repairs.py            # POST /repairs → SSE stream
├── alembic/                         # DB migrations
├── debug_wiki/
│   ├── errors/                      # One .md per error type
│   │   ├── ModuleNotFoundError.md
│   │   ├── SyntaxError.md
│   │   ├── ImportError.md
│   │   └── KeyError.md
│   └── log.md                       # Append-only repair history
├── scenarios/                       # Pre-broken repos for demo/testing
│   ├── scenario1/                   # ModuleNotFoundError
│   ├── scenario2/                   # SyntaxError
│   └── scenario3/                   # Missing env variable
├── frontend/
│   └── src/components/
│       ├── TerminalStream.tsx        # Live SSE event stream
│       ├── KnowledgePanel.tsx        # Shows wiki pages used (MUST HAVE)
│       ├── DiffViewer.tsx            # Before/after patch diff
│       ├── TimelineTracker.tsx       # Repair step progress
│       ├── MemoryHitBadge.tsx        # Second Brain hit indicator
│       └── PerformancePanel.tsx      # Run 1 vs Run 2 timing
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
└── .env.example
```

---

## Quick Start

```bash
# 1. Clone and configure
git clone https://github.com/your-username/autofix-ai.git
cd autofix-ai
cp .env.example .env
# Add your CLAUDE_API_KEY to .env

# 2. Start the stack
docker-compose up --build

# 3. Run a repair (terminal)
curl -N http://localhost:8000/api/v1/repairs \
  -H "Content-Type: application/json" \
  -d '{"repo_path": "scenarios/scenario1", "error_description": "app crashes on startup"}'

# 4. Open the dashboard
open http://localhost:5173
```

---

## SSE Event Reference

Every repair streams the following events to the frontend:

| Event | Payload | When |
|---|---|---|
| `sandbox_run` | `{ stdout, stderr, exit_code, elapsed_ms }` | After each sandbox execution |
| `fault_located` | `{ error_type, file_path, line_number }` | After fault localization |
| `wiki_context_loaded` | `{ pages_used: [...], context_length }` | After wiki read (always fires) |
| `memory_hit` | `{ confidence, fix_preview, wiki_pages, elapsed_ms, speedup }` | On Second Brain cache hit |
| `agent_called` | `{ tokens_used, model }` | When Claude API is invoked |
| `patch_applied` | `{ changed_files, patch_hash, patch_diff }` | After patch application |
| `repair_complete` | `{ iterations, elapsed_ms, memory_hit, wiki_used }` | On success |
| `repair_failed` | `{ reason, iterations, last_error }` | On max iterations or timeout |

---

## Performance Targets

| Operation | p50 | p95 | Hard Limit |
|---|---|---|---|
| First SSE event | < 500ms | < 1s | 2s |
| Full repair (cold) | < 15s | < 30s | 60s |
| Full repair (memory warm) | < 500ms | < 1s | 2s |
| Memory lookup | < 50ms | < 100ms | 500ms |
| Wiki context read | < 20ms | < 50ms | 200ms |

---

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
```

---

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
```

---

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

```bash
# Required
CLAUDE_API_KEY=sk-ant-...          # Anthropic API key

# Optional (with defaults)
DOCKER_TIMEOUT=30                   # Container kill timeout (seconds)
WIKI_PATH=./debug_wiki              # Path to wiki folder
DATABASE_URL=sqlite+aiosqlite:///./autofix.db
DEMO_TOKEN=demo                     # Simple JWT secret for hackathon
MAX_ITERATIONS=5                    # Max repair loop iterations
MEMORY_CONFIDENCE_THRESHOLD=0.80    # Minimum confidence for instant fix
```

---

## What This Is Not

- ❌ Not a code completion tool (Copilot does that)
- ❌ Not a chatbot that suggests fixes (every other tool does that)
- ❌ Not a static analyser (no linting)
- ❌ Not AGI

**What it is:** A scoped, reliable autonomous agent that closes the debug-fix-validate loop for common Python runtime errors, gets faster with every repair, and documents what it learns.

---

## Roadmap

- [ ] Multi-language support (JavaScript, Go, Rust)
- [ ] CI/CD integration (GitHub Actions trigger on failing tests)
- [ ] Team wiki — shared knowledge base across engineers
- [ ] VS Code extension — repair from the editor
- [ ] Knowledge Marketplace — share wiki packs across teams

---

## Built At

Built during the **BuildWithAI 24-Hour Hackathon**, April 2026.
PRD v3.0.0 — Full engineering spec with architecture, phase gates, and demo strategy.

---

<div align="center">

**"It fixes the bug. Then it remembers. Then it teaches itself why."**

[Demo Video](#) · [PRD v3.0.0](docs/PRD_v3.md) · [Report Issue](issues) · [Contribute](CONTRIBUTING.md)

</div>
