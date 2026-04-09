"""
tests/unit/test_confidence.py
Tests for the data-driven confidence scoring formula.
Verifies: success_rate weight, recency decay, frequency cap, thresholds.
"""
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from app.services.memory_service import compute_confidence


def _entry(
    success_count: int,
    failure_count: int,
    days_idle: int = 0,
) -> MagicMock:
    entry = MagicMock()
    entry.success_count = success_count
    entry.failure_count = failure_count
    # Simulate last_used_at relative to now
    entry.last_used_at = datetime.utcnow() - timedelta(days=days_idle)
    entry.created_at = datetime.utcnow() - timedelta(days=days_idle + 1)
    return entry


# ── Success rate component (weight 0.50) ─────────────────────────────────────

def test_perfect_success_rate_high_confidence():
    e = _entry(success_count=10, failure_count=0, days_idle=0)
    conf = compute_confidence(e)
    # success_rate=1.0 * 0.50 + recency≈1.0 * 0.20 + freq=1.0 * 0.30 ≈ 1.0
    assert conf >= 0.95

def test_zero_uses_default_confidence():
    e = _entry(success_count=0, failure_count=0, days_idle=0)
    conf = compute_confidence(e)
    # success_rate=0 * 0.50 + recency=1.0 * 0.20 + freq=0 * 0.30 = 0.20
    assert abs(conf - 0.20) < 0.05

def test_mixed_record_mid_confidence():
    # success_rate=0.50, recent, freq=1.0, effective_freq=0.50
    # → 0.25 + 0.20 + 0.15 = 0.60
    e = _entry(success_count=5, failure_count=5, days_idle=0)
    conf = compute_confidence(e)
    assert 0.55 <= conf <= 0.70


# ── Recency decay (weight 0.20, lambda=0.01) ─────────────────────────────────

def test_recent_entry_higher_than_idle():
    fresh = _entry(success_count=5, failure_count=5, days_idle=0)
    stale = _entry(success_count=5, failure_count=5, days_idle=60)
    assert compute_confidence(fresh) > compute_confidence(stale)

def test_30_days_idle_confidence_decays():
    e = _entry(success_count=10, failure_count=0, days_idle=30)
    conf = compute_confidence(e)
    # recency_score ≈ exp(-0.01*30) ≈ 0.74
    # 0.50 + 0.74*0.20 + 0.30 = 0.948
    assert conf < 1.0
    assert conf > 0.80

def test_100_days_idle_significant_decay():
    e = _entry(success_count=10, failure_count=0, days_idle=100)
    conf = compute_confidence(e)
    # recency ≈ exp(-1) ≈ 0.368 → 0.50 + 0.07 + 0.30 = 0.87
    assert conf < 0.95


# ── Frequency weight (weight 0.30, caps at 10 uses) ─────────────────────────

def test_frequency_caps_at_10_uses():
    e10 = _entry(success_count=10, failure_count=0, days_idle=0)
    e50 = _entry(success_count=50, failure_count=0, days_idle=0)
    # Both should give same confidence since frequency caps at 1.0 after 10 uses
    assert abs(compute_confidence(e10) - compute_confidence(e50)) < 0.01

def test_single_use_lower_than_10_uses():
    e1 = _entry(success_count=1, failure_count=0, days_idle=0)
    e10 = _entry(success_count=10, failure_count=0, days_idle=0)
    assert compute_confidence(e10) > compute_confidence(e1)


# ── Threshold invariants ──────────────────────────────────────────────────────

def test_confidence_never_exceeds_1():
    e = _entry(success_count=1000, failure_count=0, days_idle=0)
    assert compute_confidence(e) <= 1.0

def test_confidence_never_negative():
    e = _entry(success_count=0, failure_count=1000, days_idle=365)
    assert compute_confidence(e) >= 0.0

def test_auto_use_threshold_reachable():
    """A fix with 10 successes, 0 failures, used today must exceed 0.80 auto-use threshold."""
    e = _entry(success_count=10, failure_count=0, days_idle=0)
    assert compute_confidence(e) > 0.80

def test_eviction_threshold_reachable():
    """
    All-failure entries must be evictable below 0.20.
    With effective_freq = frequency_w * success_rate:
    compute_confidence(0, 10, 90):
      success_rate=0, recency≈0.41, frequency_w=1.0, effective_freq=0
      → 0 + 0.41*0.20 + 0 = 0.082 < 0.20 ✓
    """
    e = _entry(success_count=0, failure_count=10, days_idle=90)
    assert compute_confidence(e) <= 0.20


# ── Result precision ──────────────────────────────────────────────────────────

def test_result_rounded_to_4_decimal_places():
    e = _entry(success_count=3, failure_count=2, days_idle=5)
    conf = compute_confidence(e)
    assert conf == round(conf, 4)
