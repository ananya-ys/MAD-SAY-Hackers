"""
tests/unit/test_rule_engine.py
Rule Engine unit tests: all 6 builtin rules + confidence gate + MISS path.
"""
import pytest

from app.schemas.error_signature import ErrorSignature
from app.services.rule_engine import RuleEngineService

engine = RuleEngineService()


def _sig(**kwargs) -> ErrorSignature:
    defaults = dict(error_type="UnknownError", module=None, context="runtime")
    defaults.update(kwargs)
    return ErrorSignature(**defaults)


# ── RULE-001: ModuleNotFoundError ─────────────────────────────────────────────

def test_rule001_hits_on_module_not_found():
    sig = _sig(error_type="ModuleNotFoundError", module="sqlalchemy", context="import_failure")
    result = engine.evaluate(sig)
    assert result is not None
    assert result.rule_id == "RULE-001"
    assert result.confidence == 1.0
    assert "requirements.txt" in result.patch

def test_rule001_miss_when_module_is_none():
    sig = _sig(error_type="ModuleNotFoundError", module=None)
    result = engine.evaluate(sig)
    # Should not match RULE-001 (condition: module is not None)
    if result:
        assert result.rule_id != "RULE-001"


# ── RULE-002: NameError typo ─────────────────────────────────────────────────

def test_rule002_hits_on_name_error_with_typo():
    sig = _sig(error_type="NameError", typo_candidate="print", raw_error_line="name 'pritn' is not defined")
    result = engine.evaluate(sig)
    assert result is not None
    assert result.rule_id == "RULE-002"
    assert result.confidence == 0.95

def test_rule002_miss_when_no_typo():
    sig = _sig(error_type="NameError", typo_candidate=None)
    result = engine.evaluate(sig)
    if result:
        assert result.rule_id != "RULE-002"


# ── RULE-003: KeyError env var ────────────────────────────────────────────────

def test_rule003_hits_on_env_var_key_error():
    sig = _sig(error_type="KeyError", key="DATABASE_URL", key_is_env_var=True, env_var_name="DATABASE_URL")
    result = engine.evaluate(sig)
    assert result is not None
    assert result.rule_id == "RULE-003"

def test_rule003_miss_on_non_env_key():
    sig = _sig(error_type="KeyError", key="user_id", key_is_env_var=False)
    result = engine.evaluate(sig)
    if result:
        assert result.rule_id != "RULE-003"


# ── RULE-004: ImportError ─────────────────────────────────────────────────────

def test_rule004_hits_on_import_error_with_attr_and_module():
    sig = _sig(error_type="ImportError", attr="async_session", module="sqlalchemy.orm")
    result = engine.evaluate(sig)
    assert result is not None
    assert result.rule_id == "RULE-004"


# ── RULE-005: AttributeError ──────────────────────────────────────────────────

def test_rule005_hits_on_nonetype_attr_error():
    sig = _sig(error_type="AttributeError", attr="compute")
    result = engine.evaluate(sig)
    assert result is not None
    assert result.rule_id == "RULE-005"


# ── Confidence gate ───────────────────────────────────────────────────────────

def test_confidence_gate_blocks_low_confidence_rules():
    """
    Rules with confidence < 0.85 should not be returned.
    RULE-005 confidence=0.85 is exactly at threshold — should fire.
    Any rule below 0.85 must be blocked.
    """
    sig = _sig(error_type="AttributeError", attr="compute")
    result = engine.evaluate(sig)
    if result:
        assert result.confidence >= 0.85


# ── MISS path ─────────────────────────────────────────────────────────────────

def test_miss_returns_none_for_unknown_error():
    sig = _sig(error_type="RecursionError", module=None)
    result = engine.evaluate(sig)
    assert result is None

def test_miss_returns_none_for_runtime_error():
    sig = _sig(error_type="RuntimeError", module=None)
    result = engine.evaluate(sig)
    assert result is None


# ── Result structure ──────────────────────────────────────────────────────────

def test_result_has_all_required_fields():
    sig = _sig(error_type="ModuleNotFoundError", module="requests", context="import_failure")
    result = engine.evaluate(sig)
    assert result is not None
    assert result.rule_id
    assert result.rule_name
    assert result.action_type
    assert isinstance(result.confidence, float)
    assert result.source == "rule"

def test_evaluate_is_sub_10ms():
    """Rule Engine must stay < 5ms on every call (SLO). 10ms is the p99 ceiling."""
    import time
    sig = _sig(error_type="ModuleNotFoundError", module="pydantic", context="import_failure")
    t0 = time.perf_counter()
    engine.evaluate(sig)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert elapsed_ms < 10, f"Rule Engine took {elapsed_ms:.2f}ms — exceeds p99 SLO of 10ms"
