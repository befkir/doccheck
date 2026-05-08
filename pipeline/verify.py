"""
verify.py — symbolic verification using Selfie monster + Z3 CLI.

Pipeline:
  1. compile_source()  : write patched C* to /tmp/doccheck_patched.c
  2. run_monster()     : monster → /tmp/doccheck_patched.smt
  3. verify_smt()      : extract the exit(1) push/pop block, solve with z3

Shared pipeline component. Do not modify without team agreement.
"""

import subprocess
import os
import re

# ---------------------------------------------------------------------------
# Tool paths
# ---------------------------------------------------------------------------

MONSTER = os.environ.get("MONSTER_PATH", os.path.expanduser("~/selfie/monster"))
Z3      = os.environ.get("Z3_PATH",      "z3")

DEFAULT_DEPTH = int(os.environ.get("DOCCHECK_DEPTH", "10000"))

PATCHED_C    = "/tmp/doccheck_patched.c"
PATCHED_SMT  = "/tmp/doccheck_patched.smt"
QUERY_SMT    = "/tmp/doccheck_query.smt"


# ---------------------------------------------------------------------------
# Step 1
# ---------------------------------------------------------------------------

def compile_source(source: str) -> tuple[bool, str]:
    with open(PATCHED_C, "w") as f:
        f.write(source)
    return True, "OK"


# ---------------------------------------------------------------------------
# Step 2
# ---------------------------------------------------------------------------

def run_monster(depth: int = DEFAULT_DEPTH) -> tuple[bool, str]:
    if not os.path.exists(PATCHED_C):
        return False, f"Source file not found: {PATCHED_C}"

    if os.path.exists(PATCHED_SMT):
        os.remove(PATCHED_SMT)

    result = subprocess.run(
        [MONSTER, "-c", PATCHED_C, "-", "0", str(depth), "--merge-enabled"],
        capture_output=True, text=True, timeout=120,
    )
    combined = result.stdout + result.stderr

    if not os.path.exists(PATCHED_SMT):
        return False, f"Monster did not produce SMT file.\n{combined[:400]}"

    return True, combined


# ---------------------------------------------------------------------------
# Step 3
# ---------------------------------------------------------------------------

def _extract_push_pop_blocks(smt: str) -> list[str]:
    """Return the content of each (push 1)...(pop 1) block as a list."""
    blocks = []
    i = 0
    lines = smt.splitlines(keepends=True)
    n = len(lines)
    while i < n:
        if lines[i].strip().startswith("(push"):
            block = []
            i += 1
            while i < n and not lines[i].strip().startswith("(pop"):
                block.append(lines[i])
                i += 1
            blocks.append("".join(block))
        i += 1
    return blocks


def _preamble(smt: str) -> str:
    """Everything before the first (push 1)."""
    idx = smt.find("(push")
    return smt[:idx] if idx != -1 else smt


def _solve_block(preamble: str, block: str) -> str:
    """Write preamble + assert block to a temp file and run z3. Returns stdout+stderr."""
    query = preamble + "(push 1)\n" + block + "(pop 1)\n"
    with open(QUERY_SMT, "w") as f:
        f.write(query)

    result = subprocess.run(
        [Z3, QUERY_SMT],
        capture_output=True, text=True, timeout=300,
    )
    return result.stdout + result.stderr


def _parse_z3_output(output: str) -> str:
    """Return 'sat', 'unsat', or 'unknown' from z3 output."""
    for line in output.splitlines():
        stripped = line.strip().lower()
        if stripped in ("sat", "unsat", "unknown"):
            return stripped
    return "unknown"


def _extract_witness(output: str) -> int | str | None:
    """Pull i0 value from a z3 sat model."""
    m = re.search(r'define-fun\s+i0\s*\(\)\s*\(_\s*BitVec\s*\d+\)\s*#x([0-9a-fA-F]+)', output)
    if m:
        return int(m.group(1), 16)
    m = re.search(r'define-fun\s+i0\s*\(\)\s*\(_\s*BitVec\s*\d+\)\s*\(_\s*bv(\d+)', output)
    if m:
        return int(m.group(1))
    m = re.search(r'#x([0-9a-fA-F]+)', output)
    if m:
        return int(m.group(1), 16)
    return None


def verify_smt() -> dict:
    """
    Monster emits one push/pop block per exit() call:
      - block 0: exit(1)  → violation reachable?  sat=FALSIFIED, unsat=VERIFIED
      - block 1: exit(0)  → normal exit (ignore)

    We solve only block 0.
    """
    if not os.path.exists(PATCHED_SMT):
        return {"verdict": "UNKNOWN", "witness": None,
                "error": f"SMT file not found: {PATCHED_SMT}"}

    with open(PATCHED_SMT) as f:
        smt = f.read()

    # Strip :incremental option (unsupported by this z3 version)
    smt = re.sub(r'\(set-option\s+:incremental[^)]*\)\n?', '', smt)

    preamble = _preamble(smt)
    blocks   = _extract_push_pop_blocks(smt)

    if not blocks:
        return {"verdict": "UNKNOWN", "witness": None,
                "error": "No push/pop blocks found in SMT file."}

    # Block 0 is the exit(1) / violation path
    output = _solve_block(preamble, blocks[0])
    verdict_str = _parse_z3_output(output)

    if verdict_str == "unsat":
        return {"verdict": "VERIFIED", "witness": None, "error": None}

    if verdict_str == "sat":
        return {"verdict": "FALSIFIED", "witness": _extract_witness(output), "error": None}

    return {"verdict": "UNKNOWN", "witness": None,
            "error": f"Z3 returned unknown.\n{output[:300]}"}


# ---------------------------------------------------------------------------
# Top-level
# ---------------------------------------------------------------------------

def verify_with_toolchain(source: str, kmax: int = DEFAULT_DEPTH) -> dict:
    compile_source(source)
    ok, out = run_monster(kmax)
    if not ok:
        return {"verdict": "BEATOR_ERROR", "witness": None, "error": out[:400]}
    return verify_smt()