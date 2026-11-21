"""What a fixes-only round may review (Law Rule 4): the changed lines and the functions that hold them."""
from __future__ import annotations

import ast
import re
import subprocess
from pathlib import Path

HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def changed_lines(repo: Path, since: str, commit: str) -> dict[str, set[int]]:
    out = subprocess.run(["git", "-C", str(repo), "diff", "-U0", since, commit],
                         check=True, capture_output=True, text=True).stdout
    files: dict[str, set[int]] = {}
    cur = None
    for line in out.splitlines():
        if line.startswith("+++ "):
            cur = None if line[4:] == "/dev/null" else line[6:]
            if cur is not None:
                files.setdefault(cur, set())
        elif cur is not None and (m := HUNK.match(line)):
            start, count = int(m.group(1)), int(m.group(2) or 1)
            # a pure deletion (count 0) still touches the line where the deletion happened
            files[cur].update(range(start, start + max(count, 1)))
    return files


def _functions(src: str) -> list[tuple[int, int]]:
    spans = []
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            spans.append((node.lineno, node.end_lineno or node.lineno))
    return spans


def scope(repo: Path, since: str, commit: str) -> dict[str, list[tuple[int, int]]]:
    """For each changed file, the line ranges in scope: whole enclosing functions where possible."""
    result: dict[str, list[tuple[int, int]]] = {}
    for rel, lines in changed_lines(repo, since, commit).items():
        ranges = [(n, n) for n in sorted(lines)]
        if rel.endswith(".py"):
            try:
                src = subprocess.run(["git", "-C", str(repo), "show", f"{commit}:{rel}"],
                                     check=True, capture_output=True, text=True).stdout
                funcs = _functions(src)
                for n in lines:
                    inner = [f for f in funcs if f[0] <= n <= f[1]]
                    if inner:  # the smallest function holding the line
                        ranges.append(min(inner, key=lambda f: f[1] - f[0]))
            except (SyntaxError, subprocess.CalledProcessError):
                pass
        result[rel] = sorted(set(ranges))
    return result


def in_scope(sc: dict[str, list[tuple[int, int]]], file: str, line: int) -> bool:
    file = file.lstrip("./")
    return any(a <= line <= b for a, b in sc.get(file, []))
