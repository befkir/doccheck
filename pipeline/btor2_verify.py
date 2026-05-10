"""
btor2_verify.py — Parse Unicorn's BTOR2 output and verify with Z3.
This replaces manual Z3 models — true binary-level verification.
"""
import subprocess
import os
from z3 import *

SELFIE  = os.path.expanduser("~/selfie/selfie")
UNICORN = os.path.expanduser("~/unicorn/target/debug/unicorn")

def compile_and_run_unicorn(source_path, unroll=32):
    """Compile C* to binary and run Unicorn symbolic execution."""
    bin_path  = "/tmp/doccheck_patched.bin"
    btor2_path = "/tmp/doccheck_model.btor2"

    # compile
    r = subprocess.run([SELFIE, "-c", source_path, "-o", bin_path],
                       capture_output=True, text=True)
    if "syntax error" in r.stdout:
        return None, f"Compile error: {r.stdout[:200]}"

    # symbolic execution
    r = subprocess.run([UNICORN, "beator", bin_path,
                        "--unroll", str(unroll), "--out", btor2_path],
                       capture_output=True, text=True)
    return btor2_path, None

def parse_btor2_to_z3(btor2_path):
    """
    Parse BTOR2 file and build Z3 expressions for each node.
    Only handles bitvec sorts (sort 1 and sort 2) — not arrays.
    Returns (z3_nodes dict, input_var, error)
    """
    nodes = {}   # node_id → Z3 expression
    sorts = {}   # sort_id → bit width (None if array)
    input_var = None  # the symbolic input (read syscall)

    with open(btor2_path) as f:
        lines = f.readlines()

    for line in lines:
        line = line.strip()
        if not line or line.startswith(';'):
            continue
        parts = line.split()
        if not parts:
            continue

        nid = parts[0]
        op  = parts[1] if len(parts) > 1 else ""

        try:
            if op == 'sort':
                if parts[2] == 'bitvec':
                    sorts[nid] = int(parts[3])
                else:
                    sorts[nid] = None

            elif op in ('constd', 'const', 'consth'):
                width = sorts.get(parts[2])
                if width == 1:
                    val = int(parts[3]) if op == 'constd' else \
                          int(parts[3], 16) if op == 'consth' else \
                          int(parts[3], 2)
                    nodes[nid] = BoolVal(val != 0)
                elif width:
                    val = int(parts[3]) if op == 'constd' else \
                          int(parts[3], 16) if op == 'consth' else \
                          int(parts[3], 2)
                    nodes[nid] = BitVecVal(val, width)

            elif op == 'state':
                width = sorts.get(parts[2])
                if width == 1:
                    nodes[nid] = Bool(f'state_{nid}')
                elif width:
                    nodes[nid] = BitVec(f'state_{nid}', width)

            elif op == 'input':
                width = sorts.get(parts[2])
                if width:
                    var = BitVec('x', width)
                    nodes[nid] = var
                    if input_var is None:
                        input_var = var

            elif op == 'init':
                state_nid = parts[2]
                init_val  = parts[3]
                if state_nid in nodes and init_val in nodes:
                    nodes[state_nid] = nodes[init_val]

            elif op == 'next':
                state_nid = parts[2]
                next_val  = parts[3]
                if next_val in nodes:
                    nodes[state_nid] = nodes[next_val]

            elif op == 'not':
                if parts[3] in nodes:
                    a = nodes[parts[3]]
                    nodes[nid] = Not(a) if isinstance(a, BoolRef) else ~a

            elif op == 'and':
                if parts[3] in nodes and parts[4] in nodes:
                    a, b = nodes[parts[3]], nodes[parts[4]]
                    # normalise to Bool if either side is Bool
                    if isinstance(a, BoolRef) or isinstance(b, BoolRef):
                        if not isinstance(a, BoolRef):
                            a = a != BitVecVal(0, a.size())
                        if not isinstance(b, BoolRef):
                            b = b != BitVecVal(0, b.size())
                        nodes[nid] = And(a, b)
                    else:
                        nodes[nid] = a & b

            elif op == 'or':
                if parts[3] in nodes and parts[4] in nodes:
                    a, b = nodes[parts[3]], nodes[parts[4]]
                    if isinstance(a, BoolRef) or isinstance(b, BoolRef):
                        if not isinstance(a, BoolRef):
                            a = a != BitVecVal(0, a.size())
                        if not isinstance(b, BoolRef):
                            b = b != BitVecVal(0, b.size())
                        nodes[nid] = Or(a, b)
                    else:
                        nodes[nid] = a | b

            elif op == 'xor':
                if parts[3] in nodes and parts[4] in nodes:
                    a, b = nodes[parts[3]], nodes[parts[4]]
                    if isinstance(a, BoolRef) or isinstance(b, BoolRef):
                        nodes[nid] = Xor(a if isinstance(a, BoolRef) else a != BitVecVal(0, a.size()),
                                         b if isinstance(b, BoolRef) else b != BitVecVal(0, b.size()))
                    else:
                        nodes[nid] = a ^ b

            elif op == 'eq':
                if parts[3] in nodes and parts[4] in nodes:
                    nodes[nid] = (nodes[parts[3]] == nodes[parts[4]])

            elif op == 'neq':
                if parts[3] in nodes and parts[4] in nodes:
                    nodes[nid] = (nodes[parts[3]] != nodes[parts[4]])

            elif op == 'ite':
                if all(p in nodes for p in parts[3:6]):
                    cond = nodes[parts[3]]
                    th   = nodes[parts[4]]
                    el   = nodes[parts[5]]
                    if not isinstance(cond, BoolRef):
                        cond = cond != BitVecVal(0, cond.size())
                    nodes[nid] = If(cond, th, el)

            elif op == 'add':
                if parts[3] in nodes and parts[4] in nodes:
                    nodes[nid] = nodes[parts[3]] + nodes[parts[4]]

            elif op == 'sub':
                if parts[3] in nodes and parts[4] in nodes:
                    nodes[nid] = nodes[parts[3]] - nodes[parts[4]]

            elif op == 'mul':
                if parts[3] in nodes and parts[4] in nodes:
                    nodes[nid] = nodes[parts[3]] * nodes[parts[4]]

            elif op == 'udiv':
                if parts[3] in nodes and parts[4] in nodes:
                    nodes[nid] = UDiv(nodes[parts[3]], nodes[parts[4]])

            elif op == 'urem':
                if parts[3] in nodes and parts[4] in nodes:
                    nodes[nid] = URem(nodes[parts[3]], nodes[parts[4]])

            elif op in ('ult','slt'):
                if parts[3] in nodes and parts[4] in nodes:
                    nodes[nid] = ULT(nodes[parts[3]], nodes[parts[4]])

            elif op in ('ulte','slte'):
                if parts[3] in nodes and parts[4] in nodes:
                    nodes[nid] = ULE(nodes[parts[3]], nodes[parts[4]])

            elif op in ('ugt','sgt'):
                if parts[3] in nodes and parts[4] in nodes:
                    nodes[nid] = UGT(nodes[parts[3]], nodes[parts[4]])

            elif op in ('ugte','sgte'):
                if parts[3] in nodes and parts[4] in nodes:
                    nodes[nid] = UGE(nodes[parts[3]], nodes[parts[4]])

            elif op == 'sll':
                if parts[3] in nodes and parts[4] in nodes:
                    nodes[nid] = nodes[parts[3]] << nodes[parts[4]]

            elif op == 'srl':
                if parts[3] in nodes and parts[4] in nodes:
                    nodes[nid] = LShR(nodes[parts[3]], nodes[parts[4]])

            elif op == 'uext':
                if parts[3] in nodes:
                    src = nodes[parts[3]]
                    ext = int(parts[4])
                    if isinstance(src, BoolRef):
                        src = If(src, BitVecVal(1, 1), BitVecVal(0, 1))
                    nodes[nid] = ZeroExt(ext, src) if ext > 0 else src

            elif op == 'slice':
                if parts[3] in nodes:
                    hi = int(parts[4])
                    lo = int(parts[5])
                    nodes[nid] = Extract(hi, lo, nodes[parts[3]])

            elif op in ('bad','constraint','fair','output',
                        'read','write','array'):
                pass

        except Exception:
            pass

    return nodes, input_var, None


