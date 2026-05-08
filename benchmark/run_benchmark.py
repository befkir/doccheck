"""
run_benchmark.py — runs all claims in claims.json and reports:
  1. Translation accuracy  — LLM check statement vs human_check reference
  2. Verification accuracy — final verdict vs expected verdict

Usage:
    python3 benchmark/run_benchmark.py [--kmax N]
"""

import json
import os
import sys
import argparse
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.translate import translate_claim
from pipeline.inject    import inject_check, parse_signature
from pipeline.verify    import verify_with_toolchain

FUNCTIONS_DIR = os.path.join(os.path.dirname(__file__), "functions")
CLAIMS_FILE   = os.path.join(os.path.dirname(__file__), "claims.json")
RESULTS_DIR   = os.path.join(os.path.dirname(__file__), "results")


def _normalise(s: str) -> str:
    """Remove whitespace and unify signaling (return 1 -> exit(1))."""
    s = s.replace(" ", "").replace("\n", "").replace(";", "")
    s = s.replace("return1", "exit(1)")
    return s


def run_all(kmax: int = 100) -> None:
    with open(CLAIMS_FILE) as f:
        claims = json.load(f)

    total_claims         = 0
    translation_correct  = 0
    translation_total    = 0
    verification_correct = 0
    errors               = 0
    results              = []
    total_time           = 0.0

    func_names = set(c["function"] for c in claims)
    print(f"\n{'='*72}")
    print(f"  DocCheck Benchmark Runner")
    print(f"  {len(claims)} claims across {len(func_names)} functions  |  kmax={kmax}")
    print(f"{'='*72}\n")

    for entry in claims:
        func_file   = entry["function"]
        claim       = entry["claim"]
        expected    = entry["expected"]
        human_check = entry.get("human_check")
        func_name   = os.path.splitext(func_file)[0]
        func_path   = os.path.join(FUNCTIONS_DIR, func_file)

        if not os.path.exists(func_path):
            print(f"  SKIP  {func_file} — file not found")
            continue

        with open(func_path) as f:
            source = f.read()

        total_claims += 1
        t0 = time.time()

        # --- Step 0: parse signature ---
        try:
            real_func_name, params = parse_signature(source)
            param_names = [p[1] for p in params]
        except Exception as exc:
            print(f"  ERROR {func_name:14} | {claim[:40]:40} — signature parse: {exc}")
            errors += 1
            continue

        # --- Step 1: translate ---
        try:
            check_stmt = translate_claim(source, claim, real_func_name, param_names)
        except Exception as exc:
            elapsed = time.time() - t0
            print(f"  ERROR {func_name:14} | {claim[:40]:40} — LLM failed: {exc}")
            errors += 1
            results.append({
                "function": func_name, "claim": claim, "expected": expected,
                "llm_check": "ERROR", "translation_correct": False,
                "verdict": "ERROR", "verification_correct": False,
                "elapsed_s": round(elapsed, 2),
            })
            continue

        # --- Translation accuracy (when human reference exists) ---
        translation_match = None
        if human_check:
            translation_total += 1
            translation_match = (_normalise(check_stmt) == _normalise(human_check))
            if translation_match:
                translation_correct += 1

        # --- Step 2: inject ---
        try:
            patched = inject_check(source, check_stmt)
        except ValueError as exc:
            elapsed = time.time() - t0
            print(f"  ERROR {func_name:14} | {claim[:40]:40} — inject: {exc}")
            errors += 1
            results.append({
                "function": func_name, "claim": claim, "expected": expected,
                "llm_check": check_stmt, "translation_correct": translation_match,
                "verdict": "INJECT_ERROR", "verification_correct": False,
                "elapsed_s": round(elapsed, 2),
            })
            continue

        # --- Steps 3-5: compile → beator → bitme ---
        result  = verify_with_toolchain(patched, kmax=kmax)
        elapsed = time.time() - t0
        total_time += elapsed

        verdict = result["verdict"]

        if verdict in ("COMPILE_ERROR", "BEATOR_ERROR"):
            print(f"  CERR  {func_name:14} | {claim[:45]:45} | {verdict}")
            print(f"         {result['error'][:120]}")
            errors += 1
            results.append({
                "function": func_name, "claim": claim, "expected": expected,
                "llm_check": check_stmt, "translation_correct": translation_match,
                "verdict": verdict, "verification_correct": False,
                "elapsed_s": round(elapsed, 2),
            })
            continue

        verification_match = (verdict == expected)
        if verification_match:
            verification_correct += 1

        v_symbol = "PASS" if verification_match else "FAIL"
        witness  = result.get("witness")
        w_str    = f" (x={witness})" if witness is not None else ""
        t_str    = f" [{elapsed:.1f}s]"

        print(f"  {v_symbol}  {func_name:14} | {claim[:45]:45} | {verdict}{w_str}{t_str}")

        if human_check and not translation_match:
            print(f"         LLM  : {check_stmt}")
            print(f"         human: {human_check}")

        results.append({
            "function"            : func_name,
            "claim"               : claim,
            "expected"            : expected,
            "llm_check"           : check_stmt,
            "human_check"         : human_check,
            "translation_correct" : translation_match,
            "verdict"             : verdict,
            "verification_correct": verification_match,
            "witness"             : str(witness) if witness is not None else None,
            "elapsed_s"           : round(elapsed, 2),
        })

    # --- Summary ---
    ver_acc   = (verification_correct / total_claims * 100) if total_claims   else 0
    trans_acc = (translation_correct  / translation_total  * 100) if translation_total else 0
    avg_time  = (total_time / total_claims) if total_claims else 0

    print(f"\n{'='*72}")
    print(f"  VERIFICATION ACCURACY : {verification_correct}/{total_claims} = {ver_acc:.1f}%")
    if translation_total > 0:
        print(f"  TRANSLATION ACCURACY  : {translation_correct}/{translation_total} = {trans_acc:.1f}%")
        print(f"  (measured on {translation_total} claims with human_check reference)")
    else:
        print(f"  TRANSLATION ACCURACY  : add human_check fields to claims.json to measure")
    print(f"  COMPILE/TOOL ERRORS   : {errors}")
    print(f"  AVG RUNTIME           : {avg_time:.1f}s per claim")
    print(f"{'='*72}\n")

    os.makedirs(RESULTS_DIR, exist_ok=True)
    out_path = os.path.join(RESULTS_DIR, "latest.json")
    with open(out_path, "w") as f:
        json.dump({
            "kmax"                    : kmax,
            "verification_accuracy"   : round(ver_acc, 2),
            "translation_accuracy"    : round(trans_acc, 2) if translation_total else None,
            "verification_correct"    : verification_correct,
            "translation_correct"     : translation_correct,
            "total_claims"            : total_claims,
            "translation_total"       : translation_total,
            "errors"                  : errors,
            "avg_runtime_s"           : round(avg_time, 2),
            "results"                 : results,
        }, f, indent=2)
    print(f"  Results saved → {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the DocCheck benchmark")
    parser.add_argument("--kmax", type=int, default=100,
                        help="Bound for beator/bitme model checking (default: 100)")
    args = parser.parse_args()
    run_all(kmax=args.kmax)