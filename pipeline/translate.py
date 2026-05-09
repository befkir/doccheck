"""
translate.py — LLM-based claim translation with pluggable backends.

Supported backends (set via DOCCHECK_BACKEND env var):
  ollama      — local Ollama server (default, exp/llm-ollama branch)
  openrouter  — OpenRouter API      (exp/llm-openai branch)
  claude      — Anthropic Claude API directly

Interface contract (all branches):
    translate_claim(function_source: str, claim: str) -> str
"""

import os
import json
import re
import urllib.request
import urllib.error

# ---------------------------------------------------------------------------
# Shared prompt loading
# ---------------------------------------------------------------------------

def _load_prompt(template_name: str, **kwargs) -> str:
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "prompts", template_name
    )
    with open(path) as f:
        template = f.read()
    return template.format(**kwargs)


def _normalise_property(raw: str) -> str:
    """Strip markdown fences and common LLM noise from a semantic property."""
    line = raw.strip().split('\n')[0].strip()
    # Remove markdown code fences
    line = line.strip("`").strip()
    return line


def _negate_operator(op: str) -> str:
    """Deterministically negate a logical operator."""
    negation_table = {
        "<": ">=",
        "<=": ">",
        "==": "!=",
        "!=": "==",
        ">": "<=",
        ">=": "<"
    }
    return negation_table.get(op, "==")  # Default to == if unknown, though shouldn't happen


def translate_claim(function_source: str, claim: str, func_name: str = "", param_names: list[str] = None) -> str:
    """
    Translate a natural language claim into a C* violation check statement
    using a robust 4-step pipeline.
    """
    backend = os.environ.get("DOCCHECK_BACKEND", "ollama").lower()

    # Step 1: Extract Semantic Meaning
    prop_prompt = _load_prompt("semantic_property.txt", function_source=function_source, claim=claim)
    if backend == "ollama":
        raw_prop = _ask_ollama(prop_prompt)
    elif backend == "openrouter":
        raw_prop = _ask_openrouter(prop_prompt)
    elif backend == "claude":
        raw_prop = _ask_claude(prop_prompt)
    else:
        raise KeyError(f"Unknown backend '{backend}'")
    
    property_str = _normalise_property(raw_prop)
    
    # Step 2: Formalize into structured logic
    logic_prompt = _load_prompt("formalize_logic.txt", property=property_str)
    if DOCCHECK_BACKEND == "ollama":
        raw_logic = _ask_ollama(logic_prompt)
    elif DOCCHECK_BACKEND == "openrouter":
        raw_logic = _ask_openrouter(logic_prompt)
    elif DOCCHECK_BACKEND == "claude":
        raw_logic = _ask_claude(logic_prompt)
    
    try:
        # LLMs sometimes wrap JSON in code blocks
        json_match = re.search(r'\{.*\}', raw_logic, re.DOTALL)
        if json_match:
            logic_json = json.loads(json_match.group(0))
        else:
            logic_json = json.loads(raw_logic)
    except (json.JSONDecodeError, AttributeError):
        # Fallback if JSON parsing fails - try a simple regex-based extraction
        # This adds robustness if the LLM fails to output valid JSON
        match = re.search(r'^\s*(.+?)\s*([<>=!]+)\s*(.+?)\s*$', property_str)
        if match:
            logic_json = {"lhs": match.group(1), "op": match.group(2), "rhs": match.group(3)}
        else:
            raise ValueError(f"Could not formalize logic from: {raw_logic}")

    # Step 3: Negate Mechanically
    negated_op = _negate_operator(logic_json["op"])
    
    # Step 4: Generate Code Deterministically
    lhs = logic_json["lhs"]
    rhs = logic_json["rhs"]
    
    # Normalize result/params if needed (e.g. LLM pointer confusion)
    if func_name:
        synonyms = [re.escape(func_name), "abs"]
        pattern = re.compile(rf'({"|".join(synonyms)})\s*\([^)]*\)')
        lhs = pattern.sub("result", lhs)
        rhs = pattern.sub("result", rhs)
        
    for pname in (param_names or []):
        lhs = re.sub(rf'\*\s*{re.escape(pname)}', pname, lhs)
        lhs = re.sub(rf'\(\s*{re.escape(pname)}\s*\)', pname, lhs)
        rhs = re.sub(rf'\*\s*{re.escape(pname)}', pname, rhs)
        rhs = re.sub(rf'\(\s*{re.escape(pname)}\s*\)', pname, rhs)

    return f"if ({lhs} {negated_op} {rhs}) {{ exit(1); }}"


# ---------------------------------------------------------------------------
# Backend Configurations
# ---------------------------------------------------------------------------

OLLAMA_URL       = os.environ.get("OLLAMA_URL",   "http://172.27.0.1:11434/api/generate")
OLLAMA_MODEL     = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:3b")

OPENROUTER_URL   = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")
OPENROUTER_KEY   = os.environ.get("OPENROUTER_API_KEY", "")

CLAUDE_URL       = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL     = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514")
CLAUDE_KEY       = os.environ.get("ANTHROPIC_API_KEY", "")


# ---------------------------------------------------------------------------
# Backend: API Helpers
# ---------------------------------------------------------------------------


def _ask_ollama(prompt: str) -> str:
    payload = json.dumps({"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}).encode()
    req = urllib.request.Request(OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())["response"]

def _ask_openrouter(prompt: str) -> str:
    if not OPENROUTER_KEY: raise EnvironmentError("OPENROUTER_API_KEY is not set.")
    payload = json.dumps({"model": OPENROUTER_MODEL, "messages": [{"role": "user", "content": prompt}], "temperature": 0}).encode()
    req = urllib.request.Request(OPENROUTER_URL, data=payload, headers={"Content-Type": "application/json", "Authorization": f"Bearer {OPENROUTER_KEY}"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())["choices"][0]["message"]["content"]

def _ask_claude(prompt: str) -> str:
    if not CLAUDE_KEY: raise EnvironmentError("ANTHROPIC_API_KEY is not set.")
    payload = json.dumps({"model": CLAUDE_MODEL, "max_tokens": 1024, "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(CLAUDE_URL, data=payload, headers={"Content-Type": "application/json", "x-api-key": CLAUDE_KEY, "anthropic-version": "2023-06-01"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read())["content"][0]["text"]

DOCCHECK_BACKEND = os.environ.get("DOCCHECK_BACKEND", "ollama").lower()


def explain_result(source: str, claim: str, verdict: str, model: dict = None, formula: str = None) -> str:
    """Generate a Markdown explanation of the verification result."""
    backend = os.environ.get("DOCCHECK_BACKEND", "ollama").lower()
    prompt = _load_prompt(
        "explain_result.txt", 
        source=source, 
        claim=claim, 
        verdict=verdict, 
        model=json.dumps(model, indent=2) if model else "N/A", 
        formula=formula or "N/A"
    )

    if backend == "ollama":
        return _ask_ollama(prompt)
    elif backend == "openrouter":
        return _ask_openrouter(prompt)
    elif backend == "claude":
        return _ask_claude(prompt)
    
    return "LLM Explanation unavailable."