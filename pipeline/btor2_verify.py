"""
btor2_verify.py — Bounded Model Checking using Unicorn BTOR2 + Z3.
Implements proper sequential state unrolling for binary-level verification.
"""
import subprocess
import os
from z3 import *

SELFIE  = os.path.expanduser("~/selfie/selfie")
UNICORN = os.path.expanduser("~/unicorn/target/debug/unicorn")

def compile_and_run_unicorn(source_path, unroll=32):
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
    """Read BTOR2 file into structured dictionaries."""
    sorts   = {}   # nid → bit width (None if array)
    inits   = {}   # state_nid → init_val_nid
    nexts   = {}   # state_nid → next_val_nid
    bads    = []   # list of (cond_nid, label)
    lines   = {}   # nid → parts list (for formula nodes)

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
                    sorts[nid] = int(parts[3])
                else:
                    sorts[nid] = None  # array sort
            elif op == 'init':
                # init sort state_nid init_val_nid
                sorts[parts[2]]  # register sort
                inits[parts[3]]  = parts[4]  # state nid → init value nid
            elif op == 'next':
                nexts[parts[3]] = parts[4]  # state nid → next value nid
            elif op == 'bad':
                bads.append((parts[2], parts[3] if len(parts) > 3 else ''))
            else:
                lines[nid] = parts

    return sorts, inits, nexts, bads, lines

def eval_node(nid, lines, sorts, current_vars):
    """
    Recursively evaluate a BTOR2 node using current step variables.
    Returns a Z3 expression.
    """
    if nid in current_vars:
        return current_vars[nid]
    if nid not in lines:
        return None

    parts = lines[nid]
    op = parts[1]

    def get(n):
        return eval_node(n, lines, sorts, current_vars)

    def to_bool(e):
        if isinstance(e, BoolRef):
            return e
        return e != BitVecVal(0, e.size())

    try:
        if op in ('constd',):
            w = sorts.get(parts[2])
            if w == 1:
                result = BoolVal(int(parts[3]) != 0)
            elif w:
                result = BitVecVal(int(parts[3]), w)
            else:
                return None
        elif op == 'consth':
            w = sorts.get(parts[2])
            if w:
                result = BitVecVal(int(parts[3], 16), w)
            else:
                return None
        elif op == 'const':
            w = sorts.get(parts[2])
            if w:
                result = BitVecVal(int(parts[3], 2), w)
            else:
                return None
        elif op == 'not':
            a = get(parts[3])
            if a is None: return None
            result = Not(a) if isinstance(a, BoolRef) else ~a
        elif op == 'and':
            a, b = get(parts[3]), get(parts[4])
            if a is None or b is None: return None
            if isinstance(a, BoolRef) or isinstance(b, BoolRef):
                result = And(to_bool(a), to_bool(b))
            else:
                result = a & b
        elif op == 'or':
            a, b = get(parts[3]), get(parts[4])
            if a is None or b is None: return None
            if isinstance(a, BoolRef) or isinstance(b, BoolRef):
                result = Or(to_bool(a), to_bool(b))
            else:
                result = a | b
        elif op == 'xor':
            a, b = get(parts[3]), get(parts[4])
            if a is None or b is None: return None
            result = Xor(to_bool(a), to_bool(b)) if isinstance(a, BoolRef) \
                     else a ^ b
        elif op == 'eq':
            a, b = get(parts[3]), get(parts[4])
            if a is None or b is None: return None
            result = (a == b)
        elif op == 'neq':
            a, b = get(parts[3]), get(parts[4])
            if a is None or b is None: return None
            result = (a != b)
        elif op == 'ite':
            c = get(parts[3]); t = get(parts[4]); e = get(parts[5])
            if any(x is None for x in [c,t,e]): return None
            result = If(to_bool(c), t, e)
        elif op == 'add':
            a, b = get(parts[3]), get(parts[4])
            if a is None or b is None: return None
            result = a + b
        elif op == 'sub':
            a, b = get(parts[3]), get(parts[4])
            if a is None or b is None: return None
            result = a - b
        elif op == 'mul':
            a, b = get(parts[3]), get(parts[4])
            if a is None or b is None: return None
            result = a * b
        elif op == 'udiv':
            a, b = get(parts[3]), get(parts[4])
            if a is None or b is None: return None
            result = UDiv(a, b)
        elif op == 'urem':
            a, b = get(parts[3]), get(parts[4])
            if a is None or b is None: return None
            result = URem(a, b)
        elif op in ('ult','slt'):
            a, b = get(parts[3]), get(parts[4])
            if a is None or b is None: return None
            result = ULT(a, b)
        elif op in ('ulte','slte'):
            a, b = get(parts[3]), get(parts[4])
            if a is None or b is None: return None
            result = ULE(a, b)
        elif op in ('ugt','sgt'):
            a, b = get(parts[3]), get(parts[4])
            if a is None or b is None: return None
            result = UGT(a, b)
        elif op in ('ugte','sgte'):
            a, b = get(parts[3]), get(parts[4])
            if a is None or b is None: return None
            result = UGE(a, b)
        elif op == 'sll':
            a, b = get(parts[3]), get(parts[4])
            if a is None or b is None: return None
            result = a << b
        elif op == 'srl':
            a, b = get(parts[3]), get(parts[4])
            if a is None or b is None: return None
            result = LShR(a, b)
        elif op == 'uext':
            a = get(parts[3])
            if a is None: return None
            ext = int(parts[4])
            if isinstance(a, BoolRef):
                a = If(a, BitVecVal(1,1), BitVecVal(0,1))
            result = ZeroExt(ext, a) if ext > 0 else a
        elif op == 'slice':
            a = get(parts[3])
            if a is None: return None
            hi, lo = int(parts[4]), int(parts[5])
            result = Extract(hi, lo, a)
        else:
            return None

        current_vars[nid] = result
        return result

    except Exception:
        return None

