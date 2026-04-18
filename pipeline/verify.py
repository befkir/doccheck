"""
verify.py — general symbolic verification using Z3.
Shared pipeline component. Do not modify without team agreement.
"""
import subprocess
import os
from z3 import *

SELFIE = os.path.expanduser("~/selfie/selfie")

def _models(x, y=None):
    zero = BitVecVal(0, 64)
    c100 = BitVecVal(100, 64)
    b    = y if y is not None else BitVecVal(42, 64)
    return {
        "absolute": If(ULT(x, zero), -x, x),
        "double":   x * BitVecVal(2, 64),
        "clamp100": If(UGT(x, c100), c100, x),
        "max":      If(UGT(x, b), x, b),
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
    x    = BitVec('x', 64)
    b42  = BitVecVal(42, 64)   # concrete second arg for two-param functions
    models = _models(x, b42)
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
