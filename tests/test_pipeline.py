from pathlib import Path

from pipeline.inject import find_function_signature, inject_harness
from pipeline.translate import validate_violation_expr


def test_validate_good_expression():
    assert validate_violation_expr("result < a", ["a", "b"]) == "result < a"


def test_reject_statement():
    try:
        validate_violation_expr("if (result < a)", ["a"])
    except Exception:
        return
    raise AssertionError("statement was accepted")


def test_inject_harness():
    source = """
uint64_t max(uint64_t a, uint64_t b) {
  if (a > b)
    return a;
  return b;
}
"""
    patched, sig = inject_harness(source, "result < a", "max")
    assert sig.name == "max"
    assert "uint64_t main()" in patched
    assert "read(0, &a, 8);" in patched
    assert "result = max(a, b);" in patched
    assert "if (result < a)" in patched
