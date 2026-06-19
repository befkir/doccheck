"""
demo_failures.py — honest demonstration of DocCheck's current limitations.

These are real, current limitations — not solved problems dressed up as
limitations. Each one is documented in the paper.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.translate import translate_claim
from pipeline.inject import inject_check
from pipeline.binary_verify import hybrid_verify

def banner(text):
    width = 68
    print("╔" + "═" * width + "╗")
    pad = (width - len(text)) // 2
    print("║" + " " * pad + text + " " * (width - pad - len(text)) + "║")

def section(title):
    print()
    print("══ " + title + " ══")
    print()

def card(function, claim, why):
    print("─" * 68)
    print(f"  Function : {function}")
    print(f"  Claim    : {claim}")
    print(f"  Why this happens: {why}")
    print("─" * 68)

print("╔" + "═" * 68 + "╗")
print("║" + " " * 12 + "DocCheck — Known Current Limitations" + " " * 19 + "║")
print("║" + " " * 8 + "Honest demonstration, documented in the paper" + " " * 13 + "║")
print("╚" + "═" * 68 + "╝")

# ─────────────────────────────────────────────────────────────────
section("LIMITATION 1: Compound boolean operators (&&, ||)")

card("sign", "the function returns 1 if and only if x is not zero",
     "C* if-statements allow only ONE condition. Biconditional "
     "claims need '&&' or '||', which C* rejects at compile time.")

with open("benchmark/functions/sign.c") as f:
    source = f.read()
claim = "the function returns 1 if and only if x is not zero"
check = translate_claim(source, claim)
print(f"  LLM check : {check}")
print(f"  PROBLEM   : a biconditional needs TWO conditions joined by &&.")
print(f"  C* SUPPORT: single condition only — '&&' is not a valid token.")
print(f"  RESULT    : the LLM silently picks ONE direction of the")
print(f"              biconditional, silently dropping the other half.")
print(f"  STATUS    : CURRENT LIMITATION — needs multi-condition support")
print(f"              in inject.py and the translation prompt.")

# ─────────────────────────────────────────────────────────────────
section("LIMITATION 2: Ambiguous claim wording")

card("double", "the result is always bigger",
     "Vague claims give the LLM insufficient context. "
     "'Bigger than what?' is never specified.")

with open("benchmark/functions/double.c") as f:
    source = f.read()
claim = "the result is always bigger"
check = translate_claim(source, claim)
print(f"  LLM check : {check}")
print(f"  PROBLEM   : 'bigger' compared to what — zero? the input? a")
print(f"              previous call? The LLM has to guess, and different")
print(f"              runs or models may guess differently.")
print(f"  STATUS    : CURRENT LIMITATION — claims must be unambiguous.")
print(f"              This is a constraint on the user's English, not")
print(f"              a bug in the pipeline.")

# ─────────────────────────────────────────────────────────────────
section("NOTE: Weak claim, strong proof (not a failure)")

card("absolute", "never returns a negative value",
     "uint64_t is unsigned — values are ALWAYS >= 0 by the type system.")

with open("benchmark/functions/absolute.c") as f:
    source = f.read()
claim = "never returns a negative value"
check = translate_claim(source, claim)
verdict, witness, method = hybrid_verify(source, claim, check, "absolute")

print(f"  Check     : {check}")
print(f"  Verdict   : {verdict}  (method: {method})")
print()
print(f"  This is a CORRECT and VALID proof — Z3 genuinely proves the")
print(f"  claim for all 2^64 inputs. The proof is not misleading.")
print()
print(f"  But the CLAIM itself is weak: for uint64_t, 'never negative'")
print(f"  is true for ANY function, including a broken one, because")
print(f"  the type system makes negative values impossible to begin")
print(f"  with. The proof doesn't tell you anything about whether")
print(f"  absolute() actually computes the right thing.")
print()
print(f"  TAKEAWAY: DocCheck proves exactly what you ask it to prove.")
print(f"  A stronger claim like 'output equals -x when x >= 0' would")
print(f"  test real logic. Choosing a meaningful claim is the user's")
print(f"  responsibility — DocCheck cannot judge claim quality, only")
print(f"  claim truth.")

# ─────────────────────────────────────────────────────────────────
print()
print("╔" + "═" * 68 + "╗")
print("║  Summary of current limitations shown:                            ║")
print("║  1. Compound boolean (&&, ||) — not yet supported in C* checks    ║")
print("║  2. Vague claims — ambiguous English cannot be translated safely  ║")
print("║                                                                    ║")
print("║  Both are documented in the paper as future work.                 ║")
print("║  The unsigned-arithmetic note above is NOT a failure — it shows   ║")
print("║  the difference between proof validity and claim strength.        ║")
print("╚" + "═" * 68 + "╝")
