"""
inject.py — injects violation check using a local flag in main().
"""
import re

def inject_check(source: str, check_statement: str) -> str:
    """
    Two changes:
    1. Insert check before return result — sets a local flag
    2. Rewrite main() to use local flag and return it
    """
    if "return result;" not in source:
        raise ValueError("Could not find 'return result;' in source")

    # Step 1: inject check — keep return 1 as is
    source = source.replace(
        "return result;",
        f"  {check_statement}\n  return result;"
    )

    # Step 2: rewrite main to capture return value
    # C* requires: all declarations before any statements
    source = re.sub(
        r'uint64_t main\(\) \{(\s+)uint64_t\* x;(\s+x = malloc[^;]+;)(\s+\*x = 0;)(\s+read\(0, x, 8\);)(\s+)(\w+)\(\*x\);(\s+)return 0;\n\}',
        r'uint64_t main() {\1uint64_t r;\1uint64_t* x;\2\3\4\5r = \6(*x);\7return r;\n}',
        source
    )
    return source