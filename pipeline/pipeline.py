"""
pipeline.py — main orchestrator for DocCheck.

Usage:
    python3 pipeline/pipeline.py <function.c> "<claim>" [--kmax N]

Example:
    python3 pipeline/pipeline.py benchmark/functions/absolute.c \
        "never returns a negative value"
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.translate import translate_claim
from pipeline.inject    import inject_check
from pipeline.verify    import verify_with_toolchain


def check(function_source: str, claim: str, function_name: str, kmax: int = 100) -> dict:
    """
    Run the full DocCheck pipeline for one (function, claim) pair.

    Args:
        function_source : raw C* source text
        claim           : English claim string
        function_name   : stem of the source file (used for display only)
        kmax            : bound passed through to beator / bitme

    Returns:
        result dict: { verdict, witness, error }
    """
    sep = "=" * 60
    print(f"\n{sep}")
    print(f"Function : {function_name}")
    print(f"Claim    : {claim}")
    print(f"kmax     : {kmax}")

    # Step 1 — translate claim → C* violation check
    try:
        check_stmt = translate_claim(function_source, claim)
    except Exception as exc:
        print(f"Verdict  : ERROR — LLM translation failed: {exc}")
        return {"verdict": "ERROR", "witness": None, "error": str(exc)}

    print(f"Check    : {check_stmt}")

    # Step 2 — inject check into source and build symbolic harness
    try:
        patched = inject_check(function_source, check_stmt)
    except ValueError as exc:
        print(f"Verdict  : ERROR — inject failed: {exc}")
        return {"verdict": "ERROR", "witness": None, "error": str(exc)}

    # Steps 3-5 — compile → beator → bitme
    result = verify_with_toolchain(patched, kmax=kmax)

    verdict = result["verdict"]
    if verdict == "VERIFIED":
        print(f"Verdict  : VERIFIED ✓  — proved for ALL inputs within bound k={kmax} (UNSAT)")
    elif verdict == "FALSIFIED":
        w = result["witness"]
        print(f"Verdict  : FALSIFIED ✗ — claim broken by input x = {w}")
    elif verdict in ("COMPILE_ERROR", "BEATOR_ERROR"):
        print(f"Verdict  : {verdict}")
        print(f"Detail   : {result['error'][:300]}")
    else:
        print(f"Verdict  : UNKNOWN — {result.get('error', 'no details')}")

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="DocCheck — verify NL claims about C* functions")
    parser.add_argument("function_file", help="Path to the C* source file")
    parser.add_argument("claim",         help="English claim to verify")
    parser.add_argument("--kmax", type=int, default=100,
                        help="Bound for beator/bitme model checking (default: 100)")
    args = parser.parse_args()

    if not os.path.isfile(args.function_file):
        print(f"Error: file not found: {args.function_file}")
        sys.exit(1)

    func_name = os.path.splitext(os.path.basename(args.function_file))[0]
    with open(args.function_file) as f:
        source = f.read()

    result = check(source, args.claim, func_name, kmax=args.kmax)

    # Exit code mirrors verdict
    exit_codes = {"VERIFIED": 0, "FALSIFIED": 1}
    sys.exit(exit_codes.get(result.get("verdict", "UNKNOWN"), 2))


if __name__ == "__main__":
    main()