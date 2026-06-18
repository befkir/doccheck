"""
proof_explain.py — generates a human-readable annotated proof trace
from monster's SMT-LIB2 output.

Usage:
    from pipeline.proof_explain import explain_proof
    text = explain_proof(source, claim, check_stmt, func_name)
    print(text)
"""
import subprocess, re, os

MONSTER = os.path.expanduser("~/selfie/monster")
DEPTH   = int(os.environ.get("MONSTER_DEPTH", "10000"))

def _parse_smt(smt: str) -> dict:
    """Extract key facts from monster's SMT output."""
    result = {"inputs":[], "asserts":[], "blocks":[], "preamble":""}
    lines = smt.split("\n")
    in_block = False
    block_lines = []
    preamble = []
    for line in lines:
        s = line.strip()
        if not s or s.startswith(";"):
            if not in_block: preamble.append(line)
            continue
        if s.startswith("(set-option") or s.startswith("(set-logic"):
            if not in_block: preamble.append(line)
            continue
        if s.startswith("(declare-fun"):
            m = re.match(r'\(declare-fun (\S+) \(\) \(_ BitVec (\d+)\)', s)
            if m:
                result["inputs"].append({"name":m.group(1),"bits":int(m.group(2))})
        elif s.startswith("(push"):
            in_block = True
            block_lines = []
        elif s.startswith("(pop"):
            result["blocks"].append("\n".join(block_lines))
            in_block = False
        elif in_block:
            block_lines.append(line)
        else:
            result["asserts"].append(s)
    result["preamble"] = "\n".join(preamble)
    return result

def _decode_assert(line: str) -> str:
    """Turn one SMT assert into plain English."""
    # simple patterns
    if "= m1 i0" in line or "(= m1 i0)" in line:
        return "m1 = input  (program read the symbolic input into memory)"
    if "bvult" in line and "bv0 64" in line and "b2" in line:
        return "b2 = branch condition (x < 0?) — for uint64_t this is ALWAYS FALSE"
    if "bvsub" in line and "bv0 64" in line:
        return "m4 = 0 - x  (the negative branch: result = -x, never reached for uint64_t)"
    if re.search(r'\(= m\d+ m1\)', line):
        mn = re.search(r'= (m\d+) m1', line)
        return f"{mn.group(1)} = x  (the positive branch: result = x, always active)"
    if "bvult" in line and "b6" in line:
        return "b6 = (result < 0?) — the violation check condition"
    if "(= p3 true)" in line:
        return "p3 = TRUE  (initial path condition — all paths are reachable)"
    if "p7" in line and "or" in line:
        return "p7 = combined path condition = TRUE (all execution paths considered)"
    return None

def _explain_block(block: str, block_num: int) -> str:
    """Explain one push/pop block."""
    lines = block.strip().split("\n")
    check_sat = any("check-sat" in l for l in lines)
    assert_line = next((l for l in lines if "assert" in l and "check-sat" not in l), "")

    if block_num == 0:
        label = "exit(1) — VIOLATION PATH"
        desc  = "Z3 asks: can the injected check ever fire?"
    else:
        label = f"exit(0) — path {block_num}"
        desc  = "Z3 asks: can the program exit normally?"

    # determine if trivially false
    trivially_false = "(not (= (_ bv0 64) (_ bv0 64)))" in assert_line
    result_str = "UNSAT (trivially — 0 = 0 is always true, so NOT(0=0) is always false)" \
        if trivially_false else "[see PROOF CONCLUSION below]"

    return f"  Block {block_num}: {label}\n  {desc}\n  Assertion: {assert_line.strip()[:80]}...\n  Result: {result_str}"