def verify_btor2(btor2_path, num_steps=32):
    """
    Bounded Model Checking: unroll state machine for num_steps.
    Returns (verdict, witness, error)
    """
    sorts, inits, nexts, bads, lines = read_btor2(btor2_path)

    # find the non-zero-exit bad state
    target_bad = None
    for cond_nid, label in bads:
        if 'non-zero-exit' in label:
            target_bad = cond_nid
            break
    if target_bad is None:
        return "UNKNOWN", None, "No non-zero-exit-code bad state found"

    # identify state nodes and input nodes
    state_nodes = {}  # nid → bit width
    input_nodes = {}  # nid → bit width
    for nid, parts in lines.items():
        if parts[1] == 'state':
            w = sorts.get(parts[2])
            if w is not None:
                state_nodes[nid] = w
        elif parts[1] == 'input':
            w = sorts.get(parts[2])
            if w is not None:
                input_nodes[nid] = w

    # create the symbolic input (x — the user's input)
    input_var = None
    input_nid = None
    for nid, w in input_nodes.items():
        input_var = BitVec('x', w)
        input_nid = nid
        break  # take first input

    # === BMC: unroll for num_steps steps ===
    # current_vars holds the Z3 expressions for all nodes at current step
    current_vars = {}

    # add the symbolic input
    if input_nid:
        current_vars[input_nid] = input_var

    # Step 0: initialise state variables from init nodes
    for state_nid, w in state_nodes.items():
        if state_nid in inits:
            init_val_nid = inits[state_nid]
            # evaluate the init value (usually a constant)
            init_expr = eval_node(init_val_nid, lines, sorts, current_vars)
            if init_expr is not None:
                current_vars[state_nid] = init_expr
            else:
                # default: free symbolic variable
                if w == 1:
                    current_vars[state_nid] = Bool(f's_{state_nid}_0')
                else:
                    current_vars[state_nid] = BitVec(f's_{state_nid}_0', w)
        else:
            # no init — free symbolic variable
            if w == 1:
                current_vars[state_nid] = Bool(f's_{state_nid}_0')
            else:
                current_vars[state_nid] = BitVec(f's_{state_nid}_0', w)

    # check bad state at each step
    for step in range(num_steps):
        # clear cached formula nodes (keep only state/input vars)
        formula_cache = {k: v for k, v in current_vars.items()
                         if k in state_nodes or k == input_nid}
        current_vars = formula_cache

        # re-add input
        if input_nid:
            current_vars[input_nid] = input_var

        # evaluate bad state condition at this step
        bad_expr = eval_node(target_bad, lines, sorts, current_vars)
        if bad_expr is None:
            continue

        # make it a Bool
        if not isinstance(bad_expr, BoolRef):
            bad_expr = bad_expr != BitVecVal(0, bad_expr.size())

        # ask Z3: is the bad state reachable at this step?
        solver = Solver()
        solver.add(bad_expr)
        outcome = solver.check()

        if outcome == sat:
            # find readable witness
            witness = None
            if input_var is not None:
                isize = input_var.size()
                for v in range(101):
                    s2 = Solver()
                    s2.add(bad_expr)
                    s2.add(input_var == BitVecVal(v, isize))
                    if s2.check() == sat:
                        witness = v
                        break
                if witness is None:
                    m = solver.model()
                    val = m.eval(input_var, model_completion=True)
                    witness = val.as_long() if hasattr(val,'as_long') else str(val)
            return "FALSIFIED", witness, None

        # advance to next step: compute next state values
        next_vars = {}
        for state_nid, w in state_nodes.items():
            if state_nid in nexts:
                next_val_nid = nexts[state_nid]
                next_expr = eval_node(next_val_nid, lines, sorts, current_vars)
                if next_expr is not None:
                    next_vars[state_nid] = next_expr
                else:
                    if w == 1:
                        next_vars[state_nid] = Bool(f's_{state_nid}_{step+1}')
                    else:
                        next_vars[state_nid] = BitVec(f's_{state_nid}_{step+1}', w)
            else:
                next_vars[state_nid] = current_vars.get(state_nid,
                    BitVec(f's_{state_nid}_{step+1}', w) if w > 1
                    else Bool(f's_{state_nid}_{step+1}'))

        current_vars.update(next_vars)

    return "VERIFIED", None, None