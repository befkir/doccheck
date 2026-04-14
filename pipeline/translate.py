"""
translate.py — LLM-based claim translation using Ollama/llama3.2.
This is the exp/llm-ollama experiment branch implementation.
Interface contract: translate_claim(source, claim) -> str
"""
import urllib.request
import json

PROMPT_TEMPLATE = open("prompts/claim_to_assert.txt").read()

def translate_claim(function_source: str, claim: str) -> str:
    """
    Translate a natural language claim into a C* violation check statement.
    Args:
        function_source : full C* function source code
        claim           : English claim
    Returns:
        C* if-statement string e.g. "if (result < 0) { return 1; }"
    """
    prompt = PROMPT_TEMPLATE.format(
        function_source=function_source,
        claim=claim
    )
    data = json.dumps({
        "model": "llama3.2",
        "prompt": prompt,
        "stream": False
    }).encode()

    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())

    raw = result["response"].strip().split('\n')[0].strip()
    # normalise common LLM substitutions
    raw = raw.replace("absolute(x)", "result").replace("absolute(*x)", "result")
    return raw
