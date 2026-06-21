# DocCheck

> **Verifying natural language documentation claims using Selfie's monster symbolic execution engine and Z3**

Given a C\* function and a plain-English claim about it, DocCheck determines whether the claim holds for **all possible inputs** — and if not, produces a concrete counterexample that falsifies it.

**Course:** Advanced Systems Engineering
**University:** University of Salzburg
**Supervisor:** Prof. Christoph Kirsch

[![v1.1](https://img.shields.io/badge/release-v1.1-brightgreen)](https://github.com/befkir/doccheck)
[![accuracy](https://img.shields.io/badge/accuracy-62%2F62%20%3D%20100%25-brightgreen)](https://github.com/befkir/doccheck)

---

## The problem

Developers write comments like *"this function never returns a negative value"* — but these claims are never formally checked. They go stale silently as code changes. DocCheck bridges plain English and formal proof.

**Precise problem statement:**
Given a C\* function F and a natural language claim S, determine whether S holds for all possible inputs to F — and if not, produce a concrete counterexample input that falsifies S.

```
Claim: "never returns a negative value"  on absolute(x)
→ VERIFIED — proved for all 2^64 possible inputs

Claim: "output is always smaller than input"  on absolute(x)
→ FALSIFIED — witness x = 9223372036854775808 (= 2^63)
```

---

## Results (v1.1)

| Metric | Value |
|---|---|
| Benchmark | 62 claims across 30 C\* functions |
| **Verification accuracy** | **62/62 = 100.0%** |
| **Translation accuracy** | **62/62 = 100.0%** |
| Manual Z3 models required | **Zero** |
| VERIFIED via monster + Z3 UNSAT | 26 claims |
| FALSIFIED via monster + Z3 SAT | 28 claims |
| FALSIFIED via binary fallback | 6 claims |
| FALSIFIED via legacy Z3 model | 2 claims |
| Compile / LLM errors | 0 |

> **Scope note:** the benchmark covers single-condition claims over single-parameter `uint64_t` functions — the class of claims DocCheck's current translation prompt and injection mechanism support. Claims needing `&&`/`||` or multiple parameters are outside this scope and documented separately as limitations (see below), not counted in the 62.

---

## How it works

```
English claim
      │
      ▼
[1] translate.py   — LLM (llama3.2, temperature=0) → C* check, e.g. if (result < 0) { exit(1); }
      │
      ▼
[2] inject.py       — patches the check into your C* source, rewrites main()
      │
      ▼
[3] monster          — Selfie's symbolic execution engine: C* → RISC-V → SMT-LIB2
      │                 (tracks every possible 64-bit input simultaneously)
      ▼
[4] Z3               — solves the SMT-LIB2 formula
      │                 sat   → FALSIFIED + concrete witness
      │                 unsat → VERIFIED for all 2^64 inputs
      ▼
  [fallback] binary_verify.py — differential execution on Selfie's RISC-V
             emulator for depth-bounded cases monster's symbolic depth can't reach
```

**The key insight:** Selfie's own `monster` tool compiles C\* to RISC-V and symbolically executes the binary, producing pure bitvector SMT-LIB2 that Z3 reads natively. No BTOR2 conversion, no manual Z3 models, no human-written verification logic — monster handles every function automatically.

---

## What DocCheck requires

### Function requirements

| Requirement | Why |
|---|---|
| Written in C\* | Must compile with `starc` and be readable by `monster` |
| Exactly one parameter, type `uint64_t` | The translation prompt and injected check always refer to the input as `x` |
| Return type `uint64_t` | C\* has no floats, signed integers, or strings |
| A local variable named exactly `result` | `inject.py` searches for the literal string `"return result;"` |
| `main()` follows the canonical shape | declare `x` → `malloc` → `read` → call function → `return 0`, in that order |
| No unbounded symbolic recursion or loops | Monster times out beyond ~10,000 symbolic steps (e.g. `factorial` for large `x`) |

A function in canonical shape:
```c
uint64_t absolute(uint64_t x) {
  uint64_t result;
  if (x < 0) { result = -x; }
  else        { result = x;  }
  return result;
}

uint64_t main() {
  uint64_t* x;
  x = malloc(sizeof(uint64_t));
  *x = 0;
  read(0, x, 8);
  absolute(*x);
  return 0;
}
```

### Claim requirements

The claim must reduce to **one comparison** between `result` and either a constant or `x`:

| Supported pattern | Example | Translates to |
|---|---|---|
| Comparison to a constant | "never returns more than 1" | `if (result > 1)` |
| Comparison to the input | "output is always smaller than input" | `if (result >= x)` |
| Equality to a constant | "always returns zero" | `if (result != 0)` |
| Equality to the input | "output equals input" | `if (result != x)` |

**Not yet supported** (see `benchmark/demo_failures.py` for live examples):
- Biconditionals / compound conditions (`&&`, `||`) — C\* if-statements allow only one condition
- Vague wording ("the result is bigger") — no comparison target for the LLM to use
- Multiple parameters or side effects — the pipeline tracks one return value of one parameter

---

## Setup

### Prerequisites
- Ubuntu / WSL2
- Python 3.10+
- [Selfie](https://github.com/cksystemsteaching/selfie) — C\* compiler, emulator, and `monster` symbolic execution engine
- [Z3](https://github.com/Z3Prover/z3) — SMT solver
- [Ollama](https://ollama.com) — local LLM runtime

### Install

```bash
git clone https://github.com/befkir/doccheck.git
cd doccheck

python3 -m venv doccheck-env
source doccheck-env/bin/activate
pip install z3-solver requests --break-system-packages

# build Selfie's monster (symbolic execution engine)
cd ~/selfie && make monster

# install and run Ollama
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2
```

---

## Usage

```bash
source doccheck-env/bin/activate

# verify a single claim
python3 pipeline/pipeline.py benchmark/functions/absolute.c \
    "never returns a negative value"

# add a short, plain-English proof of the verdict
python3 pipeline/pipeline.py benchmark/functions/absolute.c \
    "never returns a negative value" --proof

# add the full step-by-step proof trace
python3 pipeline/pipeline.py benchmark/functions/absolute.c \
    "never returns a negative value" --proof-full

# show what DocCheck is, how it works, and all commands
python3 pipeline/pipeline.py --info

# run the full 62-claim benchmark
python3 benchmark/run_benchmark.py

# see DocCheck's current, honestly-documented limitations
python3 benchmark/demo_failures.py
```

### Example output

```
Function : absolute
Claim    : never returns a negative value
Check    : if (result < 0) { exit(1); }
Verdict  : VERIFIED ✓ — proved for ALL 2^64 inputs
Method   : monster_z3
```

```
======================================================================
  PROOF -- absolute(x)
======================================================================
  Claim : "never returns a negative value"
  DocCheck ran monster (Selfie's symbolic execution engine) on
  the compiled binary, tracking every possible input at once.
  Z3 was asked: "does any 64-bit value of x make
  ( if (result < 0) { exit(1); } ) true?"
  Z3 answered: UNSAT -- no, not for any of the 2^64 possible
  values. This is a mathematical proof, not a test result.
----------------------------------------------------------------------
  VERDICT: VERIFIED -- holds for EVERY possible 64-bit input.
======================================================================
```

---

## Why VERIFIED and FALSIFIED use different methods

`hybrid_verify()` always tries monster + Z3 first. The two verdicts need different kinds of evidence:

- **VERIFIED** can only come from monster + Z3. Binary execution only tests a finite set of concrete inputs (e.g. `x = 0..100`); finding no violation there does *not* prove the violation is impossible for the remaining ~2^64 untested values. Only Z3's UNSAT result is a proof over the entire input domain.
- **FALSIFIED** needs only one counterexample, so either method can supply it. If monster doesn't return a clean verdict within its depth bound (e.g. it times out on a deep loop), DocCheck falls back to differential binary execution on Selfie's RISC-V emulator — often faster at finding small, simple witnesses.

---

## Repository structure

```
doccheck/
├── pipeline/
│   ├── translate.py        ← LLM: English claim → C* check statement (temperature=0)
│   ├── inject.py            ← patches the check into C* source, rewrites main()
│   ├── monster_verify.py    ← runs monster + Z3, the core verifier
│   ├── binary_verify.py     ← differential binary execution fallback (hybrid_verify)
│   ├── proof_explain.py     ← plain-English proof traces (--proof / --proof-full)
│   ├── verify.py             ← legacy manual Z3 models (last-resort fallback)
│   ├── btor2_verify.py       ← Unicorn/BTOR2 experiment (see Unicorn investigation below)
│   └── pipeline.py           ← main CLI orchestrator (--proof, --proof-full, --info)
├── benchmark/
│   ├── functions/            ← 30 C* functions (.c files)
│   ├── claims.json           ← 62 claims + expected verdicts + human reference checks
│   ├── run_benchmark.py      ← runs all 62 claims, reports accuracy
│   └── demo_failures.py      ← honest demonstration of current limitations
├── prompts/
│   └── claim_to_assert.txt   ← few-shot LLM translation prompt
└── docs/                     ← paper, slides, deep explanation PDF
```

---

## Unicorn Z3 investigation

In parallel with the monster+Z3 approach, we investigated Unicorn's built-in Z3 solver as an alternative path to binary-level symbolic verification. Two crashes were fixed in `src/unicorn/smt_solver.rs`:

- **Array sort panic** — `as_array().expect("array")` panicked when memory was the result of an `ite` node; fixed with type-checked dispatch and raw `z3_sys` calls.
- **Eq sort panic** — `as_bv().expect("bv")` panicked when comparing `Bool` or `Array` sorts; fixed with sort-dispatched equality.

After both fixes, Unicorn reaches the `non-zero-exit-code` bad state without crashing. The remaining blocker: Unicorn checks all bad states simultaneously, so memory-limit violations (always satisfiable) contaminate the result for both VERIFIED and FALSIFIED binaries. Isolating the exit-code check requires modifying Unicorn's main verification loop — identified as future work.

---

## Limitations

- **Symbolic loop bounds** — monster times out on loops whose iteration count depends on the symbolic input (e.g. `factorial` for large `x`)
- **Compound boolean operators** — `&&`/`||` claims (biconditionals, compound conditions) aren't expressible as a single C\* check
- **Single-parameter functions** — the prompt and `inject.py` assume one parameter named `x`
- **Proof validity vs. claim strength** — DocCheck proves exactly what it's asked to prove; for `uint64_t`, claims like "never negative" are trivially true for *any* function due to the type system, regardless of the function's actual logic. The proof is valid; choosing a meaningful claim is the user's responsibility.

---

## Related work

| Paper | Venue | Difference |
|---|---|---|
| AutoBug — LLM-powered symbolic execution | OOPSLA 2025 | Uses the LLM as the solver, reasoning over source. DocCheck uses Selfie's own `monster` and Z3 — the LLM only translates. |
| SESpec — symbolic execution + LLM spec generation | arXiv 2025 | Generates specs *from* code. DocCheck verifies natural-language claims *against* code — the reverse direction. |
| Samuel's parallel branch (`exp-two`) | — | Discovered the same monster+Z3 core insight independently, using a 4-step deterministic translation and `qwen2.5-coder` backend. |

---

## Branches

| Branch | Description |
|---|---|
| `main` | Stable — v1.1, tagged `v1.1-final` |
| `exp/llm-ollama` | Primary development — monster+Z3 pipeline, proof traces, Unicorn investigation |
| `exp-two` | Samuel's parallel approach — same monster+Z3 core, different LLM backend |