"""C* injection for DocCheck.

Two things happen:
1. The violation check is inserted INSIDE the target function, just before
   `return result;`.  This is what monster symbolically executes.
2. The existing main() is replaced with a symbolic harness that allocates
   pointer-based symbolic inputs via malloc + read(0, ...) and calls the
   target function.

Important C* rule:
Do NOT generate &x because C* does not support address-of.
Use pointer allocation instead:

  uint64_t* x_ptr;
  x_ptr = malloc(8);
  read(0, x_ptr, 8);
  x = *x_ptr;
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


class InjectionError(Exception):
    pass


@dataclass(frozen=True)
class FunctionSignature:
    return_type: str
    name: str
    params: list[tuple[str, str]]

    @property
    def param_names(self) -> list[str]:
        return [name for _, name in self.params]


FUNC_RE = re.compile(
    r"\b(?P<ret>uint64_t)\s+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*"
    r"\((?P<params>[^)]*)\)\s*\{",
    re.MULTILINE,
)


def _strip_comments(source: str) -> str:
    source = re.sub(r"//.*", "", source)
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    return source


def parse_params(params_text: str) -> list[tuple[str, str]]:
    params_text = params_text.strip()

    if not params_text or params_text == "void":
        return []

    params: list[tuple[str, str]] = []

    for raw in params_text.split(","):
        part = " ".join(raw.strip().split())

        m = re.fullmatch(r"(uint64_t)\s+([A-Za-z_][A-Za-z0-9_]*)", part)
        if not m:
            raise InjectionError(
                f"Unsupported parameter {part!r}. "
                "Only uint64_t value parameters are supported."
            )

        params.append((m.group(1), m.group(2)))

    return params


def find_function_signature(
    source: str,
    function_name: str | None = None,
) -> FunctionSignature:
    clean = _strip_comments(source)

    matches = list(FUNC_RE.finditer(clean))
    matches = [m for m in matches if m.group("name") != "main"]

    if function_name:
        matches = [m for m in matches if m.group("name") == function_name]

    if not matches:
        raise InjectionError(f"No uint64_t target function found for name={function_name!r}")

    if len(matches) > 1 and not function_name:
        names = [m.group("name") for m in matches]
        raise InjectionError(
            f"Multiple target functions found {names}; specify function name in claims.json"
        )

    m = matches[0]

    return FunctionSignature(
        return_type=m.group("ret"),
        name=m.group("name"),
        params=parse_params(m.group("params")),
    )


def _insert_check_before_return(source: str, func_name: str, violation_expr: str) -> str:
    """Insert the violation check INSIDE the function, just before `return result;`.

    Finds the target function body and replaces:
        return result;
    with:
        if (violation_expr)
          exit(1);
        return result;

    Only the LAST `return result;` inside the function body is patched,
    which is the standard single-exit C* pattern.
    """
    clean = _strip_comments(source)

    # Locate the function opening brace in the original (non-stripped) source.
    # We use the clean copy to find position, then map back to the original.
    m = FUNC_RE.search(clean)
    for candidate in FUNC_RE.finditer(clean):
        if candidate.group("name") == func_name:
            m = candidate
            break
    else:
        raise InjectionError(f"Cannot find function {func_name!r} to patch")

    # Walk the braces to find the function body extent.
    start_brace = source.find("{", m.start())
    depth = 0
    i = start_brace
    func_end = -1
    while i < len(source):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                func_end = i
                break
        i += 1

    if func_end == -1:
        raise InjectionError(f"Could not find closing brace for {func_name!r}")

    func_body = source[start_brace:func_end + 1]

    # Find the last `return result;` inside the function body.
    return_pattern = re.compile(r"(\breturn result\s*;)")
    last_match = None
    for match in return_pattern.finditer(func_body):
        last_match = match

    if last_match is None:
        raise InjectionError(
            f"No `return result;` found in {func_name!r}. "
            "DocCheck requires functions to use a `result` variable and `return result;`."
        )

    # Detect indentation of the return statement.
    line_start = func_body.rfind("\n", 0, last_match.start()) + 1
    indent = ""
    for ch in func_body[line_start:]:
        if ch in (" ", "\t"):
            indent += ch
        else:
            break

    check = (
        f"{indent}if ({violation_expr})\n"
        f"{indent}  exit(1);\n"
        f"{indent}{last_match.group(0)}"
    )

    patched_body = (
        func_body[: last_match.start()]
        + check
        + func_body[last_match.end():]
    )

    return source[:start_brace] + patched_body + source[func_end + 1:]


def remove_existing_main(source: str) -> str:
    """Remove existing uint64_t main() to avoid duplicate main definitions."""

    m = re.search(r"\buint64_t\s+main\s*\([^)]*\)\s*\{", source)
    if not m:
        return source.rstrip() + "\n"

    start = m.start()
    brace = source.find("{", m.end() - 1)

    depth = 0
    i = brace

    while i < len(source):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                return (source[:start] + source[end:]).rstrip() + "\n"
        i += 1

    raise InjectionError("Found main() but could not match its closing brace")


def build_main_harness(sig: FunctionSignature) -> str:
    """Generate valid C* main() harness.

    For each function parameter p, generate:

      uint64_t* p_ptr;
      uint64_t p;
      p_ptr = malloc(8);
      read(0, p_ptr, 8);
      p = *p_ptr;

    Then call the function and exit(0).
    The violation check lives inside the function itself (injected by
    _insert_check_before_return), so main() does not need to inspect result.
    """

    lines: list[str] = []

    lines.append("uint64_t main() {")

    # Pointer declarations first (C* requires all declarations before statements)
    for _, name in sig.params:
        lines.append(f"  uint64_t* {name}_ptr;")

    # Value declarations
    for _, name in sig.params:
        lines.append(f"  uint64_t {name};")

    lines.append("")

    # Allocate memory for each symbolic input
    for _, name in sig.params:
        lines.append(f"  {name}_ptr = malloc(8);")

    if sig.params:
        lines.append("")

    # Read symbolic bytes into allocated memory
    for _, name in sig.params:
        lines.append(f"  read(0, {name}_ptr, 8);")

    if sig.params:
        lines.append("")

    # Load symbolic values into normal uint64_t variables
    for _, name in sig.params:
        lines.append(f"  {name} = *{name}_ptr;")

    if sig.params:
        lines.append("")

    call_args = ", ".join(sig.param_names)
    lines.append(f"  {sig.name}({call_args});")
    lines.append("")
    lines.append("  exit(0);")
    lines.append("}")

    return "\n".join(lines) + "\n"


def inject_harness(
    source: str,
    violation_expr: str,
    function_name: str | None = None,
) -> tuple[str, FunctionSignature]:
    sig = find_function_signature(source, function_name)

    # Step 1: insert violation check inside the function before return result;
    patched = _insert_check_before_return(source, sig.name, violation_expr)

    # Step 2: replace main() with symbolic harness
    patched = remove_existing_main(patched)
    harness = build_main_harness(sig)

    patched = patched.rstrip() + "\n\n" + harness
    return patched, sig


def inject_file(
    input_path: Path,
    output_path: Path,
    violation_expr: str,
    function_name: str | None = None,
) -> FunctionSignature:
    source = input_path.read_text(encoding="utf-8")
    patched, sig = inject_harness(source, violation_expr, function_name)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(patched, encoding="utf-8")

    return sig
