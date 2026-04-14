"""
inject.py — inserts a C* violation check before the return statement.
Shared across all experiment branches. Do not modify without team agreement.
"""

def inject_check(source: str, check_statement: str) -> str:
    """
    Insert check_statement just before 'return result;' in source.
    Args:
        source          : full C* source code
        check_statement : e.g. "if (result < 0) { return 1; }"
    Returns:
        patched C* source with check injected
    """
    if "return result;" not in source:
        raise ValueError("Could not find 'return result;' in source to inject check")
    return source.replace(
        "return result;",
        f"  {check_statement}\n  return result;"
    )
