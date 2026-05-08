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
import urllib.request
import urllib.error

# ---------------------------------------------------------------------------
# Shared prompt loading
# ---------------------------------------------------------------------------

_PROMPT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "prompts", "claim_to_assert.txt"
)

def _load_prompt(function_source: str, claim: str) -> str:
    with open(_PROMPT_PATH) as f:
        template = f.read()
    return template.format(function_source=function_source, claim=claim)


def _normalise_response(raw: str) -> str:
    """Strip markdown fences and common LLM noise from a raw response."""
    line = raw.strip().split('\n')[0].strip()
    # Remove markdown code fences if the LLM wrapped the output
    if line.startswith("```"):
        line = line.lstrip("`").strip()
    line = line.replace("absolute(x)", "result")
    line = line.replace("absolute(*x)", "result")
    line = line.replace("*x", "x")
    return line


# ---------------------------------------------------------------------------
# Backend: Ollama (local)
# ---------------------------------------------------------------------------

OLLAMA_URL   = os.environ.get("OLLAMA_URL",   "http://172.27.0.1:11434/api/generate")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:3b")


def _translate_ollama(function_source: str, claim: str) -> str:
    prompt = _load_prompt(function_source, claim)
    payload = json.dumps({
        "model":  OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
    }).encode()

    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())

    return _normalise_response(data["response"])


# ---------------------------------------------------------------------------
# Backend: OpenRouter
# ---------------------------------------------------------------------------

OPENROUTER_URL   = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini")
OPENROUTER_KEY   = os.environ.get("OPENROUTER_API_KEY", "")


def _translate_openrouter(function_source: str, claim: str) -> str:
    if not OPENROUTER_KEY:
        raise EnvironmentError("OPENROUTER_API_KEY is not set.")

    prompt = _load_prompt(function_source, claim)
    payload = json.dumps({
        "model": OPENROUTER_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0,
    }).encode()

    req = urllib.request.Request(
        OPENROUTER_URL,
        data=payload,
        headers={
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {OPENROUTER_KEY}",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())

    raw = data["choices"][0]["message"]["content"]
    return _normalise_response(raw)


# ---------------------------------------------------------------------------
# Backend: Anthropic Claude API
# ---------------------------------------------------------------------------

CLAUDE_URL   = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514")
CLAUDE_KEY   = os.environ.get("ANTHROPIC_API_KEY", "")


def _translate_claude(function_source: str, claim: str) -> str:
    if not CLAUDE_KEY:
        raise EnvironmentError("ANTHROPIC_API_KEY is not set.")

    prompt = _load_prompt(function_source, claim)
    payload = json.dumps({
        "model":      CLAUDE_MODEL,
        "max_tokens": 256,
        "messages":   [{"role": "user", "content": prompt}],
    }).encode()

    req = urllib.request.Request(
        CLAUDE_URL,
        data=payload,
        headers={
            "Content-Type":      "application/json",
            "x-api-key":         CLAUDE_KEY,
            "anthropic-version": "2023-06-01",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())

    raw = data["content"][0]["text"]
    return _normalise_response(raw)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_BACKENDS = {
    "ollama":      _translate_ollama,
    "openrouter":  _translate_openrouter,
    "claude":      _translate_claude,
}

DOCCHECK_BACKEND = os.environ.get("DOCCHECK_BACKEND", "ollama").lower()


def translate_claim(function_source: str, claim: str) -> str:
    """
    Translate a natural language claim into a C* violation check statement.

    Backend is selected by the DOCCHECK_BACKEND environment variable:
        ollama      (default) — requires local Ollama with llama3.2
        openrouter            — requires OPENROUTER_API_KEY
        claude                — requires ANTHROPIC_API_KEY

    Args:
        function_source : full C* function source code
        claim           : English claim e.g. "never returns a negative value"

    Returns:
        C* if-statement string e.g. "if (result < 0) { return 1; }"

    Raises:
        KeyError           if DOCCHECK_BACKEND is not a known backend
        EnvironmentError   if a required API key is missing
        urllib.error.URLError / OSError on network failure
    """
    if DOCCHECK_BACKEND not in _BACKENDS:
        raise KeyError(
            f"Unknown backend '{DOCCHECK_BACKEND}'. "
            f"Choose one of: {', '.join(_BACKENDS)}"
        )
    return _BACKENDS[DOCCHECK_BACKEND](function_source, claim)