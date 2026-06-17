import json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline.pipeline import load_claims, run_case

GREEN="\033[92m"; RED="\033[91m"; YELLOW="\033[93m"; CYAN="\033[96m"; BOLD="\033[1m"; RESET="\033[0m"

def fmt_ce(row):
    model = row.get("verify_model") or {}
    if not model:
        w = row.get("verify_witness")
        return f"  {CYAN}counterexample: input={w} (0x{w:016x}){RESET}" if w is not None else ""
    parts = [f"{k}={v} (0x{v:016x})" for k,v in sorted(model.items())]
    return f"  {CYAN}counterexample: {', '.join(parts)}{RESET}"

def run_benchmark():
    claims = load_claims()
    total = len(claims)
    passed = failed = errors = 0
    print(f"\n{BOLD}DocCheck Benchmark — {total} claims across 30 functions{RESET}")
    print("=" * 68)
    for entry in claims:
        claim_id = entry["id"]
        expected = entry.get("expected","")
        t0 = time.time()
        try:
            row     = run_case(entry)
            verdict = row.get("actual","ERROR")
            elapsed = time.time() - t0
            ok      = row.get("passed", False)
            if ok:
                passed += 1; tag = f"{GREEN}PASS{RESET}"
            elif verdict in ("PIPELINE_ERROR","TRANSLATION_ERROR","MONSTER_ERROR","UNKNOWN"):
                errors += 1; tag = f"{YELLOW}ERR {RESET}"
            else:
                failed += 1; tag = f"{RED}FAIL{RESET}"
            print(f"{tag}  {claim_id:<36}expected={expected:<6} got={verdict:<6}  ({elapsed:.1f}s)")
            if verdict == "SAT":
                ce = fmt_ce(row)
                if ce: print(ce)
            if verdict in ("PIPELINE_ERROR","TRANSLATION_ERROR","MONSTER_ERROR"):
                print(f"  {YELLOW}{row.get('detail','')[:80]}{RESET}")
        except Exception as exc:
            errors += 1
            print(f"{YELLOW}ERR {RESET}  {claim_id:<36}{str(exc)[:55]}  ({time.time()-t0:.1f}s)")
    print("=" * 68)
    acc = (passed/total*100) if total else 0
    print(f"{BOLD}Results: {passed}/{total} passed | {failed} failed | {errors} errors{RESET}")
    print(f"{BOLD}Accuracy: {acc:.1f}%{RESET}\n")
    return 0 if (failed==0 and errors==0) else 1

if __name__ == "__main__":
    sys.exit(run_benchmark())
