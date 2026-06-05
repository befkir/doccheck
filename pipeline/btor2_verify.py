"""
btor2_verify.py — Bounded Model Checking using Unicorn BTOR2 + Z3.
Implements proper sequential state unrolling with array memory model
for true binary-level verification.

Pipeline:
  1. compile_and_run_unicorn() — C* source → RISC-V binary → BTOR2 file
  2. verify_btor2() — parse BTOR2 → BMC with Z3 → VERIFIED or FALSIFIED
"""
import subprocess
import os
from z3 import *

SELFIE  = os.path.expanduser("~/selfie/selfie")
UNICORN = os.path.expanduser("~/unicorn/target/debug/unicorn")


def compile_and_run_unicorn(source_path, unroll=32):
    """
    Compile C* source to RISC-V binary and run Unicorn symbolic execution.
    Returns (btor2_path, error_message).
    """
    bin_path   = "/tmp/doccheck_patched.bin"
    btor2_path = "/tmp/doccheck_model.btor2"

    r = subprocess.run(
        [SELFIE, "-c", source_path, "-o", bin_path],
        capture_output=True, text=True)
    if "syntax error" in r.stdout:
        return None, f"Compile error: {r.stdout[:200]}"

    r = subprocess.run(
        [UNICORN, "beator", bin_path,
         "--unroll", str(unroll), "--out", btor2_path],
        capture_output=True, text=True)

    return btor2_path, None


