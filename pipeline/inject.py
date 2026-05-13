"""
inject.py — inserts a C* violation check before the return statement
and patches main() to propagate the return value so the non-zero
exit code bad state fires in BTOR2 symbolic execution.
"""
import re

def inject_check(source: str, check_statement: str) -> str:
    """
    Two patches:
    1. Insert check_statement before 'return result;' in the function
    2. Make main() return the function result instead of 0
       so non-zero exit code fires when violation is detected
    """
    if "return result;" not in source:
        raise ValueError("Could not find 'return result;' in source")

    # Patch 1: inject the violation check
    source = source.replace(
        "return result;",
        f"  {check_statement}\n  return result;"
    )

    # Patch 2: make main() return the function result
    # change: funcname(*x);\n  return 0;
    # to:     return funcname(*x);
    source = re.sub(
        r'(\s+)(\w+\(\*x\));(\s+)return 0;',
        r'\1return \2;',
        source
    )

    return source