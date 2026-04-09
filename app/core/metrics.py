"""
app/core/metrics.py
Prometheus metrics for AutoFix AI.
All metrics from PRD Section 4.3 (FR-OBS) are defined here.
Imported by services — never by routers.
"""
from prometheus_client import Counter, Gauge, Histogram

# ── Repair sessions ──────────────────────────────────────────────────────────
repair_sessions_total = Counter(
    "autofix_repair_sessions_total",
    "Total repair sessions by status and source_layer",
    ["status", "source_layer"],
)

repair_duration_seconds = Histogram(
    "autofix_repair_duration_seconds",
    "End-to-end repair session duration",
    ["source_layer", "validation_level"],
    buckets=[0.1, 0.5, 1.0, 5.0, 15.0, 30.0, 60.0, 90.0, 120.0],
)

# ── Layer performance ─────────────────────────────────────────────────────────
rule_hits_total = Counter(
    "autofix_rule_hits_total",
    "Rule Engine hits by rule_id",
    ["rule_id"],
)

rule_evaluate_duration_seconds = Histogram(
    "autofix_rule_evaluate_duration_seconds",
    "Rule Engine evaluation latency",
    buckets=[0.001, 0.002, 0.005, 0.010, 0.020, 0.050],
)

memory_hits_total = Counter(
    "autofix_memory_hits_total",
    "Second Brain memory hits",
    ["match_type"],  # exact | fuzzy
)

cache_hits_total = Counter(
    "autofix_cache_hits_total",
    "L1 TTLCache hits",
)

cache_misses_total = Counter(
    "autofix_cache_misses_total",
    "L1 TTLCache misses",
)

cache_hit_rate = Gauge(
    "autofix_cache_hit_rate",
    "Current L1 cache hit rate (0.0–1.0)",
)

# ── LLM ──────────────────────────────────────────────────────────────────────
llm_api_calls_total = Counter(
    "autofix_llm_api_calls_total",
    "Total Claude API calls",
    ["outcome"],  # success | error | circuit_open
)

llm_cost_usd_total = Counter(
    "autofix_llm_cost_usd_total",
    "Cumulative LLM cost in USD",
)

# ── Confidence ───────────────────────────────────────────────────────────────
confidence_histogram = Histogram(
    "autofix_confidence_histogram",
    "Distribution of memory confidence scores at lookup",
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
)

# ── Safety ────────────────────────────────────────────────────────────────────
rollback_total = Counter(
    "autofix_rollback_total",
    "Total atomic rollbacks triggered",
)

rollback_success_total = Counter(
    "autofix_rollback_success_total",
    "Successful rollbacks",
)

# ── Concurrency ───────────────────────────────────────────────────────────────
active_sandboxes = Gauge(
    "autofix_active_sandboxes",
    "Currently running Docker sandbox containers",
)
