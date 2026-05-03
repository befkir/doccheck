from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class VerificationError(Exception):
    pass


@dataclass(frozen=True)
class VerifyResult:
    status: str
    detail: str
    counterexample: dict[str, Any] | None = None
    smt_path: str | None = None
    binary_path: str | None = None


SELFIE    = "/home/tinsae/selfie/selfie"
BEATOR    = "/home/tinsae/selfie/tools/beator"
BITME     = "/home/tinsae/selfie/tools/bitme.py"
BITME_DIR = "/home/tinsae/selfie/tools"


def run_cmd(cmd, timeout=120, cwd=None):
    return subprocess.run(cmd, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=timeout, check=False, cwd=cwd)


def compile_cstar(source_path, binary_path):
    cmd = [SELFIE, "-c", str(source_path), "-o", str(binary_path)]
    proc = run_cmd(cmd, timeout=60)
    out = (proc.stdout or "") + (proc.stderr or "")
    ok = proc.returncode == 0 and "syntax error" not in out.lower()
    return ok, out


def generate_btor2(source_path, btor2_path):
    cwd = str(source_path.parent)
    cmd = [BEATOR, "-c", str(source_path), "-", "1", "--check-block-access"]
    proc = run_cmd(cmd, timeout=180, cwd=cwd)
    out = (proc.stdout or "") + (proc.stderr or "")
    generated = source_path.parent / (source_path.stem + "-beaten.btor2")
    if generated.exists():
        generated.rename(btor2_path)
        return True, out
    return False, out


def run_bitme(btor2_path):
    cmd = ["python3", BITME, str(btor2_path), "--use-Z3", "-kmax", "100"]
    proc = run_cmd(cmd, timeout=600, cwd=BITME_DIR)
    out = (proc.stdout or "") + (proc.stderr or "")
    text = out.lower()
    if "unsat" in text or "reached kmax" in text:
        return "UNSAT", out, None
    if "sat" in text or "bad-exit-code" in text:
        return "SAT", out, None
    return "UNKNOWN", out, None


def verify_patched(source_path: Path, result_dir: Path) -> VerifyResult:
    result_dir.mkdir(parents=True, exist_ok=True)
    binary_path = result_dir / (source_path.stem + ".m")
    btor2_path  = result_dir / (source_path.stem + ".btor2")

    ok, compile_log = compile_cstar(source_path, binary_path)
    (result_dir / "compile.log").write_text(compile_log)
    if not ok:
        return VerifyResult(status="COMPILE_ERROR", detail=compile_log,
            binary_path=str(binary_path))

    ok, beator_log = generate_btor2(source_path, btor2_path)
    (result_dir / "rotor.log").write_text(beator_log)
    if not ok:
        return VerifyResult(status="ROTOR_ERROR", detail=beator_log,
            binary_path=str(binary_path))

    status, solver_log, model = run_bitme(btor2_path)
    (result_dir / "solver.log").write_text(solver_log)
    return VerifyResult(status=status, detail=solver_log,
        counterexample=model, binary_path=str(binary_path),
        smt_path=str(btor2_path))
