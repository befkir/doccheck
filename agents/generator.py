from .ollama_client import call_llm, GEN_MODEL

def generate_assertion(func_sig, claim):
    system = (
        "You are a formal verification expert. You write CrossHair assertions. "
        "RULES:\n"
        "1. Output ONLY the Python code. No Markdown formatting.\n"
        "2. Use variable names from the signature.\n"
        "3. Use '__return__' to represent the function's output.\n"
        "4. DO NOT use specific numbers like 1, 2, or 10 unless the claim mentions them.\n"
        "5. DO NOT use in-place methods like .sort(), .append(), or .pop(). They return None.\n"
        "6. To check if a list is sorted, use: all(__return__[i] <= __return__[i+1] for i in range(len(__return__)-1))\n"
        "7. NO explanations or backticks."
    )
    prompt = f"""
    Signature: {func_sig}
    Claim: {claim}

    Correct Example Format: assert __return__ > x
    Task: Write the assertion for the claim above.
    Result:
    """
    
    # Get raw response from LLM
    response = call_llm(system, prompt, model=GEN_MODEL)
    
    # --- Sanitization Logic ---
    # 1. Strip whitespace
    clean_code = response.strip()
    
    # 2. Remove Markdown backticks if the model ignored instructions
    if "```" in clean_code:
        # Split by lines and filter out any line containing backticks
        lines = clean_code.splitlines()
        clean_code = "\n".join([
            line for line in lines 
            if not line.strip().startswith("```")
        ])
    
    # 3. Final trim to ensure no trailing comments or spaces
    print("[][1] Code generated\n" +clean_code.strip())
    return clean_code.strip()