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

from pipeline.translate import translate_claim, explain_result
from pipeline.inject    import inject_check, parse_signature
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

    # Step 0 — parse signature
    try:
        real_func_name, params = parse_signature(function_source)
        param_names = [p[1] for p in params]
    except Exception as exc:
        print(f"Verdict  : ERROR — could not parse signature: {exc}")
        return {"verdict": "ERROR", "witness": None, "error": str(exc)}

    # Step 1 — translate claim → C* violation check
    try:
        check_stmt = translate_claim(function_source, claim, real_func_name, param_names)
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
        print(f"Proof    : {result.get('proof', 'Formal SMT proof')}")
        
        formula = result.get("formula")
        if formula:
            print("Mathematical Formula:")
            # Limit length to avoid wall of text
            if len(formula) > 500:
                print(f"  {formula[:500]} ... [truncated]")
            else:
                print(f"  {formula}")
    elif verdict == "FALSIFIED":
        print(f"Verdict  : FALSIFIED ✗ — claim broken")
        print(f"Proof    : {result.get('proof', 'SMT counter-example found')}")
        
        # Display the model (counter-example values)
        model = result.get("model", {})
        if model:
            print("Counter-example Trace:")
            for i, val in model.items():
                try:
                    idx = int(i[1:])
                    pname = param_names[idx] if idx < len(param_names) else f"input_{idx}"
                    print(f"  {pname} = {val}")
                except:
                    print(f"  {i} = {val}")
    elif verdict in ("COMPILE_ERROR", "BEATOR_ERROR"):
        print(f"Verdict  : {verdict}")
        print(f"Detail   : {result['error'][:300]}")
    else:
        print(f"Verdict  : UNKNOWN — {result.get('error', 'no details')}")

    # Step 6 — explain result (new)
    print("\n" + "=" * 60)
    print("AI Explanation & Proof")
    print("=" * 60)
    try:
        explanation = explain_result(
            source=function_source,
            claim=claim,
            verdict=verdict,
            model=result.get("model"),
            formula=result.get("formula")
        )
        print(explanation)
    except Exception as exc:
        print(f"Error generating explanation: {exc}")

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