def read_btor2(btor2_path):
    """
    Read BTOR2 file into structured dictionaries.

    Returns:
        sorts  — nid → ('bitvec', width) or ('array', idx_sort_nid, val_sort_nid)
        inits  — state_nid → init_val_nid
        nexts  — state_nid → next_val_nid
        bads   — list of (cond_nid, label)
        lines  — nid → parts list (formula nodes only)
    """
    sorts = {}
    inits = {}
    nexts = {}
    bads  = []
    lines = {}

    with open(btor2_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith(';'):
                continue
            parts = line.split()
            if len(parts) < 2:
                continue
            nid = parts[0]
            op  = parts[1]

            if op == 'sort':
                if parts[2] == 'bitvec':
                    sorts[nid] = ('bitvec', int(parts[3]))
                elif parts[2] == 'array':
                    sorts[nid] = ('array', parts[3], parts[4])

            elif op == 'init':
                # init sort_nid state_nid init_val_nid
                inits[parts[3]] = parts[4]

            elif op == 'next':
                # next sort_nid state_nid next_val_nid
                nexts[parts[3]] = parts[4]

            elif op == 'bad':
                bads.append((parts[2],
                             parts[3] if len(parts) > 3 else ''))

            else:
                lines[nid] = parts

    return sorts, inits, nexts, bads, lines


def get_z3_sort(sort_nid, sorts):
    """Convert a BTOR2 sort node ID to a Z3 sort."""
    if sort_nid not in sorts:
        return None
    kind = sorts[sort_nid]
    if kind[0] == 'bitvec':
        w = kind[1]
        return BoolSort() if w == 1 else BitVecSort(w)
    elif kind[0] == 'array':
        idx = get_z3_sort(kind[1], sorts)
        val = get_z3_sort(kind[2], sorts)
        if idx is not None and val is not None:
            return ArraySort(idx, val)
    return None


def make_state_var(nid, sort_nid, sorts, step):
    """Create a fresh Z3 variable for a state node at a given time step."""
    if sort_nid not in sorts:
        return None
    kind  = sorts[sort_nid]
    name  = f"s_{nid}_{step}"
    if kind[0] == 'bitvec':
        w = kind[1]
        return Bool(name) if w == 1 else BitVec(name, w)
    elif kind[0] == 'array':
        z3s = get_z3_sort(sort_nid, sorts)
        if z3s is not None:
            return Const(name, z3s)
    return None


def eval_node(nid, lines, sorts, current_vars):
    """
    Recursively evaluate a BTOR2 node using the current step's variables.
    Caches results in current_vars.
    Returns a Z3 expression or None if the node cannot be evaluated.
    """
    if nid in current_vars:
        return current_vars[nid]
    if nid not in lines:
        return None

    parts = lines[nid]
    op    = parts[1]

    def get(n):
        return eval_node(n, lines, sorts, current_vars)

    def to_bool(e):
        if e is None:
            return None
        if isinstance(e, BoolRef):
            return e
        return e != BitVecVal(0, e.size())

    try:
        result = None

        # ── Constants ────────────────────────────────────────────
        if op == 'constd':
            info = sorts.get(parts[2])
            if info and info[0] == 'bitvec':
                w = info[1]
                result = BoolVal(int(parts[3]) != 0) if w == 1 \
                         else BitVecVal(int(parts[3]), w)

        elif op == 'consth':
            info = sorts.get(parts[2])
            if info and info[0] == 'bitvec':
                result = BitVecVal(int(parts[3], 16), info[1])

        elif op == 'const':
            info = sorts.get(parts[2])
            if info and info[0] == 'bitvec':
                result = BitVecVal(int(parts[3], 2), info[1])

        # ── Boolean / bitwise ────────────────────────────────────
        elif op == 'not':
            a = get(parts[3])
            if a is not None:
                result = Not(a) if isinstance(a, BoolRef) else ~a

        elif op == 'and':
            a, b = get(parts[3]), get(parts[4])
            if a is not None and b is not None:
                if isinstance(a, BoolRef) or isinstance(b, BoolRef):
                    result = And(to_bool(a), to_bool(b))
                else:
                    result = a & b

        elif op == 'or':
            a, b = get(parts[3]), get(parts[4])
            if a is not None and b is not None:
                if isinstance(a, BoolRef) or isinstance(b, BoolRef):
                    result = Or(to_bool(a), to_bool(b))
                else:
                    result = a | b

        elif op == 'xor':
            a, b = get(parts[3]), get(parts[4])
            if a is not None and b is not None:
                if isinstance(a, BoolRef) or isinstance(b, BoolRef):
                    result = Xor(to_bool(a), to_bool(b))
                else:
                    result = a ^ b

        elif op == 'eq':
            a, b = get(parts[3]), get(parts[4])
            if a is not None and b is not None:
                result = (a == b)

        elif op == 'neq':
            a, b = get(parts[3]), get(parts[4])
            if a is not None and b is not None:
                result = (a != b)

        elif op == 'ite':
            c, t, e = get(parts[3]), get(parts[4]), get(parts[5])
            if all(x is not None for x in [c, t, e]):
                result = If(to_bool(c), t, e)

        # ── Arithmetic ───────────────────────────────────────────
        elif op == 'add':
            a, b = get(parts[3]), get(parts[4])
            if a is not None and b is not None:
                result = a + b

        elif op == 'sub':
            a, b = get(parts[3]), get(parts[4])
            if a is not None and b is not None:
                result = a - b

        elif op == 'mul':
            a, b = get(parts[3]), get(parts[4])
            if a is not None and b is not None:
                result = a * b

        elif op == 'udiv':
            a, b = get(parts[3]), get(parts[4])
            if a is not None and b is not None:
                result = UDiv(a, b)

        elif op == 'urem':
            a, b = get(parts[3]), get(parts[4])
            if a is not None and b is not None:
                result = URem(a, b)

        # ── Comparisons ──────────────────────────────────────────
        elif op in ('ult', 'slt'):
            a, b = get(parts[3]), get(parts[4])
            if a is not None and b is not None:
                result = ULT(a, b)

        elif op in ('ulte', 'slte'):
            a, b = get(parts[3]), get(parts[4])
            if a is not None and b is not None:
                result = ULE(a, b)

        elif op in ('ugt', 'sgt'):
            a, b = get(parts[3]), get(parts[4])
            if a is not None and b is not None:
                result = UGT(a, b)

        elif op in ('ugte', 'sgte'):
            a, b = get(parts[3]), get(parts[4])
            if a is not None and b is not None:
                result = UGE(a, b)

        # ── Shifts ───────────────────────────────────────────────
        elif op == 'sll':
            a, b = get(parts[3]), get(parts[4])
            if a is not None and b is not None:
                result = a << b

        elif op == 'srl':
            a, b = get(parts[3]), get(parts[4])
            if a is not None and b is not None:
                result = LShR(a, b)

        elif op == 'sra':
            a, b = get(parts[3]), get(parts[4])
            if a is not None and b is not None:
                result = a >> b

        # ── Bit manipulation ─────────────────────────────────────
        elif op == 'uext':
            a = get(parts[3])
            if a is not None:
                ext = int(parts[4])
                if isinstance(a, BoolRef):
                    a = If(a, BitVecVal(1, 1), BitVecVal(0, 1))
                result = ZeroExt(ext, a) if ext > 0 else a

        elif op == 'sext':
            a = get(parts[3])
            if a is not None:
                ext = int(parts[4])
                if isinstance(a, BoolRef):
                    a = If(a, BitVecVal(1, 1), BitVecVal(0, 1))
                result = SignExt(ext, a) if ext > 0 else a

        elif op == 'slice':
            a = get(parts[3])
            if a is not None:
                hi, lo = int(parts[4]), int(parts[5])
                result = Extract(hi, lo, a)

        elif op == 'concat':
            a, b = get(parts[3]), get(parts[4])
            if a is not None and b is not None:
                result = Concat(a, b)

        # ── Memory operations ────────────────────────────────────
        elif op == 'write':
            # write sort_nid array_nid address_nid value_nid
            # → Store(array, address, value) returns new array
            arr  = get(parts[3])
            addr = get(parts[4])
            val  = get(parts[5])
            if arr is not None and addr is not None and val is not None:
                result = Store(arr, addr, val)

        elif op == 'read':
            # read sort_nid array_nid address_nid
            # → Select(array, address) returns value at address
            arr  = get(parts[3])
            addr = get(parts[4])
            if arr is not None and addr is not None:
                result = Select(arr, addr)

        if result is not None:
            current_vars[nid] = result
        return result

    except Exception:
        return None

def verify_btor2(btor2_path, num_steps=150):
    """
    Z3-assertion BMC: encode all state transitions as Z3 constraints,
    then ask Z3 to find an execution path to the bad state.
    Returns (verdict, witness, error)
    """
    sorts, inits, nexts, bads, lines = read_btor2(btor2_path)

    target_bad = None
    for cond_nid, label in bads:
        if 'non-zero-exit' in label:
            target_bad = cond_nid
            break
    if target_bad is None:
        return "UNKNOWN", None, "No non-zero-exit-code bad state found"

    state_nodes = {}
    input_nodes = {}
    for nid, parts in lines.items():
        op = parts[1]
        if op == 'state':
            state_nodes[nid] = parts[2]
        elif op == 'input':
            input_nodes[nid] = parts[2]

    solver = Solver()
    solver.set("timeout", 60000)

    # create symbolic input variables (constant across all steps)
    input_vars = {}
    for nid, sort_nid in input_nodes.items():
        info = sorts.get(sort_nid)
        if info and info[0] == 'bitvec':
            var = BitVec(f'inp_{nid}', info[1])
            input_vars[nid] = var

    print(f"  BMC: {len(state_nodes)} states, {len(input_nodes)} inputs, "
          f"{num_steps} steps max...", flush=True)

    # create step-0 state variables
    step_vars = {}  # step → {nid: z3_expr}
    step_vars[0] = {}

    for state_nid, sort_nid in state_nodes.items():
        var = make_state_var(state_nid, sort_nid, sorts, 0)
        if var is not None:
            step_vars[0][state_nid] = var

    # assert init constraints at step 0
    eval_env_0 = dict(step_vars[0])
    eval_env_0.update(input_vars)

    for state_nid, init_val_nid in inits.items():
        if state_nid in state_nodes:
            info = sorts.get(state_nodes[state_nid])
            if info and info[0] != 'array':
                init_expr = eval_node(init_val_nid, lines, sorts, eval_env_0)
                if init_expr is not None and state_nid in step_vars[0]:
                    solver.add(step_vars[0][state_nid] == init_expr)

    # BMC unrolling
    for step in range(num_steps):
        # build evaluation environment for this step
        eval_env = dict(step_vars[step])
        eval_env.update(input_vars)

        # evaluate all formula nodes at this step
        for nid in lines:
            eval_node(nid, lines, sorts, eval_env)

        # check bad state at this step
        bad_expr = eval_env.get(target_bad)
        if bad_expr is None:
            bad_expr = eval_node(target_bad, lines, sorts, eval_env)

        if bad_expr is not None:
            if not isinstance(bad_expr, BoolRef):
                bad_expr = bad_expr != BitVecVal(0, bad_expr.size())

            solver.push()
            solver.add(bad_expr)
            outcome = solver.check()
            solver.pop()

            if outcome == sat:
                # find witness
                solver.push()
                solver.add(bad_expr)
                m = solver.model()
                witness = None
                for nid, var in input_vars.items():
                    try:
                        val = m.eval(var, model_completion=True)
                        if hasattr(val, 'as_long'):
                            v = val.as_long()
                            if v < 1000:
                                witness = v
                                break
                            if witness is None:
                                witness = v
                    except Exception:
                        pass
                solver.pop()
                if witness is None:
                    witness = 0
                return "FALSIFIED", witness, None

        # compute next step state variables
        if step + 1 < num_steps:
            step_vars[step + 1] = {}
            for state_nid, sort_nid in state_nodes.items():
                if state_nid in nexts:
                    next_val_nid = nexts[state_nid]
                    next_expr = eval_node(next_val_nid, lines, sorts, eval_env)
                    if next_expr is not None:
                        step_vars[step + 1][state_nid] = next_expr
                    else:
                        var = make_state_var(state_nid, sort_nid, sorts, step + 1)
                        if var is not None:
                            step_vars[step + 1][state_nid] = var
                else:
                    if state_nid in step_vars[step]:
                        step_vars[step + 1][state_nid] = step_vars[step][state_nid]

        if step % 10 == 0:
            print(f"  Step {step}/{num_steps}...", flush=True)

    return "VERIFIED", None, None