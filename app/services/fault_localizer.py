"""
app/services/fault_localizer.py
FaultLocalizerService: parse raw Python stderr → structured ErrorSignature.
Extracts error_type, module, context, key, attr, typo_candidate fields.
All repo content treated as untrusted. Inputs length-capped before any LLM use.
"""
from __future__ import annotations

import re

import Levenshtein

from app.core.logging import get_logger
from app.schemas.error_signature import ErrorSignature

logger = get_logger(__name__)

# ── Regex patterns ────────────────────────────────────────────────────────────

_ERROR_LINE = re.compile(
    r"^(?P<error_type>[A-Za-z][A-Za-z0-9_]*(?:Error|Exception|Warning|Interrupt|Exit))"
    r"(?::\s*(?P<message>.*))?$",
    re.MULTILINE,
)
_MODULE_NOT_FOUND = re.compile(r"No module named ['\"]?([a-zA-Z0-9_\-.]+)['\"]?")
_NAME_ERROR = re.compile(r"name ['\"]([^'\"]+)['\"] is not defined")
_KEY_ERROR = re.compile(r"KeyError:\s*['\"]?([^'\"]+)['\"]?")
_ATTR_ERROR = re.compile(r"'([A-Za-z0-9_]+)' object has no attribute ['\"]([^'\"]+)['\"]")
_IMPORT_ERROR = re.compile(r"cannot import name ['\"]([^'\"]+)['\"] from ['\"]([^'\"]+)['\"]")
_SYNTAX_ERROR_LINE = re.compile(r"SyntaxError: (.+)")
_FILE_LINE = re.compile(r'File "([^"]+)", line (\d+)')
_IMPORT_CTX = re.compile(r"import\s+\w+|from\s+\w+\s+import")

# Python builtins for NameError typo detection
_PYTHON_BUILTINS: list[str] = [
    "print", "len", "range", "list", "dict", "set", "tuple", "str", "int", "float",
    "bool", "type", "isinstance", "issubclass", "super", "object", "None", "True",
    "False", "open", "input", "sorted", "enumerate", "zip", "map", "filter",
    "any", "all", "sum", "min", "max", "abs", "round", "hasattr", "getattr",
    "setattr", "delattr", "vars", "dir", "id", "hash", "repr", "format",
    "staticmethod", "classmethod", "property",
]


class FaultLocalizerService:
    """
    Parse Python stderr into a structured ErrorSignature.
    Called ONCE per repair session before the layer stack runs.
    """

    def parse(self, stack_trace: str) -> ErrorSignature:
        """
        Main entry point. Returns ErrorSignature regardless of parse quality.
        Falls back to minimal signature on any extraction failure.
        """
        try:
            return self._extract(stack_trace)
        except Exception as exc:
            logger.warning("fault_localizer_parse_error", error=str(exc))
            return ErrorSignature(
                error_type="UnknownError",
                module=None,
                context="runtime",
            )

    def _extract(self, trace: str) -> ErrorSignature:
        # ── 1. Find error type and message ────────────────────────────────
        error_type = "UnknownError"
        message = ""

        # Walk lines in reverse — last error line is the root cause
        for line in reversed(trace.splitlines()):
            m = _ERROR_LINE.match(line.strip())
            if m:
                error_type = m.group("error_type")
                message = (m.group("message") or "").strip()
                break

        # ── 2. Extract file + line for context (not used in hash) ─────────
        file_path = ""
        line_number: int | None = None
        for m in _FILE_LINE.finditer(trace):
            file_path = m.group(1)
            line_number = int(m.group(2))

        # ── 3. Determine context ──────────────────────────────────────────
        context = self._infer_context(trace, file_path, error_type)

        # ── 4. Error-type specific extraction ─────────────────────────────
        module: str | None = None
        key: str | None = None
        attr: str | None = None
        typo_candidate: str | None = None

        if error_type == "ModuleNotFoundError":
            m2 = _MODULE_NOT_FOUND.search(trace)
            if m2:
                module = m2.group(1).split(".")[0]  # top-level package only

        elif error_type == "ImportError":
            m2 = _IMPORT_ERROR.search(trace)
            if m2:
                attr = m2.group(1)   # wrong name
                module = m2.group(2)  # source module

        elif error_type == "NameError":
            m2 = _NAME_ERROR.search(trace)
            if m2:
                undefined = m2.group(1)
                candidate = self._nearest_symbol(undefined, _PYTHON_BUILTINS)
                if candidate and Levenshtein.distance(undefined, candidate) <= 2:
                    typo_candidate = candidate

        elif error_type == "KeyError":
            m2 = _KEY_ERROR.search(message or trace)
            if m2:
                key = m2.group(1).strip()

        elif error_type == "AttributeError":
            m2 = _ATTR_ERROR.search(trace)
            if m2:
                attr = m2.group(2)

        return ErrorSignature(
            error_type=error_type,
            module=module,
            context=context,
            key=key,
            attr=attr,
            typo_candidate=typo_candidate,
            raw_error_line=message,
            file_path=file_path,
            line_number=line_number,
        )

    def _infer_context(self, trace: str, file_path: str, error_type: str) -> str:
        if "test_" in file_path or "/tests/" in file_path or "pytest" in trace:
            return "test"
        if _IMPORT_CTX.search(trace) or error_type in ("ModuleNotFoundError", "ImportError"):
            return "import_failure"
        if "startup" in trace.lower() or "lifespan" in trace.lower():
            return "startup"
        return "runtime"

    def _nearest_symbol(self, name: str, candidates: list[str]) -> str | None:
        if not candidates:
            return None
        return min(candidates, key=lambda c: Levenshtein.distance(name, c))