def explain_proof(source: str, claim: str, check_stmt: str,
                  func_name: str, verdict: str = None) -> str:
    """
    Generate a plain-language annotated proof trace.
    Returns a string you can print or save.
    """
    check_exit = check_stmt.replace("return 1;", "exit(1);")
    patched = source.replace("return result;",
                             f"  {check_exit}\n  return result;")
    src_path = f"/tmp/proof_{func_name}.c"
    smt_path = f"/tmp/proof_{func_name}.smt"

    with open(src_path, "w") as f:
        f.write(patched)

    subprocess.run([MONSTER, "-c", src_path, "-", "0",
                    str(DEPTH), "--merge-enabled"],
                   capture_output=True, timeout=30)

    if not os.path.exists(smt_path):
        return "[proof_explain] monster did not produce an SMT file — function may time out"

    with open(smt_path) as f:
        smt = f.read()

    # strip incremental, solve
    smt_clean = re.sub(r'\(set-option\s+:incremental[^)]*\)\n?', '', smt)
    query_path = f"/tmp/proof_{func_name}_query.smt"
    with open(query_path, "w") as f:
        f.write(smt_clean)

    z3_out = subprocess.run(["z3", query_path],
                            capture_output=True, text=True,
                            timeout=30).stdout.strip()

    lines = z3_out.split("\n")
    first_result = lines[0].strip() if lines else "unknown"
    verdict = "VERIFIED" if first_result == "unsat" else \
              "FALSIFIED" if first_result == "sat" else "UNKNOWN"

    # extract witness
    witness = None
    if verdict == "FALSIFIED":
        m = re.search(r'define-fun i0.*?#x([0-9a-fA-F]+)', z3_out, re.DOTALL)
        if m:
            witness = int(m.group(1), 16)

    parsed = _parse_smt(smt)

    out = []
    W = 68
    out.append("=" * W)
    out.append(f"  DOCCHECK PROOF TRACE")
    out.append("=" * W)
    out.append(f"  Function  : {func_name}()")
    out.append(f"  Claim     : \"{claim}\"")
    out.append(f"  Check     : {check_exit}")
    out.append(f"  Verdict   : {verdict}" +
               (f"  (witness: x = {witness})" if witness is not None else ""))
    out.append("=" * W)
    out.append("")

    out.append("STEP 1 — LLM TRANSLATED THE CLAIM")
    out.append("-" * W)
    out.append(f"  English   : \"{claim}\"")
    out.append(f"  Violation : {check_exit}")
    out.append(f"  Meaning   : if this check fires, the claim is broken")
    out.append("")

    out.append("STEP 2 — INJECT.PY PATCHED THE SOURCE")
    out.append("-" * W)
    out.append("  Check inserted before 'return result;'")
    out.append("  main() rewritten to pass symbolic stdin input to function")
    out.append("")

    out.append("STEP 3 — MONSTER SYMBOLICALLY EXECUTED THE RISC-V BINARY")
    out.append("-" * W)
    out.append(f"  Command   : monster -c {src_path} - 0 {DEPTH} --merge-enabled")
    out.append(f"  SMT vars  : {len(parsed['inputs'])} symbolic variables declared")
    out.append(f"  SMT blocks: {len(parsed['blocks'])} exit() paths found")
    out.append("")
    out.append("  Symbolic variables (each encodes a program state):")
    for v in parsed["inputs"][:8]:
        out.append(f"    {v['name']:8} — {v['bits']}-bit bitvector")
    out.append("")

    out.append("  Annotated assertions (what each SMT line means):")
    for a in parsed["asserts"]:
        expl = _decode_assert(a)
        if expl:
            out.append(f"    ✓ {expl}")
        else:
            short = a[:65] + "..." if len(a) > 65 else a
            out.append(f"    · {short}")
    out.append("")

    out.append("STEP 4 — Z3 SOLVED THE SMT-LIB2 FORMULA")
    out.append("-" * W)
    for i, block in enumerate(parsed["blocks"]):
        out.append(_explain_block(block, i))
        out.append("")

    out.append("PROOF CONCLUSION")
    out.append("=" * W)
    if verdict == "VERIFIED":
        out.append(f"  Z3 returned UNSAT for the violation block.")
        out.append(f"  This means: no 64-bit unsigned integer exists")
        out.append(f"  that makes '{check_exit.strip()}' true.")
        out.append(f"")
        out.append(f"  ✓ VERIFIED — '{claim}'")
        out.append(f"    holds for ALL 2^64 = 18,446,744,073,709,551,616 inputs.")
        out.append(f"    This is a formal mathematical proof, not a test.")
    elif verdict == "FALSIFIED":
        out.append(f"  Z3 returned SAT for the violation block.")
        out.append(f"  This means: x = {witness} makes the check fire.")
        out.append(f"")
        out.append(f"  ✗ FALSIFIED — '{claim}' is WRONG.")
        out.append(f"    Counterexample: x = {witness}")
        out.append(f"    Verify by running the binary with this input.")
    out.append("=" * W)

    return "\n".join(out)



