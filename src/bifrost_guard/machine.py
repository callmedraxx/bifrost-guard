"""The machine check (Law Rule 13).

1. The test may replace only the outside world (checked by reading the test's patches).
2. The Court runs the test itself on the reviewed commit, in a fresh copy, with no network.
3. It must fail every run, and the failing check must be the harm check: an assertion whose
   message starts with "HARM:".
"""
from __future__ import annotations

import ast
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from .profile import Profile

PATCHERS = {"setattr", "patch", "object", "dict", "setitem", "delattr"}


@dataclass
class StandInCheck:
    ok: bool
    replaced: list[str] = field(default_factory=list)    # targets the test replaces
    forbidden: list[str] = field(default_factory=list)   # reviewed code it replaces
    unclear: list[str] = field(default_factory=list)     # targets the machine could not resolve


def _dotted(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return f"{base}.{node.attr}" if base else None
    return None


def check_stand_ins(test_src: str, profile: Profile) -> StandInCheck:
    tree = ast.parse(test_src)
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                aliases[a.asname or a.name.split(".")[0]] = a.name if a.asname else a.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.module:
            for a in node.names:
                aliases[a.asname or a.name] = f"{node.module}.{a.name}"

    def resolve(expr: ast.AST) -> str | None:
        if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
            return expr.value
        d = _dotted(expr)
        if not d:
            return None
        head, _, rest = d.partition(".")
        if head in aliases:
            return aliases[head] + (f".{rest}" if rest else "")
        return None

    res = StandInCheck(ok=True)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fname = _dotted(node.func) or ""
        last = fname.rsplit(".", 1)[-1]
        if last not in PATCHERS or not node.args:
            continue
        if last in {"setattr", "object", "delattr"} and len(node.args) >= 2 and \
                isinstance(node.args[1], ast.Constant) and not (
                    isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
            base = resolve(node.args[0])
            target = f"{base}.{node.args[1].value}" if base else None
        else:
            target = resolve(node.args[0])
        label = target or ast.unparse(node)[:120]
        if target is None:
            res.unclear.append(label)
            continue
        res.replaced.append(target)
        reviewed = any(target == p or target.startswith(p + ".") for p in profile.reviewed_packages)
        allowed = any(target == p or target.startswith(p + ".") for p in profile.allowed_stand_ins)
        if reviewed and not allowed:
            res.forbidden.append(target)
    res.ok = not res.forbidden
    return res


@dataclass
class RunResult:
    outcome: str        # "harm" (failed on the HARM check), "passed", "other-failure", "error"
    message: str = ""


@dataclass
class MachineResult:
    passed: bool        # True = the finding passes the machine check
    reason: str
    stand_ins: StandInCheck | None = None
    runs: list[RunResult] = field(default_factory=list)


def _one_run(profile: Profile, workdir: Path, test_rel: str, n: int) -> RunResult:
    xml = workdir / f".guard-run-{n}.xml"
    cmd = profile.test_command.format(python=profile.python, test=test_rel) + f" --junitxml={xml}"
    argv = ["bash", "-c", cmd]
    if profile.no_network and shutil.which("unshare"):
        argv = ["unshare", "-n"] + argv
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1", "HOME": str(workdir)}
    try:
        p = subprocess.run(argv, cwd=workdir, capture_output=True, text=True,
                           timeout=profile.run_timeout_s, env=env)
    except subprocess.TimeoutExpired:
        return RunResult("error", "the test ran too long")
    if not xml.exists():
        return RunResult("error", (p.stdout + p.stderr)[-800:])
    root = ET.parse(xml).getroot()
    cases = root.iter("testcase")
    fails, errors, ran = [], [], 0
    for c in cases:
        ran += 1
        for f in c.findall("failure"):
            fails.append((f.get("type", ""), f.get("message", "") or (f.text or "")))
        for e in c.findall("error"):
            errors.append(e.get("message", ""))
    if ran == 0:
        return RunResult("error", "no test ran")
    if errors:
        return RunResult("error", errors[0][:400])
    if not fails:
        return RunResult("passed")
    harm = [m for t, m in fails
            if ("AssertionError" in t or m.lstrip().startswith("AssertionError")) and "HARM:" in m]
    if harm and len(harm) == len(fails):
        return RunResult("harm", harm[0][:400])
    return RunResult("other-failure", fails[0][1][:400])


def run_machine_check(profile: Profile, commit: str, test_src: str) -> MachineResult:
    try:
        si = check_stand_ins(test_src, profile)
    except SyntaxError as e:
        return MachineResult(False, f"the test is not valid Python: {e}")
    if not si.ok:
        return MachineResult(False, "the test replaces code that is being reviewed: " + ", ".join(si.forbidden),
                             stand_ins=si)
    with tempfile.TemporaryDirectory(prefix="guard-") as tmp:
        work = Path(tmp)
        arch = subprocess.run(["git", "-C", str(profile.repo), "archive", commit],
                              check=True, capture_output=True).stdout
        subprocess.run(["tar", "-x", "-C", str(work)], input=arch, check=True)
        test_rel = "guard_finding_test.py"
        tests_dir = work / "tests"
        if tests_dir.is_dir():
            test_rel = "tests/guard_finding_test.py"
        (work / test_rel).write_text(test_src)
        runs = [_one_run(profile, work, test_rel, i) for i in range(profile.runs)]
    bad = [r for r in runs if r.outcome != "harm"]
    if not bad:
        return MachineResult(True, f"the test failed on the harm check in all {len(runs)} runs",
                             stand_ins=si, runs=runs)
    first = bad[0]
    why = {"passed": "the test passed in at least one run, so the harm was not shown every time",
           "other-failure": "the test failed, but not on a check marked HARM:",
           "error": "the test could not run properly"}[first.outcome]
    return MachineResult(False, why + (f" ({first.message})" if first.message else ""), stand_ins=si, runs=runs)
