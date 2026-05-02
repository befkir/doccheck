"""C* injection for DocCheck.

Keeps the original target function unchanged and appends a generated
uint64_t main() harness.

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


def build_main_harness(sig: FunctionSignature, violation_expr: str) -> str:
    """Generate valid C* main() harness.

    For each function parameter p, generate:

      uint64_t* p_ptr;
      uint64_t p;
      p_ptr = malloc(8);
      read(0, p_ptr, 8);
      p = *p_ptr;

    Then call:

      result = function(p1, p2, ...);

    Then check violation:

      if (violation_expr)
        return 1;

      return 0;
    """

    lines: list[str] = []

    lines.append("uint64_t main() {")

    # Pointer declarations
    for _, name in sig.params:
        lines.append(f"  uint64_t* {name}_ptr;")

    # Value declarations
    for _, name in sig.params:
        lines.append(f"  uint64_t {name};")

    lines.append("  uint64_t result;")
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
    lines.append(f"  result = {sig.name}({call_args});")
    lines.append("")

    lines.append(f"  if ({violation_expr})")
    lines.append("    return 1;")
    lines.append("")
    lines.append("  return 0;")
    lines.append("}")

    return "\n".join(lines) + "\n"


def inject_harness(
    source: str,
    violation_expr: str,
    function_name: str | None = None,
) -> tuple[str, FunctionSignature]:
    sig = find_function_signature(source, function_name)
    base = remove_existing_main(source)
    harness = build_main_harness(sig, violation_expr)

    patched = base.rstrip() + "\n\n" + harness
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
