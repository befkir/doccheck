import ollama

# Match these exactly to your 'ollama list' output
GEN_MODEL = "qwen2.5-coder:3b" 
CRITIC_MODEL = "qwen2.5-coder:3b" #"deepseek-r1:latest"    

def call_llm(system_prompt, user_prompt, model=GEN_MODEL):
    """Standardized LLM interface with model selection."""
    response = ollama.generate(
        model=model,
        system=system_prompt,
        prompt=user_prompt,
        options={"temperature": 0.1 if model == GEN_MODEL else 0.2}
    )
    return response['response'].strip()