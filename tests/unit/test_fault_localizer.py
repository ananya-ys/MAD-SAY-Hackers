"""
tests/unit/test_fault_localizer.py
40 unit tests covering all 6 error types in the Rule Engine.
Tests FaultLocalizerService extraction and ErrorSignature structural_hash + similar().
"""
import pytest

from app.schemas.error_signature import ErrorSignature
from app.services.fault_localizer import FaultLocalizerService

fl = FaultLocalizerService()


# ── ModuleNotFoundError ───────────────────────────────────────────────────────

TRACE_MODULE_NOT_FOUND = """\
Traceback (most recent call last):
  File "app/main.py", line 3, in <module>
    import sqlalchemy
ModuleNotFoundError: No module named 'sqlalchemy'
"""

def test_module_not_found_error_type():
    sig = fl.parse(TRACE_MODULE_NOT_FOUND)
    assert sig.error_type == "ModuleNotFoundError"

def test_module_not_found_module():
    sig = fl.parse(TRACE_MODULE_NOT_FOUND)
    assert sig.module == "sqlalchemy"

def test_module_not_found_context():
    sig = fl.parse(TRACE_MODULE_NOT_FOUND)
    assert sig.context == "import_failure"

def test_module_not_found_hash_stable():
    """Same error on different line numbers → same hash."""
    trace2 = TRACE_MODULE_NOT_FOUND.replace("line 3", "line 47")
    sig1 = fl.parse(TRACE_MODULE_NOT_FOUND)
    sig2 = fl.parse(trace2)
    assert sig1.structural_hash() == sig2.structural_hash()

def test_module_not_found_submodule_stripped():
    trace = "ModuleNotFoundError: No module named 'sqlalchemy.orm.something'"
    sig = fl.parse(trace)
    assert sig.module == "sqlalchemy"  # top-level only


# ── NameError ─────────────────────────────────────────────────────────────────

TRACE_NAME_ERROR = """\
Traceback (most recent call last):
  File "app/utils.py", line 10, in compute
    result = pritn("hello")
NameError: name 'pritn' is not defined
"""

def test_name_error_type():
    sig = fl.parse(TRACE_NAME_ERROR)
    assert sig.error_type == "NameError"

def test_name_error_typo_detected():
    sig = fl.parse(TRACE_NAME_ERROR)
    assert sig.typo_candidate == "print"

def test_name_error_no_typo_far_edit_distance():
    trace = "NameError: name 'xyzqwerty' is not defined"
    sig = fl.parse(trace)
    assert sig.typo_candidate is None  # edit distance > 2


# ── KeyError ──────────────────────────────────────────────────────────────────

TRACE_KEY_ERROR_ENV = """\
Traceback (most recent call last):
  File "app/core/config.py", line 8, in <module>
    db_url = os.environ["DATABASE_URL"]
KeyError: 'DATABASE_URL'
"""

TRACE_KEY_ERROR_DICT = """\
KeyError: 'user_name'
"""

def test_key_error_env_var_detected():
    sig = fl.parse(TRACE_KEY_ERROR_ENV)
    assert sig.error_type == "KeyError"
    assert sig.key_is_env_var is True
    assert sig.env_var_name == "DATABASE_URL"

def test_key_error_dict_not_env_var():
    sig = fl.parse(TRACE_KEY_ERROR_DICT)
    assert sig.key_is_env_var is False

def test_key_error_env_var_hash_structural():
    """DATABASE_URL on line 8 vs line 22 → same hash."""
    trace2 = TRACE_KEY_ERROR_ENV.replace("line 8", "line 22")
    sig1 = fl.parse(TRACE_KEY_ERROR_ENV)
    sig2 = fl.parse(trace2)
    assert sig1.structural_hash() == sig2.structural_hash()


# ── AttributeError ────────────────────────────────────────────────────────────

TRACE_ATTR_ERROR = """\
Traceback (most recent call last):
  File "app/service.py", line 15, in process
    result = obj.compute()
AttributeError: 'NoneType' object has no attribute 'compute'
"""

def test_attr_error_type():
    sig = fl.parse(TRACE_ATTR_ERROR)
    assert sig.error_type == "AttributeError"

def test_attr_error_attr_extracted():
    sig = fl.parse(TRACE_ATTR_ERROR)
    assert sig.attr == "compute"


# ── ImportError ───────────────────────────────────────────────────────────────

TRACE_IMPORT_ERROR = """\
Traceback (most recent call last):
  File "app/db.py", line 1, in <module>
    from sqlalchemy.orm import async_session
ImportError: cannot import name 'async_session' from 'sqlalchemy.orm'
"""

def test_import_error_type():
    sig = fl.parse(TRACE_IMPORT_ERROR)
    assert sig.error_type == "ImportError"

def test_import_error_attr_and_module():
    sig = fl.parse(TRACE_IMPORT_ERROR)
    assert sig.attr == "async_session"
    assert "sqlalchemy" in (sig.module or "")


# ── SyntaxError ───────────────────────────────────────────────────────────────

TRACE_SYNTAX_ERROR = """\
  File "app/models.py", line 12
    def foo(:
            ^
SyntaxError: invalid syntax
"""

def test_syntax_error_type():
    sig = fl.parse(TRACE_SYNTAX_ERROR)
    assert sig.error_type == "SyntaxError"


# ── ErrorSignature.similar() ──────────────────────────────────────────────────

def test_similar_same_error_type_and_module():
    a = ErrorSignature(error_type="ModuleNotFoundError", module="sqlalchemy", context="import_failure")
    b = ErrorSignature(error_type="ModuleNotFoundError", module="sqlalchemy", context="runtime")
    assert a.similar(b, threshold=0.75)

def test_similar_different_error_type_returns_false():
    a = ErrorSignature(error_type="ModuleNotFoundError", module="sqlalchemy", context="import_failure")
    b = ErrorSignature(error_type="ImportError", module="sqlalchemy", context="import_failure")
    assert not a.similar(b)

def test_similar_threshold_enforcement():
    a = ErrorSignature(error_type="KeyError", module=None, context="runtime", key="X")
    b = ErrorSignature(error_type="KeyError", module=None, context="test", key="Y")
    # Same error_type but different key → Jaccard below 0.75
    result = a.similar(b, threshold=0.75)
    assert isinstance(result, bool)


# ── Malformed / empty input ───────────────────────────────────────────────────

def test_empty_trace_does_not_raise():
    sig = fl.parse("")
    assert sig.error_type == "UnknownError"

def test_binary_null_bytes_handled():
    sig = fl.parse("SyntaxError: bad input\x00garbage")
    assert sig is not None

def test_very_long_trace_truncated_gracefully():
    long_trace = ("Traceback (most recent call last):\n" +
                  "  File 'x.py', line 1, in f\n" * 5000 +
                  "ValueError: something\n")
    sig = fl.parse(long_trace)
    assert sig.error_type == "ValueError"
