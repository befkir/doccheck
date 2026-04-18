"""
verify.py — general symbolic verification using Z3.
Shared pipeline component. Do not modify without team agreement.
"""
import subprocess
import os
from z3 import *

SELFIE = os.path.expanduser("~/selfie/selfie")

# ── Function model registry ──────────────────────────────
# Add one entry per benchmark function.
# Each entry: function_name → lambda x: Z3 expression for return value
# x is a 64-bit unsigned bitvector (uint64_t in C*)

def _models(x):
    zero   = BitVecVal(0, 64)
    c100   = BitVecVal(100, 64)
    return {
        "absolute": If(ULT(x, zero), -x, x),
        "double":   x * BitVecVal(2, 64),
        "clamp100": If(UGT(x, c100), c100, x),
    }

# ── Condition registry ────────────────────────────────────
# Maps condition string pattern → Z3 violation expression

def _violation(check_statement: str, result_expr, x) -> BoolRef | None:
    zero = BitVecVal(0, 64)
    conditions = {
        "result < 0"  : ULT(result_expr, zero),
        "result <= 0" : ULE(result_expr, zero),
        "result >= x" : UGE(result_expr, x),
        "result > x"  : UGT(result_expr, x),
        "result != x" : result_expr != x,
        "result == x" : result_expr == x,
        "result != 0" : result_expr != zero,
        "result == 0" : result_expr == zero,
        "result > 100": UGT(result_expr, BitVecVal(100, 64)),
    }
    for pattern, expr in conditions.items():
        if pattern in check_statement:
            return expr
    return None

# ── Main verification function ────────────────────────────

def compile_source(source: str) -> tuple:
    with open("/tmp/patched.c", "w") as f:
        f.write(source)
    result = subprocess.run(
        [SELFIE, "-c", "/tmp/patched.c", "-o", "/tmp/patched.bin"],
        capture_output=True, text=True
    )
    if "syntax error" in result.stdout:
        return False, result.stdout
    return True, result.stdout

def verify_with_z3(check_statement: str, function_name: str) -> dict:
    """
    Symbolically verify a claim against a named function.
    Args:
        check_statement : e.g. "if (result < 0) { return 1; }"
        function_name   : e.g. "absolute" (must exist in model registry)
    Returns:
        dict with keys: verdict, witness, error
    """
    x = BitVec('x', 64)

    models = _models(x)
    if function_name not in models:
        return {
            "verdict": "UNKNOWN",
            "witness": None,
            "error": f"No Z3 model registered for function '{function_name}'. Add it to verify.py."
        }

    result_expr = models[function_name]
    violation   = _violation(check_statement, result_expr, x)

    if violation is None:
        return {
            "verdict": "UNKNOWN",
            "witness": None,
            "error": f"Cannot parse condition from: {check_statement}"
        }

    solver = Solver()
    solver.add(violation)
    outcome = solver.check()

    if outcome == sat:
        val     = solver.model().eval(x, model_completion=True)
        witness = val.as_long() if hasattr(val, 'as_long') else str(val)
        return {"verdict": "FALSIFIED", "witness": witness, "error": None}
    elif outcome == unsat:
        return {"verdict": "VERIFIED", "witness": None, "error": None}
    else:
        return {"verdict": "UNKNOWN", "witness": None, "error": "Z3 returned unknown"}
"""
verify.py — general symbolic verification using Z3.
Shared pipeline component. Do not modify without team agreement.
"""
import subprocess
import os
from z3 import *

SELFIE = os.path.expanduser("~/selfie/selfie")

def _models(x):
    zero = BitVecVal(0, 64)
    c100 = BitVecVal(100, 64)
    return {
        "absolute": If(ULT(x, zero), -x, x),
        "double":   x * BitVecVal(2, 64),
        "clamp100": If(UGT(x, c100), c100, x),
    }

def _violation(check_statement, result_expr, x):
    zero = BitVecVal(0, 64)
    conditions = {
        "result < 0"  : ULT(result_expr, zero),
        "result <= 0" : ULE(result_expr, zero),
        "result >= x" : UGE(result_expr, x),
        "result > x"  : UGT(result_expr, x),
        "result != x" : result_expr != x,
        "result == x" : result_expr == x,
        "result != 0" : result_expr != zero,
        "result == 0" : result_expr == zero,
        "result > 100": UGT(result_expr, BitVecVal(100, 64)),
    }
    for pattern, expr in conditions.items():
        if pattern in check_statement:
            return expr
    return None

def compile_source(source):
    with open("/tmp/patched.c", "w") as f:
        f.write(source)
    result = subprocess.run(
        [SELFIE, "-c", "/tmp/patched.c", "-o", "/tmp/patched.bin"],
        capture_output=True, text=True
    )
    if "syntax error" in result.stdout:
        return False, result.stdout
    return True, result.stdout

def verify_with_z3(check_statement, function_name):
    x = BitVec('x', 64)
    models = _models(x)
    if function_name not in models:
        return {
            "verdict": "UNKNOWN",
            "witness": None,
            "error": f"No Z3 model for '{function_name}'. Add it to verify.py."
        }
    result_expr = models[function_name]
    violation   = _violation(check_statement, result_expr, x)
    if violation is None:
        return {
            "verdict": "UNKNOWN",
            "witness": None,
            "error": f"Cannot parse condition: {check_statement}"
        }
    solver = Solver()
    solver.add(violation)
    outcome = solver.check()
    if outcome == sat:
        val     = solver.model().eval(x, model_completion=True)
        witness = val.as_long() if hasattr(val, 'as_long') else str(val)
        return {"verdict": "FALSIFIED", "witness": witness, "error": None}
    elif outcome == unsat:
        return {"verdict": "VERIFIED", "witness": None, "error": None}
    else:
        return {"verdict": "UNKNOWN", "witness": None, "error": "Z3 returned unknown"}
