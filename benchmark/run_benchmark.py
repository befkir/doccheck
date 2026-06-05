"""
run_benchmark.py — runs all claims and reports two accuracy scores:
  1. Translation accuracy  — did the LLM generate the correct check statement?
  2. Verification accuracy — did the final verdict match the expected verdict?
Usage: python3 benchmark/run_benchmark.py
"""
import json
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.translate import translate_claim
from pipeline.inject    import inject_check
from pipeline.verify    import compile_source, verify_with_z3
from pipeline.binary_verify import hybrid_verify

FUNCTIONS_DIR = os.path.join(os.path.dirname(__file__), "functions")
CLAIMS_FILE   = os.path.join(os.path.dirname(__file__), "claims.json")

def run_all():
    with open(CLAIMS_FILE) as f:
        claims = json.load(f)

    total_claims         = 0
    translation_correct  = 0
    translation_total    = 0
    verification_correct = 0
    errors               = 0
    results              = []

    func_names = set(c["function"] for c in claims)
    print(f"\n{'='*70}")
    print(f"  DocCheck Benchmark Runner")
    print(f"  {len(claims)} claims across {len(func_names)} functions")
    print(f"{'='*70}\n")

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

        try:
            check_stmt = translate_claim(source, claim)
        except Exception as e:
            print(f"  ERROR {func_name:12} | {claim[:40]} — LLM failed: {e}")
            errors += 1
            results.append({"function": func_name, "claim": claim,
                            "expected": expected, "llm_check": "ERROR",
                            "translation_correct": False, "verdict": "ERROR",
                            "verification_correct": False})
            continue

        translation_match = None
        if human_check:
            translation_total += 1
            llm_norm   = check_stmt.replace(" ", "").replace("\n", "")
            human_norm = human_check.replace(" ", "").replace("\n", "")
            translation_match = (llm_norm == human_norm)
            if translation_match:
                translation_correct += 1

        try:
            patched = inject_check(source, check_stmt)
        except ValueError:
            print(f"  ERROR {func_name:12} | {claim[:40]} — inject failed")
            errors += 1
            continue

        ok, _ = compile_source(patched)
        if not ok:
            print(f"  CERR  {func_name:12} | {claim[:45]:45} | LLM: {check_stmt}")
            print(f"         C* does not support this syntax — translation failure")
            errors += 1
            results.append({"function": func_name, "claim": claim,
                            "expected": expected, "llm_check": check_stmt,
                            "translation_correct": False, "verdict": "COMPILE_ERROR",
                            "verification_correct": False})
            continue

        verdict, witness, method = hybrid_verify(source, claim, check_stmt, func_name)
        verification_match = (verdict == expected)
        if verification_match:
            verification_correct += 1

        v_symbol = "PASS" if verification_match else "FAIL"
        w_str    = f" (x={witness})" if witness is not None else ""

        print(f"  {v_symbol} {func_name:12} | {claim[:45]:45} | {verdict}{w_str}")
        if human_check and not translation_match:
            print(f"       LLM:   {check_stmt}")
            print(f"       human: {human_check}")

        results.append({
            "function"             : func_name,
            "claim"                : claim,
            "expected"             : expected,
            "llm_check"            : check_stmt,
            "human_check"          : human_check,
            "translation_correct"  : translation_match,
            "verdict"              : verdict,
            "verification_correct" : verification_match,
            "witness"              : str(witness) if witness else None
        })

    ver_acc   = (verification_correct / total_claims * 100) if total_claims else 0
    trans_acc = (translation_correct  / translation_total  * 100) if translation_total else 0

    print(f"\n{'='*70}")
    print(f"  VERIFICATION ACCURACY  : {verification_correct}/{total_claims} = {ver_acc:.1f}%")
    if translation_total > 0:
        print(f"  TRANSLATION ACCURACY   : {translation_correct}/{translation_total} = {trans_acc:.1f}%")
        print(f"  (measured on {translation_total} claims with human_check reference)")
    else:
        print(f"  TRANSLATION ACCURACY   : add human_check fields to claims.json to measure")
    print(f"  COMPILE/LLM ERRORS     : {errors}")
    print(f"{'='*70}\n")

    os.makedirs(os.path.join(os.path.dirname(__file__), "results"), exist_ok=True)
    out = os.path.join(os.path.dirname(__file__), "results", "latest.json")
    with open(out, "w") as f:
        json.dump({
            "verification_accuracy": ver_acc,
            "translation_accuracy" : trans_acc if translation_total else None,
            "verification_correct" : verification_correct,
            "translation_correct"  : translation_correct,
            "total_claims"         : total_claims,
            "translation_total"    : translation_total,
            "errors"               : errors,
            "results"              : results
        }, f, indent=2)
    print(f"  Results saved to benchmark/results/latest.json")

if __name__ == "__main__":
    run_all()