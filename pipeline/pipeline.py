"""
pipeline.py — main orchestrator for DocCheck.
Usage:
    python3 pipeline/pipeline.py <function.c> "<claim>"
    python3 pipeline/pipeline.py <function.c> "<claim>" --proof
"""
import sys
import os
import argparse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.translate    import translate_claim
from pipeline.inject       import inject_check
from pipeline.binary_verify import hybrid_verify
from pipeline.proof_explain import explain_proof

def check(function_source, claim, function_name, show_proof=False):
    print(f"\n{'='*60}")
    print(f"Function : {function_name}")
    print(f"Claim    : {claim}")

    check_stmt = translate_claim(function_source, claim)
    print(f"Check    : {check_stmt}")

    verdict, witness, method = hybrid_verify(
        function_source, claim, check_stmt, function_name)

    if verdict == "VERIFIED":
        print(f"Verdict  : VERIFIED ✓ — proved for ALL 2^64 inputs")
        print(f"Method   : {method}")
    elif verdict == "FALSIFIED":
        print(f"Verdict  : FALSIFIED ✗ — claim broken by input x = {witness}")
        print(f"Method   : {method}")
    else:
        print(f"Verdict  : {verdict}")
        print(f"Method   : {method}")

    if show_proof:
        print()
        proof = explain_proof(function_source, claim, check_stmt, function_name)
        print(proof)

    return {"verdict": verdict, "witness": witness, "method": method}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DocCheck — verify a natural language claim about a C* function")
    parser.add_argument("function_file", help="path to the C* source file")
    parser.add_argument("claim",         help="natural language claim to verify")
    parser.add_argument("--proof",       action="store_true",
                        help="show annotated step-by-step proof trace")
    args = parser.parse_args()

    if not os.path.exists(args.function_file):
        print(f"Error: file not found: {args.function_file}")
        sys.exit(1)

    with open(args.function_file) as f:
        source = f.read()

    func_name = os.path.splitext(os.path.basename(args.function_file))[0]
    check(source, args.claim, func_name, show_proof=args.proof)
