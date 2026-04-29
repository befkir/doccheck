import sys
from core.parser import extract_claims_and_signatures
from core.symbolic_prep import inject_assertion
from core.evaluator import run_crosshair
from agents.generator import generate_assertion
from agents.translator import back_translate
from agents.critic import compare_claims

MAX_RETRIES = 3

def run_loop(claim, sig, source_code):
    """The Agentic Refinement Loop using dual-LLMs."""
    current_feedback = ""
    
    for i in range(MAX_RETRIES):
        print(f"[*] Iteration {i+1}...")
        
        # Step 1: Draft with Code-Model (Qwen)
        # Note: We pass feedback in the prompt if this isn't the first try
        assertion = generate_assertion(sig, claim + current_feedback)
        
        # Step 2: Syntax Validation
        import ast
        try:
            ast.parse(assertion)
        except SyntaxError as e:
            print(f"[-] Syntax error in generated assertion: {e}")
            current_feedback = f"\nPrevious attempt generated invalid Python syntax. Do not wrap the assertion in strings. Error: {e}"
            continue
            
        # Step 3: Back-translate with Code-Model (Qwen)
        translated = back_translate(assertion)
        
        # Step 4: Critical Analysis with Reasoning-Model (DeepSeek)
        is_match, feedback = compare_claims(claim, translated)
        
        if is_match:
            print("[+] Semantic match confirmed by Critic.")
            return assertion
        
        print(f"[-] Critic found mismatch: {feedback}")
        current_feedback = f"\nPrevious attempt failed. Feedback: {feedback}"
        
    return None

def main(target_file):
    # 1. Load and Parse
    with open(target_file, 'r') as f:
        source_code = f.read()
    
    claims_and_sigs = extract_claims_and_signatures(source_code)
    if not claims_and_sigs:
        print("[!] No # claim: found in file.")
        return

    total = len(claims_and_sigs)
    verified = 0

    for idx, item in enumerate(claims_and_sigs, 1):
        claim = item['claim']
        precondition = item.get('precondition')
        sig = item['signature']
        func_name = item['func_name']
        
        print(f"\n" + "="*40)
        print(f"[*] Research Goal {idx}/{total}: Verify '{claim}' for function '{func_name}'")
        if precondition:
            print(f"[*] Precondition: {precondition}")
        print("="*40)

        # 2. Start the Agentic Loop
        validated_assertion = run_loop(claim, sig, source_code)

        if validated_assertion:
            # 3. Final Verification with CrossHair
            print("[*] Running CrossHair Symbolic Execution...")
            instrumented_code = inject_assertion(source_code, validated_assertion, sig, func_name, precondition)
            verdict = run_crosshair(instrumented_code)
            
            print("\n" + "-"*30)
            print(f"FINAL RESEARCH VERDICT FOR '{func_name}'")
            print("-"*30)
            print(verdict)
            if "[OK]" in verdict:
                verified += 1
        else:
            print("[!] Failed to generate a logically sound assertion after retries.")
            
    print(f"\n[*] Summary: {verified}/{total} claims verified successfully.")

if __name__ == "__main__":
    # You can change this path to whatever test file you want to check
    test_file = sys.argv[1] if len(sys.argv) > 1 else "data/targets/test_code.py"
    main(test_file)