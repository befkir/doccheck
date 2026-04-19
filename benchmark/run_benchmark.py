"""
run_benchmark.py — runs all claims in claims.json and scores accuracy.
Usage: python3 benchmark/run_benchmark.py
"""
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.translate import translate_claim
from pipeline.inject    import inject_check
from pipeline.verify    import compile_source, verify_with_z3

FUNCTIONS_DIR = os.path.join(os.path.dirname(__file__), "functions")
CLAIMS_FILE   = os.path.join(os.path.dirname(__file__), "claims.json")

def run_all():
    with open(CLAIMS_FILE) as f:
        claims = json.load(f)

    total       = 0
    correct     = 0
    errors      = 0
    results     = []

    print(f"\n{'='*70}")
    print(f"  DocCheck Benchmark Runner")
    print(f"  {len(claims)} claims across {len(set(c['function'] for c in claims))} functions")
    print(f"{'='*70}\n")

    for entry in claims:
        func_file    = entry["function"]
        claim        = entry["claim"]
        expected     = entry["expected"]
        func_name    = os.path.splitext(func_file)[0]
        func_path    = os.path.join(FUNCTIONS_DIR, func_file)

        if not os.path.exists(func_path):
            print(f"  SKIP  {func_file} — file not found")
            continue

        with open(func_path) as f:
            source = f.read()

        total += 1

        # translate
        try:
            check_stmt = translate_claim(source, claim)
        except Exception as e:
            print(f"  ERROR {func_name} | {claim[:40]} — LLM failed: {e}")
            errors += 1
            results.append({"function": func_name, "claim": claim,
                            "expected": expected, "got": "ERROR", "correct": False})
            continue

        # inject
        try:
            patched = inject_check(source, check_stmt)
        except ValueError:
            print(f"  ERROR {func_name} | {claim[:40]} — inject failed")
            errors += 1
            results.append({"function": func_name, "claim": claim,
                            "expected": expected, "got": "ERROR", "correct": False})
            continue

        # compile
        ok, _ = compile_source(patched)
        if not ok:
            print(f"  ERROR {func_name} | {claim[:40]} — compile failed: {check_stmt}")
            errors += 1
            results.append({"function": func_name, "claim": claim,
                            "expected": expected, "got": "COMPILE_ERROR", "correct": False})
            continue

        # verify
        result  = verify_with_z3(check_stmt, func_name)
        verdict = result["verdict"]
        match   = verdict == expected

        if match:
            correct += 1
            status = "  PASS"
        else:
            status = "  FAIL"

        witness_str = f" (counterexample: x={result['witness']})" if result.get("witness") else ""
        print(f"{status} {func_name:12} | {claim[:45]:45} | {verdict}{witness_str}")

        results.append({
            "function": func_name,
            "claim":    claim,
            "check":    check_stmt,
            "expected": expected,
            "got":      verdict,
            "correct":  match
        })

    # summary
    accuracy = (correct / total * 100) if total > 0 else 0
    print(f"\n{'='*70}")
    print(f"  Results: {correct}/{total} correct  |  Accuracy: {accuracy:.1f}%  |  Errors: {errors}")
    print(f"{'='*70}\n")

    # save results
    os.makedirs(os.path.join(os.path.dirname(__file__), "results"), exist_ok=True)
    out_file = os.path.join(os.path.dirname(__file__), "results", "latest.json")
    with open(out_file, "w") as f:
        json.dump({"accuracy": accuracy, "correct": correct,
                   "total": total, "results": results}, f, indent=2)
    print(f"  Full results saved to benchmark/results/latest.json")

if __name__ == "__main__":
    run_all()
