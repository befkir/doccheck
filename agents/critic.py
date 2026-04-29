from .ollama_client import call_llm, CRITIC_MODEL

def compare_claims(original_claim, back_translated_claim):
    """Semantic comparison with logic-first tolerance."""
    system = (
        "You are a logical equivalence evaluator. Focus ONLY on the mathematical "
        "relationship between inputs and outputs. Ignore differences in phrasing, "
        "formality, or whether one is 'general' and the other 'specific'."
    )
    prompt = f"""
    Compare these two for CORE LOGICAL EQUIVALENCE:
    
    1. Original: "{original_claim}"
    2. Generated: "{back_translated_claim}"

    If both describe the SAME relationship (e.g., Output > Input), reply 'MATCH'.
    Otherwise, if there is a real mathematical contradiction (e.g., one says > and 
    the other says >=), explain the error.
    
    Decision:
    """
    result = call_llm(system, prompt, model=CRITIC_MODEL)
    return "MATCH" in result.upper(), result