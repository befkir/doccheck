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


def _normalise_response(raw: str, func_name: str, param_names: list[str]) -> str:
    """Strip markdown fences and common LLM noise from a raw response."""
    line = raw.strip().split('\n')[0].strip()
    # Remove markdown code fences if the LLM wrapped the output
    if line.startswith("```"):
        line = line.lstrip("`").strip()

    # Dynamically replace any call to the target function (or 'abs') with 'result'
    # e.g. "absolute(x)" -> "result", "abs(x)" -> "result"
    if func_name:
        synonyms = [re.escape(func_name), "abs"]
        pattern = re.compile(rf'({"|".join(synonyms)})\s*\([^)]*\)')
        line = pattern.sub("result", line)

    # Clean up potential LLM pointer-confusion for any parameter
    # e.g. "*x", "* x", "(*x)" -> "x"
    for pname in param_names:
        line = re.sub(rf'\*\s*{re.escape(pname)}', pname, line)
        line = re.sub(rf'\(\s*{re.escape(pname)}\s*\)', pname, line)

    # Standardize signaling to exit(1) as per new project requirement
    line = line.replace("return 1", "exit(1)").replace("return(1)", "exit(1)")

    return line


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


def translate_claim(function_source: str, claim: str, func_name: str = "", param_names: list[str] = None) -> str:
    """Translate a natural language claim into a C* violation check statement."""
    prompt = _load_prompt("claim_to_assert.txt", function_source=function_source, claim=claim)
    
    if DOCCHECK_BACKEND == "ollama":
        raw = _ask_ollama(prompt)
    elif DOCCHECK_BACKEND == "openrouter":
        raw = _ask_openrouter(prompt)
    elif DOCCHECK_BACKEND == "claude":
        raw = _ask_claude(prompt)
    else:
        raise KeyError(f"Unknown backend '{DOCCHECK_BACKEND}'")
        
    return _normalise_response(raw, func_name, param_names or [])


def explain_result(source: str, claim: str, verdict: str, model: dict = None, formula: str = None) -> str:
    """Generate a Markdown explanation of the verification result."""
    prompt = _load_prompt(
        "explain_result.txt", 
        source=source, 
        claim=claim, 
        verdict=verdict, 
        model=json.dumps(model, indent=2) if model else "N/A", 
        formula=formula or "N/A"
    )

    if DOCCHECK_BACKEND == "ollama":
        return _ask_ollama(prompt)
    elif DOCCHECK_BACKEND == "openrouter":
        return _ask_openrouter(prompt)
    elif DOCCHECK_BACKEND == "claude":
        return _ask_claude(prompt)
    
    return "LLM Explanation unavailable."