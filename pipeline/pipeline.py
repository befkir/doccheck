"""DocCheck orchestrator.

Usage:
  python -m pipeline.pipeline --case-id max_ge_a
  python -m pipeline.pipeline --all
  python -m pipeline.pipeline --source benchmark/functions/max.c --claim "The result is always >= a" --function max
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

# Allow both `python -m pipeline.pipeline` and direct execution.
try:
    from .inject import find_function_signature, inject_file
    from .translate import TranslationError, translate_claim
    from .verify import verify_patched
except ImportError:  # pragma: no cover
    from inject import find_function_signature, inject_file
    from translate import TranslationError, translate_claim
    from verify import verify_patched

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmark"
FUNCTIONS = BENCH / "functions"
RESULTS = BENCH / "results"
CLAIMS = BENCH / "claims.json"


def load_claims() -> list[dict[str, Any]]:
    """Load benchmark cases.

    Preferred claims.json format is a list of cases:
      [{"id":"max_ge_a", "file":"max.c", "function":"max", "claim":"..."}]

    A legacy mapping is also accepted for convenience:
      {"max.c": {"function":"max", "claim":"..."}}

    There is intentionally NO `params` field. Parameter names are extracted
    from the C* function signature by inject.py.
    """
    if not CLAIMS.exists():
        raise FileNotFoundError(f"Missing {CLAIMS}")

    data = json.loads(CLAIMS.read_text(encoding="utf-8"))

    if isinstance(data, dict) and "cases" in data:
        data = data["cases"]

    if isinstance(data, dict):
        cases = []
        for file_name, spec in data.items():
            if not isinstance(spec, dict):
                raise ValueError(f"claims.json entry for {file_name!r} must be an object")
            case = dict(spec)
            case.setdefault("file", file_name)
            case.setdefault("id", Path(file_name).stem)
            case.pop("params", None)
            cases.append(case)
        data = cases

    if not isinstance(data, list):
        raise ValueError("claims.json must contain a list, {'cases': [...]}, or {file: case} mapping")

    for case in data:
        if not isinstance(case, dict):
            raise ValueError("each claim case must be an object")
        case.pop("params", None)  # params are deliberately ignored/removed
        if "id" not in case:
            case["id"] = Path(case["file"]).stem

    return data


def write_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True) + "\n")


def run_case(case: dict[str, Any]) -> dict[str, Any]:
    start = time.time()
    case_id = case["id"]
    function_file = FUNCTIONS / case["file"]
    function_name = case.get("function")
    claim = case["claim"]
    expected = case.get("expected")

    case_dir = RESULTS / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    patched_path = case_dir / "patched.c"

    row: dict[str, Any] = {
        "id": case_id,
        "file": case["file"],
        "function": function_name,
        "claim": claim,
        "expected": expected,
    }

    try:
        source = function_file.read_text(encoding="utf-8")
        sig = find_function_signature(source, function_name)
        row["function"] = sig.name
        row["parameters"] = sig.param_names

        translation = translate_claim(source, claim, sig.param_names)
        row["violation_expr"] = translation.violation_expr
        (case_dir / "llm_raw.txt").write_text(translation.raw_response, encoding="utf-8")

        inject_file(function_file, patched_path, translation.violation_expr, sig.name)
        verify_result = verify_patched(patched_path, case_dir)
        row.update({f"verify_{k}": v for k, v in asdict(verify_result).items()})

        actual = verify_result.status
        row["actual"] = actual
        row["passed"] = expected is None or actual == expected

    except TranslationError as exc:
        row["actual"] = "TRANSLATION_ERROR"
        row["detail"] = str(exc)
        row["passed"] = expected == "TRANSLATION_ERROR"
    except Exception as exc:
        row["actual"] = "PIPELINE_ERROR"
        row["detail"] = repr(exc)
        row["passed"] = expected == "PIPELINE_ERROR"

    row["elapsed_sec"] = round(time.time() - start, 3)
    write_jsonl(RESULTS / "results.jsonl", row)
    return row


def run_single_source(source: Path, claim: str, function_name: str | None) -> dict[str, Any]:
    case = {
        "id": source.stem + "_adhoc",
        "file": source.name,
        "function": function_name,
        "claim": claim,
    }
    tmp_target = FUNCTIONS / source.name
    if source.resolve() != tmp_target.resolve():
        tmp_target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    return run_case(case)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true")
    group.add_argument("--case-id")
    group.add_argument("--source", type=Path)
    parser.add_argument("--claim")
    parser.add_argument("--function")
    args = parser.parse_args(argv)

    if args.all:
        rows = [run_case(case) for case in load_claims()]
        print(json.dumps(rows, indent=2))
        return 0 if all(r.get("passed") for r in rows) else 1

    if args.case_id:
        cases = load_claims()
        matches = [c for c in cases if c.get("id") == args.case_id]
        if not matches:
            print(f"No case id {args.case_id!r}", file=sys.stderr)
            return 2
        row = run_case(matches[0])
        print(json.dumps(row, indent=2))
        return 0 if row.get("passed") else 1

    if args.source:
        if not args.claim:
            print("--claim is required with --source", file=sys.stderr)
            return 2
        row = run_single_source(args.source, args.claim, args.function)
        print(json.dumps(row, indent=2))
        return 0 if row.get("actual") in {"SAT", "UNSAT"} else 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
