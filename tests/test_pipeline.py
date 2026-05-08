"""
test_pipeline.py — unit and integration tests for the DocCheck pipeline.

Run with:
    pytest tests/test_pipeline.py -v
"""

import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.inject import inject_check, _parse_signature, _build_harness, _strip_existing_main
from pipeline.verify import _parse_bitme_output, compile_source


# ===========================================================================
# inject.py tests
# ===========================================================================

ABSOLUTE_SRC = """\
uint64_t absolute(uint64_t x) {
  uint64_t result;
  if (x < 0) {
    result = -x;
  } else {
    result = x;
  }
  return result;
}

uint64_t main() {
  uint64_t* x;
  x = malloc(sizeof(uint64_t));
  *x = 0;
  read(0, x, 8);
  absolute(*x);
  return 0;
}
"""

MAX_SRC = """\
uint64_t max(uint64_t x, uint64_t b) {
  uint64_t result;
  if (x > b) {
    result = x;
  } else {
    result = b;
  }
  return result;
}

uint64_t main() {
  uint64_t* x;
  x = malloc(sizeof(uint64_t));
  *x = 0;
  read(0, x, 8);
  max(*x, 42);
  return 0;
}
"""


class TestParseSignature:
    def test_single_param(self):
        name, params = _parse_signature(ABSOLUTE_SRC)
        assert name == "absolute"
        assert len(params) == 1
        assert params[0] == ("uint64_t", "x")

    def test_two_params(self):
        name, params = _parse_signature(MAX_SRC)
        assert name == "max"
        assert len(params) == 2
        assert params[0] == ("uint64_t", "x")
        assert params[1] == ("uint64_t", "b")

    def test_no_function_raises(self):
        with pytest.raises(ValueError, match="Could not find"):
            _parse_signature("uint64_t main() { return 0; }")


class TestBuildHarness:
    def test_single_param_harness(self):
        harness = _build_harness("absolute", [("uint64_t", "x")])
        assert "uint64_t main()" in harness
        assert "x_ptr = malloc" in harness
        assert "read(0, x_ptr, 8)" in harness
        assert "absolute(*x_ptr)" in harness

    def test_two_param_harness(self):
        harness = _build_harness("max", [("uint64_t", "x"), ("uint64_t", "b")])
        assert "x_ptr = malloc" in harness
        assert "b_ptr = malloc" in harness
        assert "read(0, x_ptr, 8)" in harness
        assert "read(0, b_ptr, 8)" in harness
        assert "max(*x_ptr, *b_ptr)" in harness


class TestStripExistingMain:
    def test_strips_main(self):
        stripped = _strip_existing_main(ABSOLUTE_SRC)
        assert "uint64_t main()" not in stripped
        assert "uint64_t absolute" in stripped

    def test_no_main_unchanged(self):
        src = "uint64_t absolute(uint64_t x) { return x; }"
        assert _strip_existing_main(src) == src


class TestInjectCheck:
    def test_check_injected_before_return(self):
        patched = inject_check(ABSOLUTE_SRC, "if (result < 0) { return 1; }")
        assert "if (result < 0) { return 1; }" in patched
        # Check appears before return result;
        idx_check  = patched.index("if (result < 0)")
        idx_return = patched.index("return result;")
        assert idx_check < idx_return

    def test_new_harness_replaces_old_main(self):
        patched = inject_check(ABSOLUTE_SRC, "if (result < 0) { return 1; }")
        # Old harness called absolute(*x); new one calls absolute(*x_ptr)
        assert "absolute(*x_ptr)" in patched

    def test_missing_return_result_raises(self):
        bad_src = "uint64_t f(uint64_t x) { return x; }"
        with pytest.raises(ValueError, match="return result"):
            inject_check(bad_src, "if (result < 0) { return 1; }")

    def test_two_param_function(self):
        patched = inject_check(MAX_SRC, "if (result < 0) { return 1; }")
        assert "max(*x_ptr, *b_ptr)" in patched
        assert "if (result < 0) { return 1; }" in patched

    def test_only_first_return_result_replaced(self):
        """Ensure only the function body return is patched, not duplicates."""
        src = ABSOLUTE_SRC
        patched = inject_check(src, "if (result < 0) { return 1; }")
        # Should appear exactly once
        assert patched.count("if (result < 0) { return 1; }") == 1


# ===========================================================================
# verify.py tests — _parse_bitme_output
# ===========================================================================

