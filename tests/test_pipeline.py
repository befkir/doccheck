"""Unit tests for DocCheck pipeline stages."""
from pipeline.inject import find_function_signature, inject_harness
from pipeline.translate import validate_violation_expr


# ── translate tests ────────────────────────────────────────────────────────────

def test_validate_good_expression():
    assert validate_violation_expr("result < x", ["x"]) == "result < x"


def test_validate_two_param_expression():
    assert validate_violation_expr("result < x", ["x", "b"]) == "result < x"


def test_reject_statement():
    try:
        validate_violation_expr("if (result < x)", ["x"])
    except Exception:
        return
    raise AssertionError("statement was accepted")


def test_reject_forbidden_keyword():
    try:
        validate_violation_expr("result != uint64_t", ["x"])
    except Exception:
        return
    raise AssertionError("forbidden keyword was accepted")


def test_reject_unknown_identifier():
    try:
        validate_violation_expr("result < z", ["x"])
    except Exception:
        return
    raise AssertionError("unknown identifier was accepted")


# ── inject tests ───────────────────────────────────────────────────────────────

# Standard single-param function (the most common shape in the benchmark)
SINGLE_PARAM_SOURCE = """\
uint64_t absolute(uint64_t x) {
  uint64_t result;
  if (x < 0)
    result = x * -1;
  else
    result = x;
  return result;
}
"""

# Two-param function
TWO_PARAM_SOURCE = """\
uint64_t max(uint64_t x, uint64_t b) {
  uint64_t result;
  if (x > b)
    result = x;
  else
    result = b;
  return result;
}
"""


def test_inject_single_param_signature():
    _, sig = inject_harness(SINGLE_PARAM_SOURCE, "result < 0", "absolute")
    assert sig.name == "absolute"
    assert sig.param_names == ["x"]


def test_inject_two_param_signature():
    _, sig = inject_harness(TWO_PARAM_SOURCE, "result < x", "max")
    assert sig.name == "max"
    assert sig.param_names == ["x", "b"]


def test_inject_check_inside_function():
    """Violation check must appear INSIDE the function, before return result;"""
    patched, _ = inject_harness(SINGLE_PARAM_SOURCE, "result < 0", "absolute")
    # The check must be inside the function body — before 'return result;'
    assert "if (result < 0)" in patched
    assert "exit(1);" in patched
    # exit(1) must come before return result
    assert patched.index("exit(1);") < patched.index("return result;")


def test_inject_main_harness_present():
    patched, _ = inject_harness(SINGLE_PARAM_SOURCE, "result < 0", "absolute")
    assert "uint64_t main()" in patched


def test_inject_main_uses_malloc_and_read():
    """C* symbolic inputs use malloc + read(0, ptr, 8), not address-of (&x)."""
    patched, _ = inject_harness(SINGLE_PARAM_SOURCE, "result < 0", "absolute")
    assert "malloc(8)" in patched
    assert "read(0, x_ptr, 8)" in patched
    # address-of (&) is forbidden in C*
    assert "&x" not in patched


def test_inject_main_calls_function():
    patched, _ = inject_harness(SINGLE_PARAM_SOURCE, "result < 0", "absolute")
    assert "absolute(x)" in patched


def test_inject_main_exits_cleanly():
    """main() exits with exit(0) on the normal path (violation exits via exit(1) inside function)."""
    patched, _ = inject_harness(SINGLE_PARAM_SOURCE, "result < 0", "absolute")
    assert "exit(0);" in patched


def test_inject_two_param_malloc_and_read():
    patched, _ = inject_harness(TWO_PARAM_SOURCE, "result < x", "max")
    assert "malloc(8)" in patched
    assert "read(0, x_ptr, 8)" in patched
    assert "read(0, b_ptr, 8)" in patched
    assert "max(x, b)" in patched


def test_inject_no_duplicate_main():
    """Source with an existing main() must not produce two main() definitions."""
    source_with_main = TWO_PARAM_SOURCE + "\nuint64_t main() { return 0; }\n"
    patched, _ = inject_harness(source_with_main, "result < x", "max")
    assert patched.count("uint64_t main()") == 1
