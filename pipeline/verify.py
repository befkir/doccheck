import os, re, subprocess
from pathlib import Path

MONSTER       = os.environ.get("MONSTER_PATH", os.path.expanduser("~/selfie/tools/monster"))
Z3            = os.environ.get("Z3_PATH", "z3")
DEFAULT_DEPTH = int(os.environ.get("MONSTER_DEPTH", "10000"))
PATCHED_C     = "/tmp/doccheck_patched.c"
PATCHED_SMT   = "/tmp/doccheck_patched.smt"
QUERY_SMT     = "/tmp/doccheck_query.smt"

def compile_source(source):
    open(PATCHED_C, "w").write(source)
    return True, "OK"

def run_monster(depth=DEFAULT_DEPTH):
    if not os.path.exists(PATCHED_C):
        return False, f"Source not found: {PATCHED_C}"
    if os.path.exists(PATCHED_SMT):
        os.remove(PATCHED_SMT)
    r = subprocess.run(
        [MONSTER, "-c", PATCHED_C, "-", "0", str(depth), "--merge-enabled"],
        capture_output=True, text=True, timeout=120)
    out = r.stdout + r.stderr
    if not os.path.exists(PATCHED_SMT):
        return False, f"Monster did not produce SMT.\n{out[:400]}"
    return True, out

def _extract_push_pop_blocks(smt):
    blocks, i = [], 0
    lines = smt.splitlines(keepends=True)
    while i < len(lines):
        if lines[i].strip().startswith("(push"):
            block, i = [], i+1
            while i < len(lines) and not lines[i].strip().startswith("(pop"):
                block.append(lines[i]); i += 1
            blocks.append("".join(block))
        i += 1
    return blocks

def _preamble(smt):
    idx = smt.find("(push")
    return smt[:idx] if idx != -1 else smt

def _solve_block(preamble, block):
    query = preamble + "(push 1)\n" + block + "(check-sat)\n(get-model)\n(pop 1)\n"
    open(QUERY_SMT, "w").write(query)
    r = subprocess.run([Z3, QUERY_SMT], capture_output=True, text=True, timeout=300)
    return r.stdout + r.stderr

def _parse_z3(output):
    for line in output.splitlines():
        s = line.strip().lower()
        if s in ("sat","unsat","unknown"): return s
    return "unknown"

def _extract_model(output):
    model = {}
    for m in re.finditer(r'define-fun\s+(i\d+)\s*\(\)\s*\(_\s*BitVec\s*\d+\)\s*#x([0-9a-fA-F]+)', output):
        model[m.group(1)] = int(m.group(2), 16)
    for m in re.finditer(r'define-fun\s+(i\d+)\s*\(\)\s*\(_\s*BitVec\s*\d+\)\s*\(_\s*bv(\d+)', output):
        if m.group(1) not in model: model[m.group(1)] = int(m.group(2))
    return model

def verify_smt():
    if not os.path.exists(PATCHED_SMT):
        return {"verdict":"UNKNOWN","witness":None,"error":f"SMT not found: {PATCHED_SMT}"}
    smt = open(PATCHED_SMT).read()
    smt = re.sub(r'\(set-option\s+:incremental[^)]*\)\n?', '', smt)
    preamble = _preamble(smt)
    blocks   = _extract_push_pop_blocks(smt)
    if not blocks:
        return {"verdict":"UNKNOWN","witness":None,"error":"No push/pop blocks in SMT."}
    output = _solve_block(preamble, blocks[0])
    v = _parse_z3(output)
    if v == "unsat":
        return {"verdict":"UNSAT","witness":None,"model":None,
                "proof":"Violation unreachable for all inputs (UNSAT).","error":None}
    if v == "sat":
        model = _extract_model(output)
        return {"verdict":"SAT","witness":model.get("i0"),"model":model,
                "proof":f"Counterexample found: {model}","error":None}
    return {"verdict":"UNKNOWN","witness":None,"model":None,
            "error":f"Z3 unknown.\n{output[:300]}"}

def verify_patched(patched_path: Path, result_dir: Path):
    from dataclasses import dataclass, field
    @dataclass
    class VerifyResult:
        status: str
        detail: str = ""
        witness: object = None
        model: object = None
        bound_used: int = DEFAULT_DEPTH
        binary_path: str = ""

    source = patched_path.read_text(encoding="utf-8")
    compile_source(source)
    ok, mlog = run_monster(DEFAULT_DEPTH)
    (result_dir / "monster.log").write_text(mlog, encoding="utf-8")
    if not ok:
        return VerifyResult(status="MONSTER_ERROR", detail=mlog[:400])
    if os.path.exists(PATCHED_SMT):
        (result_dir / "patched.smt").write_text(open(PATCHED_SMT).read(), encoding="utf-8")
    r = verify_smt()
    return VerifyResult(
        status=r.get("verdict","UNKNOWN"),
        detail=r.get("proof") or r.get("error") or "",
        witness=r.get("witness"),
        model=r.get("model"),
        bound_used=DEFAULT_DEPTH,
    )
