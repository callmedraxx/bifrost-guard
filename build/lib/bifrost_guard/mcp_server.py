"""MCP server: the door every agent reviews through (the executive).

The first thing a connecting agent receives is INSTRUCTIONS: the Law in short. Findings count
only when handed in through `guard_submit_finding` (Law Rule 2).

Settings come from the environment:
  GUARD_PROFILE  path to the project's profile.yaml
  GUARD_DB       path to the Court's database (default: guard.db next to the profile)
  GUARD_RELEASE  the release name (default: the profile's version)
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .court import Court
from .profile import LAW_PATH, load_profile
from .report import release_status, round_report
from .store import Store

try:  # mcp 2.x
    from mcp.server.mcpserver import MCPServer as _Server
except ImportError:  # mcp 1.x
    from mcp.server.fastmcp import FastMCP as _Server

INSTRUCTIONS = """This project is reviewed under the bifrost-guard Law. Read it with `guard_rules`.

In short:
1. Only real harm counts. The project's harms are listed by `guard_rules`. Everything else is a
   Note: messages, logs, wording, documents, display, style. Notes never block anything.
2. A finding counts only if you hand it in with `guard_submit_finding`, with a test the Court runs
   itself. The test must end with an assertion whose message starts with "HARM:", must fail every
   time, and may replace only the outside world, never the project's own code.
3. Only the Court's report counts (`guard_report`). When you tell your user what you found, give
   the Court's result. Its first line is "Material findings: N".
4. Do not fix, change or decide anything that is not Material. It goes to the Operator.
5. Write for someone who is not a developer: short sentences, everyday words."""


INSTRUCTIONS_LAW_ONLY = """This project is reviewed under the bifrost-guard Law. Read it with `guard_rules` before
you review anything.

In short:
1. Only real harm counts. The project's harms are listed by `guard_rules`. Everything else is a
   Note: messages, logs, wording, documents, display, style. Notes never block anything.
2. You run the Court on your own side, with the Law and the Profile from `guard_rules`
   (`guard_rules` explains how). This server only gives information; it takes no findings.
3. A finding counts only if your Court ran its test itself, on the exact commit: the test ends
   with an assertion whose message starts with "HARM:", fails every time, and replaces only the
   outside world, never the project's own code.
4. Report the Court's result. Its first line is "Material findings: N". Everything that is not
   Material goes on the Operator's list. Do not ask for anything on that list to be fixed.
5. Write for someone who is not a developer: short sentences, everyday words."""

HOW_TO_RUN = """=== HOW TO RUN THE COURT ON YOUR SIDE ===
1. pip install git+https://github.com/callmedraxx/bifrost-guard
2. Save the Profile above as profile.yaml. Set `repo:` to your checkout of the project and
   `machine_check.python:` to a Python that has the project's test dependencies.
3. Choose your judges under `judges:` (any two; `command` judges can be any model).
4. bifrost-guard --profile profile.yaml accept --commit <commit> --owner <operator> --client <you>
   bifrost-guard --profile profile.yaml open --commit <commit> --hours 48
   bifrost-guard --profile profile.yaml submit finding.json      (one JSON file per finding)
   bifrost-guard --profile profile.yaml work                      (machine check, then judges)
   bifrost-guard --profile profile.yaml report
5. The report's first line is "Material findings: N". Send the report to the Operator. When your
   two judges disagree, the Operator decides (Rule 14).
A finding JSON has: title, file, line, steps, happens, should, harm (a code below, or empty for a
Note), test (the full pytest file)."""


def register_law_only(srv, profile_path: str, annotations=None):
    """Give agents the Law and the Profile, read-only. No findings are taken and no Court runs
    here: each reviewer runs the Court on its own side."""
    kw = {"annotations": annotations} if annotations is not None else {}

    @srv.tool(**kw)
    def guard_rules() -> str:
        """The review Law, this project's Profile (its harms and conditions), and how to run the
        Court on your side. Read this before reviewing anything."""
        prof = load_profile(profile_path)
        harms = "\n".join(f"- {h.code}: {h.title}. {h.meaning}" for h in prof.harms)
        return (f"{LAW_PATH.read_text()}\n\n=== PROFILE: {prof.name} {prof.version} ===\n"
                f"{prof.source.read_text()}\n\n=== HARMS ===\n{harms}\n\n{HOW_TO_RUN}")


def _court():
    prof = load_profile(os.environ["GUARD_PROFILE"])
    db = os.environ.get("GUARD_DB") or str(Path(prof.source).with_name("guard.db"))
    release = os.environ.get("GUARD_RELEASE") or prof.version
    return Court(prof, Store(db), release)


def build_server():
    srv = _Server("bifrost-guard", instructions=INSTRUCTIONS)
    register(srv)
    return srv


def register(srv, annotations=None):
    # `annotations` (e.g. read-only hints) apply to the three reading tools only.
    """Add the guard's tools to an existing MCP server (mcp 1.x FastMCP or 2.x MCPServer).
    Put INSTRUCTIONS at the top of that server's own instructions, so agents read the Law first."""
    kw = {"annotations": annotations} if annotations is not None else {}

    @srv.tool(**kw)
    def guard_rules() -> str:
        """The Law, the project's Profile (its harms and conditions), and how to hand in a finding."""
        c = _court()
        harms = "\n".join(f"- {h.code}: {h.title}. {h.meaning}" for h in c.p.harms)
        return (f"{LAW_PATH.read_text()}\n\n=== PROFILE: {c.p.name} {c.p.version} ===\n"
                f"{c.p.source.read_text()}\n\n=== HARMS ===\n{harms}")

    @srv.tool(**kw)
    def guard_round() -> str:
        """The round that is open now: which commit, full or fixes-only, and when it closes."""
        c = _court()
        r = c.s.open_now(c.release)
        if not r:
            return ("No round is open. A finding handed in now waits for the next round (Rules 3, 5).\n"
                    + release_status(c.s, c.release))
        info = {"round": r["id"], "commit": r["commit_sha"], "scope": r["scope"],
                "since_commit": r["since_commit"], "closes_utc": r["closes"]}
        return json.dumps(info)

    @srv.tool()  # writes a finding into the Court's record, so never marked read-only
    def guard_submit_finding(reviewer: str, title: str, file: str, line: int, steps: str, happens: str,
                             should: str, harm: str, test: str) -> str:
        """Hand in one finding. `harm` is a harm code from the Profile (leave empty for a Note).
        `test` is the full source of a pytest file that fails on an assertion whose message
        starts with "HARM:"."""
        c = _court()
        res = c.submit(reviewer, dict(title=title, file=file, line=line, steps=steps, happens=happens,
                                      should=should, harm=harm, test=test))
        return json.dumps(res)

    @srv.tool(**kw)
    def guard_report(round_id: int | None = None) -> str:
        """The Court's report for a round (the open one, or the latest)."""
        c = _court()
        r = c.s.open_now(c.release) if round_id is None else c.s.round(round_id)
        if r is None:
            rs = c.s.rounds(c.release)
            if not rs:
                return "No round has been held yet."
            r = rs[-1]
        return round_report(c.s, r["id"]) + "\n\n" + release_status(c.s, c.release)


def main():
    import argparse
    ap = argparse.ArgumentParser(prog="bifrost-guard-mcp")
    ap.add_argument("--transport", default="stdio", choices=["stdio", "sse", "streamable-http"])
    a = ap.parse_args()
    build_server().run(a.transport)


if __name__ == "__main__":
    main()
