"""
verify.py — symbolic verification using the real Selfie/Unicorn toolchain.

Pipeline:
  1. compile_source()  : starc  → RISC-V binary  (/tmp/patched.bin)
  2. run_beator()      : beator → BTOR2 model     (/tmp/patched.btor2)
  3. verify_btor2()    : bitme  → SAT / UNSAT + witness

Shared pipeline component. Do not modify without team agreement.
"""

import subprocess
import os
import re

# ---------------------------------------------------------------------------
# Tool paths — override with env vars if tools live elsewhere
# ---------------------------------------------------------------------------

SELFIE  = os.environ.get("SELFIE_PATH",  os.path.expanduser("~/selfie/selfie"))
BEATOR  = os.environ.get("BEATOR_PATH",  os.path.expanduser("~/unicorn/beator"))
BITME   = os.environ.get("BITME_PATH",   os.path.expanduser("~/unicorn/bitme"))

# Bound k for bounded model checking (can be overridden per-call)
DEFAULT_KMAX = int(os.environ.get("DOCCHECK_KMAX", "100"))

PATCHED_C    = "/tmp/doccheck_patched.c"
PATCHED_BIN  = "/tmp/doccheck_patched.bin"
PATCHED_BTOR = "/tmp/doccheck_patched.btor2"


# ---------------------------------------------------------------------------
# Step 1 — compile with starc
# ---------------------------------------------------------------------------

def compile_source(source: str) -> tuple[bool, str]:
    """
    Write *source* to a temp file and compile it with starc (Selfie).

    Returns:
        (success: bool, compiler_output: str)
    """
    with open(PATCHED_C, "w") as f:
        f.write(source)

    result = subprocess.run(
        [SELFIE, "-c", PATCHED_C, "-o", PATCHED_BIN],
        capture_output=True,
        text=True,
        timeout=60,
    )
    combined = result.stdout + result.stderr

    if result.returncode != 0 or "syntax error" in combined.lower():
        return False, combined

    return True, combined


# ---------------------------------------------------------------------------
# Step 2 — run beator to produce BTOR2
# ---------------------------------------------------------------------------

def run_beator(kmax: int = DEFAULT_KMAX) -> tuple[bool, str]:
    """
    Run beator on the compiled binary to produce a BTOR2 model.

    Args:
        kmax : loop unrolling / step bound

    Returns:
        (success: bool, output: str)
    """
    if not os.path.exists(PATCHED_BIN):
        return False, f"Binary not found: {PATCHED_BIN}"

    result = subprocess.run(
        [BEATOR, "-kmax", str(kmax), PATCHED_BIN, "-o", PATCHED_BTOR],
        capture_output=True,
        text=True,
        timeout=120,
    )
    combined = result.stdout + result.stderr

    if result.returncode != 0 or not os.path.exists(PATCHED_BTOR):
        return False, combined

    return True, combined


# ---------------------------------------------------------------------------
# Step 3 — run bitme (Z3 back-end) on the BTOR2 model
# ---------------------------------------------------------------------------

def _parse_bitme_output(output: str) -> dict:
    """
    Parse bitme / btor2tools stdout to extract verdict and witness.

    bitme prints one of:
        sat
        unsat
        unknown
    and on SAT it also prints a witness block like:
        ; witness 1
        1 <value> <node-name>
        ...
    We extract the concrete value assigned to the symbolic input
    (node name contains 'read' or 'input' or is simply the first state
    assignment).
    """
    output_lower = output.lower()

    if "unsat" in output_lower:
        return {"verdict": "VERIFIED", "witness": None, "error": None}

    if "sat" in output_lower:
        # Try to extract the concrete input value from the witness block.
        # bitme prints lines like:  1 <hex_or_dec> input_x
        witness = None
        for line in output.splitlines():
            # Match lines that look like: <step> <value> <name>
            m = re.match(r'^\d+\s+(\S+)\s+\S*(?:input|read|x)\S*', line, re.IGNORECASE)
            if m:
                raw = m.group(1)
                try:
                    witness = int(raw, 16) if raw.startswith(('0x', '0b')) else int(raw)
                except ValueError:
                    witness = raw
                break

        # Fall back: grab first numeric assignment anywhere in witness block
        if witness is None:
            m = re.search(r'^\d+\s+(\d+)', output, re.MULTILINE)
            if m:
                try:
                    witness = int(m.group(1))
                except ValueError:
                    pass

        return {"verdict": "FALSIFIED", "witness": witness, "error": None}

    if "unknown" in output_lower:
        return {
            "verdict": "UNKNOWN",
            "witness": None,
            "error": f"bitme returned unknown — try increasing kmax (current: {DEFAULT_KMAX})",
        }

    return {
        "verdict": "UNKNOWN",
        "witness": None,
        "error": f"Could not parse bitme output:\n{output[:400]}",
    }


def verify_btor2(kmax: int = DEFAULT_KMAX) -> dict:
    """
    Run bitme on the BTOR2 file and return a result dict.

    Returns:
        {
          "verdict" : "VERIFIED" | "FALSIFIED" | "UNKNOWN",
          "witness" : int | str | None,
          "error"   : str | None,
        }
    """
    if not os.path.exists(PATCHED_BTOR):
        return {
            "verdict": "UNKNOWN",
            "witness": None,
            "error": f"BTOR2 file not found: {PATCHED_BTOR}",
        }

    result = subprocess.run(
        [BITME, "--kmax", str(kmax), PATCHED_BTOR],
        capture_output=True,
        text=True,
        timeout=300,
    )
    combined = result.stdout + result.stderr
    return _parse_bitme_output(combined)


# ---------------------------------------------------------------------------
# Top-level convenience used by pipeline.py and run_benchmark.py
# ---------------------------------------------------------------------------

def verify_with_toolchain(source: str, kmax: int = DEFAULT_KMAX) -> dict:
    """
    Full end-to-end verification:
      compile → beator → bitme → result dict

    Args:
        source : complete patched C* source (violation check already injected)
        kmax   : bound for model checking

    Returns:
        result dict with keys: verdict, witness, error
    """
    ok, out = compile_source(source)
    if not ok:
        return {"verdict": "COMPILE_ERROR", "witness": None, "error": out[:400]}

    ok, out = run_beator(kmax)
    if not ok:
        return {"verdict": "BEATOR_ERROR", "witness": None, "error": out[:400]}

    return verify_btor2(kmax)