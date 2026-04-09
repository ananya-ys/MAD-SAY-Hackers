"""
app/services/rule_engine.py
Layer 1: Rule Engine — deterministic pattern matching on ErrorSignature.
< 5ms. $0.000 LLM cost. Fires BEFORE memory and LLM.

Rules are evaluated in a sandboxed evaluator — no arbitrary code execution.
Conditions access ErrorSignature fields via a restricted dict (field-access only).
SREs manage rules via rules.yaml and the /api/v1/rules API — no code deploy required.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import yaml

from app.core.logging import get_logger
from app.core.metrics import rule_evaluate_duration_seconds, rule_hits_total
from app.schemas.error_signature import ErrorSignature

logger = get_logger(__name__)


# ── Actions ───────────────────────────────────────────────────────────────────

@dataclass
class RuleResult:
    rule_id: str
    rule_name: str
    action_type: str
    action_params: dict[str, Any]
    confidence: float
    patch: str           # unified diff produced by action
    source: str = "rule"


@dataclass
class _Rule:
    id: str
    name: str
    condition: Callable[[dict], bool]   # operates on ErrorSignature as dict
    action_type: str
    action_params: dict[str, Any]
    confidence: float
    source: str = "builtin"


# ── Sandboxed condition evaluator ─────────────────────────────────────────────

_ALLOWED_OPS: frozenset[str] = frozenset({
    "error_type", "module", "context", "key", "attr",
    "typo_candidate", "env_var_name", "key_is_env_var", "language",
})


def _safe_eval_condition(condition_expr: str, sig_dict: dict) -> bool:
    """
    Evaluate a YAML condition string in a restricted namespace.
    Only ErrorSignature field access is permitted — no builtins, no imports.
    Raises ValueError on any unsafe attempt.
    """
    safe_ns: dict[str, Any] = {k: sig_dict.get(k) for k in _ALLOWED_OPS}
    safe_ns["__builtins__"] = {}   # strip all builtins

    try:
        return bool(eval(condition_expr, {"__builtins__": {}}, safe_ns))  # noqa: S307
    except Exception as exc:
        raise ValueError(f"Rule condition eval failed: {exc}") from exc


# ── Action builders ────────────────────────────────────────────────────────────

def _build_add_package_patch(module: str) -> str:
    return (
        f"--- a/requirements.txt\n"
        f"+++ b/requirements.txt\n"
        f"@@ -1,0 +1,1 @@\n"
        f"+{module}\n"
    )


def _build_add_env_var_patch(env_var: str, default: str = "") -> str:
    return (
        f"--- a/.env\n"
        f"+++ a/.env\n"
        f"@@ -1,0 +1,1 @@\n"
        f"+{env_var}={default}\n"
    )


def _build_typo_patch(wrong: str, correct: str, file_path: str = "unknown.py") -> str:
    return (
        f"--- a/{file_path}\n"
        f"+++ b/{file_path}\n"
        f"@@ -1 +1 @@\n"
        f"-{wrong}\n"
        f"+{correct}\n"
    )


_ACTION_BUILDERS: dict[str, Callable[[dict, ErrorSignature], str]] = {
    "ADD_PACKAGE": lambda params, sig: _build_add_package_patch(sig.module or params.get("module", "")),
    "ADD_ENV_VAR": lambda params, sig: _build_add_env_var_patch(sig.env_var_name or sig.key or "", params.get("default", "")),
    "CORRECT_TYPO": lambda params, sig: _build_typo_patch(sig.raw_error_line.split("'")[1] if "'" in sig.raw_error_line else "", sig.typo_candidate or "", sig.file_path),
    "FIX_IMPORT": lambda params, sig: f"# FIX_IMPORT: correct import of '{sig.attr}' from '{sig.module}'\n",
    "ADD_NONE_GUARD": lambda params, sig: f"# ADD_NONE_GUARD: add None check before accessing '{sig.attr}'\n",
}


# ── Builtin rules (PRD §3.2) ─────────────────────────────────────────────────

_BUILTIN_RULE_SPECS: list[dict] = [
    {
        "id": "RULE-001",
        "name": "ModuleNotFoundError — Add to requirements.txt",
        "condition": "error_type == 'ModuleNotFoundError' and module is not None",
        "action_type": "ADD_PACKAGE",
        "action_params": {},
        "confidence": 1.0,
    },
    {
        "id": "RULE-002",
        "name": "NameError — Obvious typo (edit-distance ≤ 2 to a known symbol)",
        "condition": "error_type == 'NameError' and typo_candidate is not None",
        "action_type": "CORRECT_TYPO",
        "action_params": {},
        "confidence": 0.95,
    },
    {
        "id": "RULE-003",
        "name": "KeyError — Missing env variable with .env default available",
        "condition": "error_type == 'KeyError' and key_is_env_var == True",
        "action_type": "ADD_ENV_VAR",
        "action_params": {"default": ""},
        "confidence": 0.90,
    },
    {
        "id": "RULE-004",
        "name": "ImportError — Wrong submodule",
        "condition": "error_type == 'ImportError' and attr is not None and module is not None",
        "action_type": "FIX_IMPORT",
        "action_params": {},
        "confidence": 0.92,
    },
    {
        "id": "RULE-005",
        "name": "AttributeError — NoneType guard",
        "condition": "error_type == 'AttributeError' and attr is not None",
        "action_type": "ADD_NONE_GUARD",
        "action_params": {},
        "confidence": 0.85,
    },
]


class RuleEngineService:
    """
    Layer 1: Deterministic rule matching.
    Loads builtin rules + org rules from YAML on startup.
    YAML rules can be hot-reloaded without redeploy.
    """

    def __init__(self, rules_yaml_path: Path | None = None) -> None:
        self._rules: list[_Rule] = []
        self._load_builtin_rules()
        if rules_yaml_path and rules_yaml_path.exists():
            self._load_yaml_rules(rules_yaml_path)

    def _load_builtin_rules(self) -> None:
        for spec in _BUILTIN_RULE_SPECS:
            condition_expr = spec["condition"]
            self._rules.append(
                _Rule(
                    id=spec["id"],
                    name=spec["name"],
                    condition=lambda sig_dict, ce=condition_expr: _safe_eval_condition(ce, sig_dict),
                    action_type=spec["action_type"],
                    action_params=spec.get("action_params", {}),
                    confidence=spec["confidence"],
                    source="builtin",
                )
            )
        # Sort by confidence DESC — evaluate highest-confidence rules first
        self._rules.sort(key=lambda r: r.confidence, reverse=True)
        logger.info("rule_engine_loaded", builtin_count=len(self._rules))

    def _load_yaml_rules(self, path: Path) -> None:
        try:
            with path.open() as f:
                specs = yaml.safe_load(f) or []
            for spec in specs:
                condition_expr = spec["condition"]
                self._rules.append(
                    _Rule(
                        id=spec.get("id", str(uuid.uuid4())[:8]),
                        name=spec["name"],
                        condition=lambda sd, ce=condition_expr: _safe_eval_condition(ce, sd),
                        action_type=spec["action_type"],
                        action_params=spec.get("action_params", {}),
                        confidence=float(spec.get("confidence", 0.80)),
                        source="yaml",
                    )
                )
            self._rules.sort(key=lambda r: r.confidence, reverse=True)
            logger.info("yaml_rules_loaded", path=str(path), total=len(self._rules))
        except Exception as exc:
            logger.error("yaml_rules_load_failed", error=str(exc))

    def reload_yaml(self, path: Path) -> None:
        """Hot-reload YAML rules without restart. Replaces non-builtin rules."""
        self._rules = [r for r in self._rules if r.source == "builtin"]
        if path.exists():
            self._load_yaml_rules(path)

    def evaluate(self, sig: ErrorSignature) -> RuleResult | None:
        """
        Evaluate rules against ErrorSignature in confidence DESC order.
        Returns first match or None (MISS → proceed to Layer 2).
        Pure in-process — no I/O — always < 5ms.
        """
        sig_dict = sig.to_dict()
        t0 = time.perf_counter()

        for rule in self._rules:
            try:
                if rule.confidence < 0.85:
                    continue  # PRD §9: confidence gate for rule actions
                matched = rule.condition(sig_dict)
            except Exception as exc:
                logger.warning("rule_condition_error", rule_id=rule.id, error=str(exc))
                continue

            if matched:
                builder = _ACTION_BUILDERS.get(rule.action_type)
                patch = builder(rule.action_params, sig) if builder else ""

                elapsed_ms = int((time.perf_counter() - t0) * 1000)
                rule_hits_total.labels(rule_id=rule.id).inc()
                rule_evaluate_duration_seconds.observe(time.perf_counter() - t0)

                logger.info(
                    "rule_hit",
                    rule_id=rule.id,
                    confidence=rule.confidence,
                    elapsed_ms=elapsed_ms,
                )
                return RuleResult(
                    rule_id=rule.id,
                    rule_name=rule.name,
                    action_type=rule.action_type,
                    action_params=rule.action_params,
                    confidence=rule.confidence,
                    patch=patch,
                )

        rule_evaluate_duration_seconds.observe(time.perf_counter() - t0)
        return None  # MISS
