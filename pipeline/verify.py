"""
verify.py — compiles patched C* and verifies the claim with Z3.
Shared across all experiment branches. Do not modify without team agreement.
"""
import subprocess
import os
from z3 import *

SELFIE  = os.path.expanduser("~/selfie/selfie")

def compile_source(source: str) -> tuple[bool, str]:
    """
    Compile C* source with starc.
    Returns (success, compiler_output).
    """
    with open("/tmp/patched.c", "w") as f:
        f.write(source)
    result = subprocess.run(
        [SELFIE, "-c", "/tmp/patched.c", "-o", "/tmp/patched.bin"],
        capture_output=True, text=True
    )
    if "syntax error" in result.stdout:
        return False, result.stdout
    return True, result.stdout

def verify_with_z3(check_statement: str, function_source: str) -> dict:
    """
    Use Z3 to check whether the violation condition is satisfiable.
    Returns dict with keys: verdict, witness, error
      verdict: "VERIFIED" | "FALSIFIED" | "UNKNOWN"
      witness: concrete input value if FALSIFIED, else None
      error:   error message if UNKNOWN, else None
    """
    x    = BitVec('x', 64)
    zero = BitVecVal(0, 64)

    # symbolic execution of absolute(x) — unsigned 64-bit
    result_expr = If(ULT(x, zero), -x, x)

    conditions = {
        "result < 0"  : ULT(result_expr, zero),
        "result <= 0" : ULE(result_expr, zero),
        "result >= x" : Not(ULT(result_expr, x)),
        "result > x"  : ULT(x, result_expr),
        "result != x" : result_expr != x,
        "result == x" : result_expr == x,
        "result != 0" : result_expr != zero,
        "result == 0" : result_expr == zero,
    }

    violation = None
    for pattern, expr in conditions.items():
        if pattern in check_statement:
            violation = expr
            break

    if violation is None:
        return {"verdict": "UNKNOWN", "witness": None,
                "error": f"Cannot parse condition: {check_statement}"}

    solver = Solver()
    solver.add(violation)
    outcome = solver.check()

    if outcome == sat:
        val = solver.model().eval(x, model_completion=True)
        witness = val.as_long() if hasattr(val, 'as_long') else str(val)
        return {"verdict": "FALSIFIED", "witness": witness, "error": None}
    elif outcome == unsat:
        return {"verdict": "VERIFIED", "witness": None, "error": None}
    else:
        return {"verdict": "UNKNOWN", "witness": None, "error": "Z3 returned unknown"}
