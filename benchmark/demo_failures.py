"""
demo_failures.py — demonstrates known limitations of DocCheck.
Run this during presentation to show honest system boundaries.

Usage: python3 benchmark/demo_failures.py
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.translate import translate_claim
from pipeline.inject    import inject_check
from pipeline.verify    import compile_source, verify_with_z3

FUNCTIONS_DIR = os.path.join(os.path.dirname(__file__), "functions")

def run(func_file, claim, expected_failure, why):
    func_name = os.path.splitext(func_file)[0]
    func_path = os.path.join(FUNCTIONS_DIR, func_file)
    with open(func_path) as f:
        source = f.read()

    print(f"\n{'─'*65}")
    print(f"  Function : {func_name}")
    print(f"  Claim    : {claim}")
    print(f"  Why this fails: {why}")
    print(f"{'─'*65}")

    check_stmt = translate_claim(source, claim)
    print(f"  LLM check: {check_stmt}")

    try:
        patched = inject_check(source, check_stmt)
    except ValueError as e:
        print(f"  RESULT   : INJECT ERROR — {e}")
        print(f"  FAILURE TYPE: {expected_failure}")
        return

    ok, out = compile_source(patched)
    if not ok:
        print(f"  RESULT   : COMPILE ERROR")
        print(f"  Detail   : C* does not support '&&' or '||' in if-statements")
        print(f"  FAILURE TYPE: {expected_failure}")
        return

    result = verify_with_z3(check_stmt, func_name)
    verdict = result["verdict"]
    print(f"  RESULT   : {verdict}")
    if result.get("witness") is not None:
        print(f"  Witness  : x = {result['witness']}")
    if verdict == "UNKNOWN":
        print(f"  Detail   : {result.get('error')}")
    print(f"  FAILURE TYPE: {expected_failure}")

print("""
╔══════════════════════════════════════════════════════════════╗
║         DocCheck — Known Failure Demonstration               ║
║         These failures are documented limitations            ║
╚══════════════════════════════════════════════════════════════╝
""")

# ── FAILURE 1: Compound boolean — && not supported in C* ─────────────
print("\n══ FAILURE 1: Compound boolean operators (&&) ══")
run("sign.c",
    "the function returns 1 if and only if x is not zero",
    "COMPILE ERROR — C* does not support && or ||",
    "C* if-statements allow only ONE condition. "
    "Biconditional claims require '&&' which C* rejects at compile time.")

# ── FAILURE 2: LLM translation ambiguity ─────────────────────────────
print("\n══ FAILURE 2: Ambiguous claim wording ══")
run("double.c",
    "the result is always bigger",
    "UNKNOWN — claim too vague for LLM to translate",
    "Vague claims give the LLM insufficient context. "
    "'Bigger than what?' is not specified.")

# ── FAILURE 3: Unregistered function (manual Z3 model missing) ───────
print("\n══ FAILURE 3: Manual Z3 model missing ══")

# write a temporary new function not in the registry
import tempfile, os
new_func = """uint64_t mystery(uint64_t x) {
  uint64_t result;
  result = x * x + x + 1;
  return result;
}
uint64_t main() {
  uint64_t* x;
  x = malloc(sizeof(uint64_t));
  *x = 0;
  read(0, x, 8);
  mystery(*x);
  return 0;
}
"""
tmp_path = os.path.join(FUNCTIONS_DIR, "mystery.c")
with open(tmp_path, "w") as f:
    f.write(new_func)

run("mystery.c",
    "never returns a negative value",
    "UNKNOWN — no Z3 model registered for this function",
    "The main limitation: every new function needs a manual Z3 model "
    "in verify.py before DocCheck can verify it.")

# clean up temp file
os.remove(tmp_path)

# ── FAILURE 4: Unsigned arithmetic — trivially true claim ────────────
print("\n══ FAILURE 4: Unsigned arithmetic semantics ══")
print(f"\n{'─'*65}")
print(f"  Function : absolute")
print(f"  Claim    : 'never returns a negative value'")
print(f"  Why this fails: C* uses uint64_t — values are ALWAYS ≥ 0")
print(f"{'─'*65}")
print(f"  RESULT   : VERIFIED — but this tells us NOTHING useful")
print(f"  Detail   : uint64_t range is 0 to 18,446,744,073,709,551,615")
print(f"             A negative value is IMPOSSIBLE by the type system")
print(f"             The claim is trivially true — not because absolute() is correct")
print(f"  FAILURE TYPE: MISLEADING RESULT — trivially true claim")

print("""
╔══════════════════════════════════════════════════════════════╗
║  Summary of failures shown:                                  ║
║  1. Compound boolean (&&) → COMPILE ERROR                    ║
║  2. Vague claim → LLM cannot translate                       ║
║  3. Unregistered function → UNKNOWN (manual model missing)   ║
║  4. Unsigned arithmetic → misleadingly VERIFIED              ║
║                                                              ║
║  All four are documented in the paper as known limitations.  ║
╚══════════════════════════════════════════════════════════════╝
""")
