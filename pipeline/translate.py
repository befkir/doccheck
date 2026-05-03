"""LLM claim translation for DocCheck.

Input: C* function source + natural-language claim.
Output: a validated violation expression string, e.g. "result < a".

The LLM must never output statements such as if/return/assert. Those are generated
by inject.py so the next pipeline steps receive predictable C*.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "claim_to_assert.txt"

FORBIDDEN_TOKENS = {
    "if", "while", "return", "assert", "include", "define", "bool", "int", "char",
    "uint64_t", "void", "main", "read", "malloc", "sizeof", "else",
}

ALLOWED_CHARS_RE = re.compile(r"^[A-Za-z0-9_\s()+\-*/%<>=!]+$")
COMPARISON_RE = re.compile(r"(==|!=|<=|>=|<|>)")
IDENT_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")


class TranslationError(Exception):
    pass


@dataclass(frozen=True)
class TranslationResult:
    violation_expr: str
    raw_response: str


def _client() -> OpenAI:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise TranslationError("OPENROUTER_API_KEY is not set")
    return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)


def build_prompt(function_source: str, claim: str) -> str:
    system_prompt = PROMPT_PATH.read_text(encoding="utf-8")
    return (
        f"{system_prompt}\n\n"
        "Now translate this case.\n\n"
        "Function source:\n"
        f"{function_source}\n\n"
        f"Claim: {claim}\n\n"
        "JSON output:"
    )


def _extract_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise TranslationError(f"LLM did not return JSON: {text!r}")
        return json.loads(text[start : end + 1])


def validate_violation_expr(expr: str, allowed_names: Iterable[str]) -> str:
    """Validate a C*-safe violation expression.

    This intentionally accepts only a small expression language to protect the
    downstream compiler and verifier.
    """
    if not isinstance(expr, str):
        raise TranslationError("violation_expr must be a string")

    expr = " ".join(expr.strip().split())
    if not expr:
        raise TranslationError("violation_expr is empty")

    if ";" in expr or "{" in expr or "}" in expr or "," in expr:
        raise TranslationError(f"forbidden punctuation in expression: {expr}")
    if "&&" in expr or "||" in expr or "!" in expr.replace("!=", ""):
        raise TranslationError(f"unsupported boolean operator in expression: {expr}")
    if not ALLOWED_CHARS_RE.match(expr):
        raise TranslationError(f"unsupported character in expression: {expr}")
    if not COMPARISON_RE.search(expr):
        raise TranslationError(f"expression must contain a comparison operator: {expr}")

    allowed = set(allowed_names) | {"result"}
    for ident in IDENT_RE.findall(expr):
        if ident in FORBIDDEN_TOKENS:
            raise TranslationError(f"forbidden keyword/type in expression: {ident}")
        if ident not in allowed:
            raise TranslationError(
                f"unknown identifier {ident!r}; allowed names are {sorted(allowed)}"
            )

    return expr


def translate_claim(
    function_source: str,
    claim: str,
    allowed_names: Iterable[str],
    *,
    retries: int = 1,
) -> TranslationResult:
    prompt = build_prompt(function_source, claim)
    model = os.getenv("OPENROUTER_MODEL", "openrouter/auto")
    client = _client()

    last_raw = ""
    last_error: Exception | None = None

    for attempt in range(retries + 1):
        if attempt > 0:
            prompt += (
                "\n\nYour previous answer was invalid. Return ONLY JSON like "
                "{\"violation_expr\":\"result < x\"}. No explanations."
            )
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            extra_headers={
                "HTTP-Referer": os.getenv("OPENROUTER_REFERER", "http://localhost:3000"),
                "X-Title": os.getenv("OPENROUTER_TITLE", "DocCheck"),
            },
        )
        last_raw = response.choices[0].message.content or ""
        try:
            data = _extract_json(last_raw)
            expr = validate_violation_expr(data.get("violation_expr"), allowed_names)
            return TranslationResult(violation_expr=expr, raw_response=last_raw)
        except Exception as exc:  # retry once with a stricter instruction
            last_error = exc

    raise TranslationError(f"translation_error: {last_error}; raw={last_raw!r}")
