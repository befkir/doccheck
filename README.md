# DocCheck

DocCheck verifies natural-language claims about C* functions using an LLM, Selfie/starc, rotor, and Z3.

## Core design

The LLM does **not** output C* statements. It outputs only a JSON object with a `violation_expr`:

```json
{"violation_expr": "result < a"}
```

`violation_expr` must be true exactly when the claim is broken.

The injector keeps the original function unchanged and appends a generated `main()` harness:

```c
uint64_t main() {
  uint64_t a;
  uint64_t b;
  uint64_t result;

  read(0, &a, 8);
  read(0, &b, 8);

  result = max(a, b);

  if (result < a)
    return 1;

  return 0;
}
```

Rotor checks whether `main()` can exit non-zero.

```text
SAT   = violation reachable = claim false
UNSAT = violation unreachable = claim true within the bound
```

## Repository structure

```text
doccheck/
├── README.md
├── .gitignore
├── benchmark/
│   ├── functions/
│   ├── claims.json
│   └── results/
├── pipeline/
│   ├── translate.py
│   ├── inject.py
│   ├── verify.py
│   └── pipeline.py
├── prompts/
│   └── claim_to_assert.txt
├── docs/
│   ├── proposal.md
│   └── related_work.md
├── tools/
│   └── setup.sh
└── tests/
    └── test_pipeline.py
```



## claims.json format — no params needed

Do not write a `params` field. The pipeline automatically extracts the parameter names from the C* function signature.

```json
[
  {
    "id": "max_ge_a",
    "file": "max.c",
    "function": "max",
    "claim": "The result is always greater than or equal to a.",
    "expected": "UNSAT"
  }
]
```

For `uint64_t max(uint64_t a, uint64_t b)`, the injector automatically creates symbolic variables `a` and `b`, reads them, calls `max(a, b)`, and checks the generated violation expression.

## Setup

```bash
cd doccheck
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and add your OpenRouter API key and Selfie path.

## Run one case

```bash
python -m pipeline.pipeline --case-id max_ge_a
```

## Run all benchmark cases

```bash
python -m pipeline.pipeline --all
```
