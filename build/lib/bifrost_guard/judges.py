"""The judges (Law Rule 14). Each judge tries to disprove a finding and answers in JSON.

Judges are pluggable, set in the Profile under `judges:`:

  - kind: claude-code      # runs the local Claude Code CLI (no API key needed)
    model: claude-opus-5-5
  - kind: command          # any program: reads the prompt on stdin, prints the JSON answer
    run: "my-judge --flag"

A judge only reads; it never changes code (Law Rule 21).
"""
from __future__ import annotations

import json
import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path

VERDICTS = ["Material", "Note", "Known", "Duplicate", "Not valid"]

ANSWER_SHAPE = """Answer with ONE JSON object and nothing after it:
{"verdict": "Material" | "Note" | "Known" | "Duplicate" | "Not valid",
 "rules": [rule numbers you used],
 "harm": "harm code from the Profile, or null",
 "duplicate_of": finding number or null,
 "what_happens": "one or two plain sentences: the real-world event",
 "what_it_means": "one or two plain sentences: how bad it is, or 'This cannot ...'",
 "what_to_do": "one plain sentence for the Operator, or 'Nothing.'",
 "reasons": "your reasons, with evidence; technical detail is fine here"}
The three plain fields must use short sentences and words a 12-year-old knows (Rule 19)."""


@dataclass
class JudgeAnswer:
    judge: str
    verdict: str | None
    data: dict
    raw: str
    error: str | None = None


def build_prompt(law: str, profile_text: str, finding: dict, machine_reason: str, earlier: list[dict],
                 code_dir: Path) -> str:
    earlier_txt = "\n".join(f"- #{e['id']}: {e['title']} ({e.get('file','?')}:{e.get('line','?')})"
                            for e in earlier) or "- none"
    return f"""You are a judge under the bifrost-guard Law. Your job is to try hard to DISPROVE this
finding. Read only; do not change any file. The reviewed code is at {code_dir}.

=== THE LAW ===
{law}

=== THE PROFILE ===
{profile_text}

=== THE FINDING ===
{json.dumps(finding, indent=2)}

=== MACHINE CHECK (Rule 13) ===
Passed: {machine_reason}

=== EARLIER MATERIAL FINDINGS ON THIS RELEASE (for Rule 12) ===
{earlier_txt}

Decide the verdict under the Law. Check: is the scenario reachable in the real code under the
Profile's Operating Conditions (Rule 10)? Is it one of the Profile's harms (Rules 6-8)? Is it on
the accepted known-problems list (Rule 11)? Would the smallest fix of an earlier finding cure it
(Rule 12)? Is it the owner's choice (Rule 16)?

{ANSWER_SHAPE}"""


def _parse(text: str) -> dict | None:
    for m in reversed(list(re.finditer(r"\{", text))):
        try:
            obj, _ = json.JSONDecoder().raw_decode(text[m.start():])
            if isinstance(obj, dict) and "verdict" in obj:
                return obj
        except json.JSONDecodeError:
            continue
    return None


def run_judge(spec: dict, prompt: str, code_dir: Path, timeout: int = 1800) -> JudgeAnswer:
    name = spec.get("name") or spec.get("model") or spec.get("run") or spec["kind"]
    if spec["kind"] == "claude-code":
        argv = ["claude", "-p", "--model", spec.get("model", "claude-opus-5-5"), "--output-format", "json",
                "--allowedTools", "Read,Grep,Glob", "--add-dir", str(code_dir)]
    elif spec["kind"] == "command":
        argv = shlex.split(spec["run"])
    else:
        return JudgeAnswer(name, None, {}, "", f"unknown judge kind {spec['kind']}")
    try:
        p = subprocess.run(argv, input=prompt, capture_output=True, text=True, timeout=timeout, cwd=code_dir)
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return JudgeAnswer(name, None, {}, "", str(e))
    out = p.stdout
    if spec["kind"] == "claude-code":
        try:
            out = json.loads(out).get("result", out)
        except json.JSONDecodeError:
            pass
    data = _parse(out)
    if not data or data.get("verdict") not in VERDICTS:
        return JudgeAnswer(name, None, data or {}, out[-2000:], "the judge did not give a valid verdict")
    return JudgeAnswer(name, data["verdict"], data, out[-2000:])
