"""
monster_verify.py — Full binary-level symbolic verification using
Selfie monster + Z3. No manual models needed. No BTOR2 issues.

Pipeline:
  1. inject_check() adds exit(1) violation check
  2. monster compiles C* → RISC-V and symbolically executes → SMT-LIB2
  3. Z3 solves: sat=FALSIFIED, unsat=VERIFIED
"""
import subprocess
import re
import os

MONSTER = os.path.expanduser("~/selfie/monster")
MONSTER_DEPTH = int(os.environ.get("MONSTER_DEPTH", "10000"))

def verify_with_monster(source: str, check_stmt: str, func_name: str) -> dict:
    """
    Full symbolic verification: C* source → monster → Z3.
    check_stmt must use exit(1) not return 1.
    Returns: {"verdict": VERIFIED|FALSIFIED|UNKNOWN, "witness": val, "error": str}
    """
    # write patched source
    src_path = f"/tmp/monster_{func_name}.c"
    smt_path = f"/tmp/monster_{func_name}.smt"

    # inject exit(1) version of check
    check_exit = check_stmt.replace("return 1;", "exit(1);")
    if "exit(1)" not in check_exit:
        check_exit = check_stmt  # already uses exit(1)

    patched = source.replace(
        "return result;",
        f"  {check_exit}\n  return result;"
    )

    with open(src_path, "w") as f:
        f.write(patched)

    # run monster
    try:
        r = subprocess.run(
            [MONSTER, "-c", src_path, "-", "0",
             str(MONSTER_DEPTH), "--merge-enabled"],
            capture_output=True, text=True, timeout=60
        )
    except subprocess.TimeoutExpired:
        return {"verdict": "UNKNOWN", "witness": None, "error": "monster timeout"}
    except FileNotFoundError:
        return {"verdict": "UNKNOWN", "witness": None, "error": "monster not found"}

    if not os.path.exists(smt_path):
        return {"verdict": "UNKNOWN", "witness": None,
                "error": f"SMT file not generated. monster output: {r.stderr[:200]}"}

    # read and clean SMT
    with open(smt_path) as f:
        smt = f.read()
    smt = re.sub(r'\(set-option\s+:incremental[^)]*\)\n?', '', smt)

    # write cleaned SMT
    query_path = f"/tmp/monster_{func_name}_query.smt"
    with open(query_path, "w") as f:
        f.write(smt)

    # solve with Z3
    try:
        z3_result = subprocess.run(
            ["z3", query_path],
            capture_output=True, text=True, timeout=30
        )
    except subprocess.TimeoutExpired:
        return {"verdict": "UNKNOWN", "witness": None, "error": "Z3 timeout"}

    output = z3_result.stdout

    # first push/pop block = exit(1) path (violation)
    # sat = violation reachable = FALSIFIED
    # unsat = violation unreachable = VERIFIED
    lines = output.strip().split('\n')
    first_result = lines[0].strip() if lines else ""

    if first_result == "sat":
        # extract witness from model
        witness = None
        m = re.search(r'define-fun i0.*?#x([0-9a-fA-F]+)', output, re.DOTALL)
        if m:
            val = int(m.group(1), 16)
            # prefer small readable values
            if val <= 100:
                witness = val
            else:
                witness = val
        return {"verdict": "FALSIFIED", "witness": witness, "error": None}

    elif first_result == "unsat":
        return {"verdict": "VERIFIED", "witness": None, "error": None}

    else:
        return {"verdict": "UNKNOWN", "witness": None,
                "error": f"Unexpected Z3 output: {output[:100]}"}
