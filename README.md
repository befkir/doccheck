# + DocCheck

> **Verifying natural language documentation claims using symbolic execution and AI**

Given a C\* function and a plain-English claim about it, DocCheck determines whether the claim holds for **all possible inputs** — and if not, produces a concrete counterexample that falsifies it.

**Course:** Advanced Systems Engineering  
**University:** University of Salzburg  
**Supervisor:** Prof. Christoph Kirsch  

---

## The problem

Developers write comments like *"this function never returns a negative value"* — but these claims are never formally checked. They go stale silently as code changes. DocCheck bridges plain English and formal proof.

**Precise problem statement:**  
Given a C\* function F and a natural language claim S, determine whether S holds for all possible inputs to F — and if not, produce a concrete counterexample input that falsifies S.

---

## How it works
English claim
↓  [1] LLM translates
C* if-statement (violation check with exit(1))
↓  [2] inject into function
Patched C* source
↓  [3] starc/monster compiles
RISC-V binary & SMT-LIB constraints
↓  [4] Z3 solves
VERIFIED or FALSIFIED + counterexample
↓  [5] LLM Explainer
Markdown Report with LaTeX Proofs & Traces

---

## Team

| Name | GitHub | Branch |
|------|--------|--------|
| Befkir | @befkir | `exp/llm-ollama` |
| Samuel | @SamuelFentie | `origin/exp-two  origin/Experimental` |
| Tinsae | @tinsae27 | `exp/llm-openai` |

---

## Repository structure
doccheck/
├── pipeline/
│   ├── translate.py     ← LLM: English claim → C* check statement
│   ├── inject.py        ← insert check into C* source
│   ├── verify.py        ← compile + symbolic execution + Z3
│   └── pipeline.py      ← main orchestrator
├── benchmark/
│   ├── functions/       ← 30 C* functions (.c files)
│   └── claims.json      ← claims + expected verdicts per function
├── prompts/
│   └── claim_to_assert.txt  ← few-shot prompt (shared)
├── docs/
│   ├── proposal.md      ← project proposal
│   └── related_work.md  ← AutoBug, SESpec comparison
├── tools/
│   └── setup.sh         ← install all dependencies
└── tests/
└── test_pipeline.py ← basic tests

---

## Setup

### Prerequisites

- Ubuntu / WSL2
- Python 3.12+
- Rust / cargo
- [Selfie](https://github.com/cksystemsteaching/selfie) — C\* compiler
- [Unicorn](https://github.com/cksystemsgroup/unicorn) — symbolic execution
- [Ollama](https://ollama.com) — local LLM (for `exp/llm-ollama` branch)

### Install

```bash
# Clone the repo
git clone https://github.com/befkir/doccheck.git
cd doccheck

# Create Python environment
python3 -m venv ~/doccheck-env
source ~/doccheck-env/bin/activate
pip install z3-solver requests

# Install and run Ollama (exp/llm-ollama branch only)
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2
```

---

## Run

```bash
source ~/doccheck-env/bin/activate
python3 pipeline/pipeline.py benchmark/functions/absolute.c "never returns a negative value"
```

### Example output
Claim   : never returns a negative value
Check   : if (result < 0) { exit(1); }
Verdict : VERIFIED ✓ — proved for ALL inputs (Z3: UNSAT)
Proof   : Exhaustive state-space search proved unsatisfiable.

### AI Explanation & Proof
**Mathematical Proof (LaTeX):**
\[ \forall x \in \text{uint64}, \text{result} = |x| \implies \text{result} \geq 0 \]
**Natural Language:**
The function uses an unsigned 64-bit integer type. By definition, an unsigned integer cannot be less than zero.

---

## Translation interface

All experiment branches implement the same function signature so they are interchangeable:

```python
def translate_claim(function_source: str, claim: str) -> str:
    """
    Args:
        function_source : full C* function source code
        claim           : English claim e.g. "never returns a negative value"
    Returns:
        C* if-statement e.g. "if (result < 0) { return 1; }"
    """
```

---

## Related work

| Paper | Venue | Difference |
|-------|-------|------------|
| AutoBug — LLM-powered symbolic execution | OOPSLA 2025 | Works at source level (Python/C). We work at RISC-V binary level with formal SMT proof. |
| SESpec — symbolic execution + LLM for spec generation | arXiv 2025 | Generates specs *from* code. We verify NL claims *against* code. |

---

## Current status

- [x] Toolchain installed (Selfie, Unicorn, Z3, Ollama)
- [x] General symbolic verification pipeline (not hardcoded to specific functions)
- [x] Robust signaling via `exit(1)` (prevents return-value collisions)
- [x] SMT-LIB Pretty-printing and LaTeX proof generation
- [x] Automated AI Explainer for results
- [ ] 30-function benchmark evaluation
- [ ] Cross-backend comparison (Ollama vs Claude vs GPT-4)
