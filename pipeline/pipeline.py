"""
pipeline.py — main orchestrator for DocCheck.
Usage: python3 pipeline/pipeline.py <function.c> "<claim>"
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.translate import translate_claim
from pipeline.inject    import inject_check
from pipeline.verify    import compile_source, verify_with_z3

def check(function_source, claim, function_name):
    print(f"\n{'='*60}")
    print(f"Function: {function_name}")
    print(f"Claim   : {claim}")

    check_stmt = translate_claim(function_source, claim)
    print(f"Check   : {check_stmt}")

    try:
        patched = inject_check(function_source, check_stmt)
    except ValueError as e:
        print(f"Verdict : ERROR — {e}")
        return {}

    ok, compiler_out = compile_source(patched)
    if not ok:
        print(f"Verdict : COMPILE ERROR")
        print(f"Detail  : {compiler_out[:300]}")
        return {}
    print(f"Compile : OK")

    result = verify_with_z3(check_stmt, function_name)

    if result["verdict"] == "VERIFIED":
        print(f"Verdict : VERIFIED ✓ — proved for ALL inputs (Z3: UNSAT)")
    elif result["verdict"] == "FALSIFIED":
        w = result["witness"]
        print(f"Verdict : FALSIFIED ✗ — claim broken by input x = {w}")
    else:
        print(f"Verdict : UNKNOWN — {result['error']}")

    return result

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 pipeline/pipeline.py <function.c> \"<claim>\"")
        sys.exit(1)
    path  = sys.argv[1]
    fname = os.path.splitext(os.path.basename(path))[0]
    with open(path) as f:
        source = f.read()
    check(source, sys.argv[2], fname)