class TestParseBitmeOutput:
    def test_unsat_gives_verified(self):
        result = _parse_bitme_output("unsat\n")
        assert result["verdict"] == "VERIFIED"
        assert result["witness"] is None
        assert result["error"] is None

    def test_sat_gives_falsified(self):
        result = _parse_bitme_output("sat\n")
        assert result["verdict"] == "FALSIFIED"

    def test_sat_with_witness_line(self):
        output = "sat\n1 5 input_x\n"
        result = _parse_bitme_output(output)
        assert result["verdict"] == "FALSIFIED"
        assert result["witness"] == 5

    def test_sat_with_hex_witness(self):
        output = "sat\n1 0x0a input_x\n"
        result = _parse_bitme_output(output)
        assert result["verdict"] == "FALSIFIED"
        assert result["witness"] == 10

    def test_unknown(self):
        result = _parse_bitme_output("unknown\n")
        assert result["verdict"] == "UNKNOWN"
        assert result["error"] is not None

    def test_empty_output(self):
        result = _parse_bitme_output("")
        assert result["verdict"] == "UNKNOWN"


# ===========================================================================
# translate.py tests — mock LLM calls
# ===========================================================================

class TestTranslateClaim:
    def _mock_ollama_response(self, stmt: str):
        """Return a mock urllib response that yields an Ollama-style JSON body."""
        body = json.dumps({"response": stmt}).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = body
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        return mock_resp

    def test_ollama_backend(self):
        from pipeline import translate as t_module
        with patch.dict(os.environ, {"DOCCHECK_BACKEND": "ollama"}):
            with patch("urllib.request.urlopen",
                       return_value=self._mock_ollama_response(
                           "if (result < 0) { return 1; }")):
                result = t_module.translate_claim("uint64_t f(uint64_t x){}", "never negative")
        assert result == "if (result < 0) { return 1; }"

    def test_unknown_backend_raises(self):
        from pipeline import translate as t_module
        with patch.dict(os.environ, {"DOCCHECK_BACKEND": "nonexistent"}):
            with pytest.raises(KeyError, match="Unknown backend"):
                t_module.translate_claim("src", "claim")

    def test_openrouter_missing_key_raises(self):
        from pipeline import translate as t_module
        env = {"DOCCHECK_BACKEND": "openrouter", "OPENROUTER_API_KEY": ""}
        with patch.dict(os.environ, env):
            with pytest.raises(EnvironmentError, match="OPENROUTER_API_KEY"):
                t_module.translate_claim("src", "claim")

    def test_claude_missing_key_raises(self):
        from pipeline import translate as t_module
        env = {"DOCCHECK_BACKEND": "claude", "ANTHROPIC_API_KEY": ""}
        with patch.dict(os.environ, env):
            with pytest.raises(EnvironmentError, match="ANTHROPIC_API_KEY"):
                t_module.translate_claim("src", "claim")

    def test_normalise_pointer_deref(self):
        """LLM sometimes writes *x — should be normalised to x."""
        from pipeline import translate as t_module
        with patch.dict(os.environ, {"DOCCHECK_BACKEND": "ollama"}):
            with patch("urllib.request.urlopen",
                       return_value=self._mock_ollama_response(
                           "if (result >= *x) { return 1; }")):
                result = t_module.translate_claim("uint64_t f(uint64_t x){}", "claim")
        assert "*x" not in result
        assert "result >= x" in result


# ===========================================================================
# Integration smoke test (skipped if toolchain not installed)
# ===========================================================================

SELFIE_INSTALLED = os.path.exists(os.path.expanduser("~/selfie/selfie"))

@pytest.mark.skipif(not SELFIE_INSTALLED, reason="Selfie toolchain not installed")
class TestCompileSmoke:
    def test_compile_valid_source(self):
        src = """\
uint64_t identity(uint64_t x) {
  uint64_t result;
  result = x;
  if (result != x) { return 1; }
  return result;
}

uint64_t main() {
  uint64_t* x_ptr;
  x_ptr = malloc(sizeof(uint64_t));
  *x_ptr = 0;
  read(0, x_ptr, 8);
  uint64_t result;
  result = identity(*x_ptr);
  return 0;
}
"""
        ok, out = compile_source(src)
        assert ok, f"Compile failed:\n{out}"

    def test_compile_invalid_source(self):
        ok, _ = compile_source("this is not valid C*;")
        assert not ok