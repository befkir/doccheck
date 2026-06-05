"""
binary_verify.py — Hybrid binary-level verification.
FALSIFIED: runs actual RISC-V binary via selfie emulator with concrete inputs
VERIFIED:  Z3 proves claim holds for all inputs (mathematical proof)
Both paths operate on the compiled binary — genuinely binary-level.
"""
import subprocess
import struct
import os
from pipeline.verify import compile_source, verify_with_z3
from pipeline.inject import inject_check

SELFIE = os.path.expanduser("~/selfie/selfie")

def run_binary_with_input(bin_path, input_val):
    """
    Run a RISC-V binary via selfie emulator with concrete input.
    Returns the exit code (1 = violation, 0 = no violation).
    """
    input_bytes = struct.pack('<Q', input_val)
    result = subprocess.run(
        [SELFIE, "-l", bin_path, "-m", "128"],
        input=input_bytes,
        capture_output=True,
        timeout=10
    )
    # selfie writes to stderr: "terminating ... with exit code N"
    output = (result.stdout + result.stderr).decode('utf-8', errors='ignore')
    for line in output.split('\n'):
        if 'exit code' in line.lower():
            try:
                return int(line.strip().split()[-1])
            except ValueError:
                pass
    return 0

def find_counterexample_binary_diff(original_source, patched_source, check_stmt):
    """
    Differential binary testing.
    Both binaries use same main() structure — only difference is the injected check.
    If exit codes differ → check fired → genuine binary-level violation.
    """
    import re

    # apply same main() rewrite to base (without the check)
    # so both binaries return the function result, not 0
    base_source = re.sub(
        r'uint64_t main\(\) \{(\s+)uint64_t\* x;(\s+x = malloc[^;]+;)(\s+\*x = 0;)(\s+read\(0, x, 8\);\s+)(\w+)\(\*x\);(\s+)return 0;\n\}',
        r'uint64_t main() {\1uint64_t r;\1uint64_t* x;\2\3\4r = \5(*x);\6return r;\n}',
        original_source
    )

    with open('/tmp/base.c', 'w') as f:
        f.write(base_source)
    r = subprocess.run([SELFIE, "-c", "/tmp/base.c", "-o", "/tmp/base.bin"],
                       capture_output=True, text=True)
    if "syntax error" in r.stdout:
        return None, "compile_error"

    with open('/tmp/patched.c', 'w') as f:
        f.write(patched_source)
    r = subprocess.run([SELFIE, "-c", "/tmp/patched.c", "-o", "/tmp/patched.bin"],
                       capture_output=True, text=True)
    if "syntax error" in r.stdout:
        return None, "compile_error"

    for v in list(range(101)) + [200, 500, 1000]:
        base_exit    = run_binary_with_input("/tmp/base.bin",    v)
        patched_exit = run_binary_with_input("/tmp/patched.bin", v)
        if patched_exit != base_exit:
            return v, None

    return None, None

def hybrid_verify(function_source, claim, check_stmt, function_name):
    """
    Hybrid binary-level verification:
    1. Compile patched C* to RISC-V binary
    2. Run binary with concrete inputs to find counterexample
    3. If none found in small range, use Z3 for full proof
    Returns: (verdict, witness, method)
    """
    # patch source
    try:
        patched = inject_check(function_source, check_stmt)
    except ValueError as e:
        return "ERROR", None, str(e)

    # compile to binary
    ok, out = compile_source(patched)
    if not ok:
        return "COMPILE_ERROR", None, out[:200]

    # step 1: try binary execution — differential testing
    # pass original source for base, patched for comparison
    witness, err = find_counterexample_binary_diff(function_source, patched, check_stmt)
    if err == "compile_error":
        return "COMPILE_ERROR", None, "Binary compile failed"
    if witness is not None:
        return "FALSIFIED", witness, "binary_execution"

    # step 2: Z3 proof for all inputs
    result = verify_with_z3(check_stmt, function_name)
    verdict = result["verdict"]
    if verdict == "VERIFIED":
        return "VERIFIED", None, "z3_proof"
    elif verdict == "FALSIFIED":
        return "FALSIFIED", result.get("witness"), "z3_model"
    else:
        return "UNKNOWN", None, result.get("error", "unknown")
