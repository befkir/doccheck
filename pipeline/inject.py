"""
inject.py — parses a C* function signature, injects a violation check before
'return result;', and builds a complete symbolic main() harness so the compiled
binary's reachability of 'return 1' is what the solver tests.

Shared across all experiment branches. Do not modify without team agreement.
"""

import re


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_signature(source: str) -> tuple[str, list[tuple[str, str]]]:
    """
    Extract function name and parameter list from a C* source file.

    Returns:
        (func_name, [(type, param_name), ...])

    Raises:
        ValueError if no non-main function can be found.
    """
    # Match:  <return_type> <name> ( <params> )  {
    pattern = re.compile(
        r'uint64_t\s+(?!main\b)(\w+)\s*\(([^)]*)\)\s*\{',
        re.MULTILINE
    )
    match = pattern.search(source)
    if not match:
        raise ValueError("Could not find a non-main function signature in source.")

    func_name = match.group(1)
    raw_params = match.group(2).strip()

    params: list[tuple[str, str]] = []
    if raw_params:
        for part in raw_params.split(','):
            part = part.strip()
            tokens = part.split()
            if len(tokens) >= 2:
                ptype = ' '.join(tokens[:-1])
                pname = tokens[-1]
                params.append((ptype, pname))

    return func_name, params


def _build_harness(func_name: str, params: list[tuple[str, str]]) -> str:
    """
    Build a C* main() harness that:
      1. Declares ALL local variables first (C* requires this before any statements)
      2. Allocates one symbolic uint64_t for each parameter via malloc + read(0,…,8)
      3. Calls the function under test and captures the return value
      4. Returns 0 (violation check is already injected into the function body)

    The harness replaces any existing main() in the source.
    """
    decls: list[str] = []
    stmts: list[str] = []

    # C* rule: ALL declarations must come before ANY statements
    decls.append("  uint64_t result;")
    for _, pname in params:
        ptr = f"{pname}_ptr"
        decls.append(f"  uint64_t* {ptr};")

    # Statements: malloc + read for each param
    for _, pname in params:
        ptr = f"{pname}_ptr"
        stmts.append(f"  {ptr} = malloc(sizeof(uint64_t));")
        stmts.append(f"  *{ptr} = 0;")
        stmts.append(f"  read(0, {ptr}, 8);")

    args = ", ".join(f"*{pname}_ptr" for _, pname in params)
    stmts.append(f"  result = {func_name}({args});")
    stmts.append(f"  return 0;")

    lines = ["uint64_t main() {"] + decls + [""] + stmts + ["}"]
    return "\n".join(lines)


def _strip_existing_main(source: str) -> str:
    """
    Remove an existing main() function from source so we can replace it
    with the generated harness.  Handles simple brace-matching.
    """
    # Find 'uint64_t main()' or 'int main()'
    start_match = re.search(r'(?:uint64_t|int)\s+main\s*\([^)]*\)\s*\{', source)
    if not start_match:
        return source  # nothing to strip

    depth = 0
    start = start_match.start()
    i = start_match.end() - 1  # position of the opening '{'

    while i < len(source):
        if source[i] == '{':
            depth += 1
        elif source[i] == '}':
            depth -= 1
            if depth == 0:
                # Strip from 'main' to closing '}' (inclusive), plus trailing newline
                end = i + 1
                stripped = source[:start].rstrip() + "\n" + source[end:].lstrip('\n')
                return stripped
        i += 1

    return source  # unbalanced braces — return unchanged


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def inject_check(source: str, check_statement: str) -> str:
    """
    Inject *check_statement* just before 'return result;' in the target
    function, then rebuild main() as a complete symbolic harness.

    Args:
        source          : full C* source code (must contain exactly one
                          non-main function with a 'return result;')
        check_statement : e.g. "if (result < 0) { return 1; }"

    Returns:
        Patched C* source ready to be compiled by starc.

    Raises:
        ValueError if 'return result;' cannot be found, or the signature
        cannot be parsed.
    """
    if "return result;" not in source:
        raise ValueError("Could not find 'return result;' in source — cannot inject check.")

    func_name, params = _parse_signature(source)

    # 1. Inject the violation check into the function body
    patched = source.replace(
        "return result;",
        f"  {check_statement}\n  return result;",
        1  # only the first occurrence (inside the target function)
    )

    # 2. Strip the old main() and append the generated harness
    patched = _strip_existing_main(patched)
    harness = _build_harness(func_name, params)
    patched = patched.rstrip() + "\n\n" + harness + "\n"

    return patched