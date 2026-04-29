import subprocess
import tempfile
import os
import sys
import re

def run_crosshair(code_string):
    """Executes symbolic verification and returns the research verdict."""
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode='w') as tmp:
        tmp.write(code_string)
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            [sys.executable, "-m", "crosshair", "check", tmp_path],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and not result.stdout and not result.stderr:
            return "Verified [OK]: The claim holds for all symbolic paths."
        
        output = result.stdout
        if result.stderr:
            output += f"\nSTDERR:\n{result.stderr}"
            
        # Clean up output: remove temp file path and wrapper function name
        output = re.sub(r'^.*\.py:\d+:\s*error:\s*', 'Error: ', output, flags=re.MULTILINE)
        output = output.replace('crosshair_checker', 'the target function')
            
        return f"Falsified [FAIL]: Counterexample found:\n{output.strip()}"
    except Exception as e:
        return f"Unknown: Timeout or undecidable path. Error: {str(e)}"
    finally:
        os.remove(tmp_path)