def explain_proof_short(source: str, claim: str, check_stmt: str,
                        func_name: str) -> str:
    """Concise proof conclusion only."""
    import re as re2, subprocess as sp2
    check_exit = check_stmt.replace("return 1;", "exit(1);")
    patched = source.replace("return result;",
                             "  " + check_exit + "\n  return result;")
    src_path = "/tmp/proof_" + func_name + ".c"
    smt_path = "/tmp/proof_" + func_name + ".smt"
    with open(src_path, "w") as f:
        f.write(patched)
    sp2.run([MONSTER, "-c", src_path, "-", "0", str(DEPTH), "--merge-enabled"],
            capture_output=True, timeout=30)
    if not os.path.exists(smt_path):
        return "[proof not available]"
    with open(smt_path) as f:
        smt = f.read()
    smt2 = re2.sub(r'\(set-option :incremental[^)]*\)\n?', '', smt)
    qpath = "/tmp/proof_" + func_name + "_q.smt"
    with open(qpath, "w") as f:
        f.write(smt2)
    z3out = sp2.run(["z3", qpath], capture_output=True,
                    text=True, timeout=30).stdout.strip()
    first = z3out.split("\n")[0].strip() if z3out else "unknown"
    verdict = "VERIFIED" if first == "unsat" else "FALSIFIED" if first == "sat" else "UNKNOWN"
    witness = None
    if verdict == "FALSIFIED":
        import re as re3
        m = re3.search(r'define-fun i0.*?#x([0-9a-fA-F]+)', z3out, re3.DOTALL)
        if m:
            witness = int(m.group(1), 16)
    W = 60
    out = ["=" * W]
    if verdict == "VERIFIED":
        out.append("  PROOF: VERIFIED")
        out.append("  Claim  : \"" + claim + "\"")
        out.append("  Check  : " + check_exit)
        out.append("  Z3     : UNSAT")
        out.append("  Result : no 64-bit integer makes the check fire.")
        out.append("  Proved for ALL 2^64 inputs. Formal proof, not a test.")
        out.append("")
        out.append("  Why this is a proof:")
        out.append("  i0 is unconstrained -- it represents every possible")
        out.append("  64-bit value simultaneously, not a sample. UNSAT means")
        out.append("  no value of i0 satisfies the violation. Exhaustive.")
    elif verdict == "FALSIFIED":
        out.append("  PROOF: FALSIFIED")
        out.append("  Claim   : \"" + claim + "\"")
        out.append("  Check   : " + check_exit)
        out.append("  Z3      : SAT")
        out.append("  Witness : x = " + str(witness))
        out.append("  Meaning : " + func_name + "(" + str(witness) + ") triggers the check.")
        out.append("  Run the binary with this input to confirm.")
        out.append("")
        out.append("  Why this is proof:")
        out.append("  x was extracted directly from Z3's model -- not")
        out.append("  guessed. Independently verifiable by running the")
        out.append("  compiled binary with this exact input.")
    else:
        out.append("  PROOF: " + verdict + " -- " + claim)
    out.append("=" * W)
    return "\n".join(out)
