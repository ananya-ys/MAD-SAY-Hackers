"""
app/schemas/error_signature.py
Structural ErrorSignature — identity based on WHAT the error is, not WHERE.
File-rename resilient. Enables fuzzy matching across codebases.
Replaces the brittle v3 hash(error_type + file + line).
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field


@dataclass
class ErrorSignature:
    """
    Structured identity for a Python runtime error.
    Hash on semantic fields — never on line number or filename.
    """
    error_type: str              # 'ModuleNotFoundError'
    module: str | None           # 'sqlalchemy' (extracted by FaultLocalizer)
    context: str                 # 'import_failure' | 'runtime' | 'startup' | 'test'
    language: str = "python"

    # Optional structural fields — populated when extractable
    key: str | None = None          # for KeyError: the missing key name
    attr: str | None = None         # for AttributeError: the missing attribute
    typo_candidate: str | None = None  # for NameError: nearest symbol by edit-distance
    env_var_name: str | None = None    # for KeyError on os.environ: the env var name
    key_is_env_var: bool = False       # True if KeyError key matches ENV_VAR pattern

    # Populated by FaultLocalizer for context — not used in hash
    raw_error_line: str = ""
    file_path: str = ""
    line_number: int | None = None

    # ── ENV_VAR detection ────────────────────────────────────────────────────
    _ENV_VAR_PATTERN: re.Pattern = field(
        default=re.compile(r'^[A-Z][A-Z0-9_]{2,}$'),
        init=False,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        if self.key and self._ENV_VAR_PATTERN.match(self.key):
            self.key_is_env_var = True
            self.env_var_name = self.key

    # ── Identity ─────────────────────────────────────────────────────────────
    def structural_hash(self) -> str:
        """
        Hash on WHAT the error is, not WHERE it is.
        Same bug across 3 files = same hash. Line number irrelevant.
        """
        fields = f"{self.error_type}:{self.module}:{self.context}:{self.key}:{self.attr}"
        return hashlib.sha256(fields.encode()).hexdigest()[:16]

    def similar(self, other: ErrorSignature, threshold: float = 0.75) -> bool:
        """
        Jaccard similarity on non-None structural fields.
        Same error_type = strong signal.
        Matching module = near-certain match.
        Used by MemoryService for fuzzy matching beyond exact hash.
        """
        if self.error_type != other.error_type:
            return False  # Hard requirement: same error class

        self_fields = self._non_none_fields()
        other_fields = other._non_none_fields()

        if not self_fields or not other_fields:
            return False

        intersection = self_fields & other_fields
        union = self_fields | other_fields

        if not union:
            return False

        score = len(intersection) / len(union)
        return score >= threshold

    def _non_none_fields(self) -> set[str]:
        """
        Return set of 'field=value' strings for structural (non-positional) fields.
        context is EXCLUDED: it is derived from call-site (import_failure, runtime, test)
        and must not dilute similarity between the same error in different execution phases.
        error_type + module + key + attr + env_var_name are the true structural identity.
        """
        result: set[str] = set()
        for f in ("error_type", "module", "key", "attr", "env_var_name"):
            val = getattr(self, f)
            if val is not None:
                result.add(f"{f}={val}")
        return result

    def to_dict(self) -> dict:
        """Serialise for JSONB storage. Excludes non-serialisable fields."""
        d = asdict(self)
        d.pop("_ENV_VAR_PATTERN", None)
        return d

    @classmethod
    def from_dict(cls, data: dict) -> ErrorSignature:
        """Deserialise from JSONB storage."""
        data.pop("_ENV_VAR_PATTERN", None)
        known = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)
