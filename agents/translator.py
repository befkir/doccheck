from .ollama_client import call_llm, GEN_MODEL

def back_translate(assertion):
    system = "Translate this Python assertion into a short 5-word logical property."
    prompt = f"Assertion: {assertion}"
    # Example output: "Return value exceeds input x"
    return call_llm(system, prompt, model=GEN_MODEL)