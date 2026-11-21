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


INSTRUCTIONS_LAW_ONLY = """This project is reviewed under the bifrost-guard Law. Call `guard_rules` and read it
before you review anything.

In short:
1. Only real harm counts. The project's harms are listed by `guard_rules`. Everything else is a
   Note: messages, logs, wording, documents, display, style. Notes never block anything.
2. A Material finding must come with a test: a pytest file that fails on the exact commit, on an
   assertion whose message starts with "HARM:", every time, and that replaces only the outside
   world, never the project's own code. Without a test it is a Question, not a finding.
3. Write your result with the report template from `guard_rules`. Its first line is
   "Material findings: N". Send it to the Operator. This server only gives information; it takes
   no reports.
4. Everything that is not Material goes on the Operator's list. Do not ask for anything on that
   list to be fixed. The Operator checks each Material test and decides.
5. Write for someone who is not a developer: short sentences, everyday words."""

REPORT_TEMPLATE = """=== HOW TO REPORT ===
Review only the commit you name. Follow the Law. Then send the Operator one report in this shape:

Material findings: N
Commit: <full commit id>

## Real problems
For each Material finding (one per cause, Rule 12):
- Title
- What happens: one or two plain sentences, the real-world event
- What it means: how bad it is, in plain words
- Harm: the harm code from the Profile (H1 to H5)
- Where: file and line
- Steps: the starting state, the inputs, the order of events
- Test: the full pytest file. It must fail on its "HARM:" assertion every time on that commit.

## Operator's list (nothing here blocks anything)
For each Note, Question or Known item: one or two plain sentences on what happens, then
"This cannot cause a wrong trade, a wrong money record or lost money" (or what it can cause),
then "What you need to do: nothing" (or one plain sentence).

## Technical detail
Anything else: code, logs, reasoning.

The Operator runs each Material test on the same commit. A test that does not fail on its
"HARM:" assertion every time is "Not valid" (Rule 13), and nothing is changed for it."""


def register_law_only(srv, profile_path: str, annotations=None):
    """Give agents the Law, the Profile and the report template, read-only. No findings are
    taken here: reviewers send their report to the Operator, who checks each Material test."""
    kw = {"annotations": annotations} if annotations is not None else {}

    @srv.tool(**kw)
    def guard_rules() -> str:
        """The review Law, this project's Profile (its harms and conditions), and the report
        template. Read this before reviewing anything."""
        prof = load_profile(profile_path)
        harms = "\n".join(f"- {h.code}: {h.title}. {h.meaning}" for h in prof.harms)
        return (f"{LAW_PATH.read_text()}\n\n=== PROFILE: {prof.name} {prof.version} ===\n"
                f"{prof.source.read_text()}\n\n=== HARMS ===\n{harms}\n\n{REPORT_TEMPLATE}")


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
