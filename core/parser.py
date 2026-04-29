import libcst as cst

def extract_claims_and_signatures(source_code):
    """
    Robustly extracts all natural language claims and their corresponding 
    function signatures using string analysis and basic AST parsing.
    Returns a list of dicts: [{"claim": text, "signature": sig, "func_name": name}]
    """
    lines = source_code.splitlines()
    
    results = []
    current_claim = None
    signature = ""
    found_def = False
    
    for line in lines:
        stripped = line.strip()
        
        # Look for the # claim: comment
        if "# claim:" in stripped:
            current_claim = stripped.split("# claim:")[1].strip()
            # Reset definition parsing state for the new claim
            signature = ""
            found_def = False
            continue
            
        if current_claim:
            if stripped.startswith("def "):
                found_def = True
            
            if found_def:
                # Add the line to the signature
                signature += " " + stripped
                # If we find the colon, the signature is complete
                if ":" in stripped:
                    # Clean up extra spaces
                    signature = " ".join(signature.split()).strip()
                    # Extract function name
                    func_name = signature.split("def ", 1)[1].split("(", 1)[0].strip()
                    
                    results.append({
                        "claim": current_claim,
                        "signature": signature,
                        "func_name": func_name
                    })
                    
                    # Reset state for next claim
                    current_claim = None
                    signature = ""
                    found_def = False
                    
    return results