def verify_btor2(btor2_path):
    """
    Find non-zero-exit-code bad state and check with Z3.
    Returns (verdict, witness, error)
    """
    # find the bad state node
    target_cond_id = None
    with open(btor2_path) as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 3 and parts[1] == 'bad' and 'non-zero-exit' in line:
                target_cond_id = parts[2]
                break

    if target_cond_id is None:
        return "UNKNOWN", None, "Could not find non-zero-exit-code bad state in BTOR2"

    # parse the BTOR2
    nodes, input_var, err = parse_btor2_to_z3(btor2_path)
    if err:
        return "UNKNOWN", None, err

    if target_cond_id not in nodes:
        return "UNKNOWN", None, \
            f"Could not build Z3 expression for condition node {target_cond_id}"

    violation = nodes[target_cond_id]

    # make sure violation is a Bool
    if not isinstance(violation, BoolRef):
        violation = violation != BitVecVal(0, violation.size())

    # ask Z3: can this violation ever be true?
    solver = Solver()
    solver.add(violation)
    outcome = solver.check()

    if outcome == sat:
        # find a small readable witness
        witness = None
        if input_var is not None:
            input_size = input_var.size()
            for v in range(101):
                s2 = Solver()
                s2.add(violation)
                s2.add(input_var == BitVecVal(v, input_size))
                if s2.check() == sat:
                    witness = v
                    break
            if witness is None:
                m = solver.model()
                val = m.eval(input_var, model_completion=True)
                witness = val.as_long() if hasattr(val, 'as_long') else str(val)
        return "FALSIFIED", witness, None

    elif outcome == unsat:
        return "VERIFIED", None, None

    else:
        return "UNKNOWN", None, "Z3 returned unknown"