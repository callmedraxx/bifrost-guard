"""`bifrost-guard` command line, for the Operator and the background worker."""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .court import Court
from .profile import load_profile
from .report import release_status, round_report
from .store import Store


def _court(a) -> Court:
    prof = load_profile(a.profile)
    db = a.db or str(Path(prof.source).with_name("guard.db"))
    return Court(prof, Store(db), a.release or prof.version)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="bifrost-guard")
    ap.add_argument("--profile", required=True)
    ap.add_argument("--db")
    ap.add_argument("--release")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("accept", help="both sides accept the rules at this commit (Rule 1)")
    s.add_argument("--commit", default="HEAD"); s.add_argument("--owner", required=True)
    s.add_argument("--client", required=True)
    s = sub.add_parser("open", help="open a round (Rule 3)")
    s.add_argument("--commit", default="HEAD"); s.add_argument("--hours", type=float, default=24)
    sub.add_parser("close", help="close the open round")
    s = sub.add_parser("submit", help="hand in a finding from a JSON file")
    s.add_argument("file"); s.add_argument("--reviewer", default="cli")
    s = sub.add_parser("work", help="run the machine check and judges on waiting findings")
    s.add_argument("--loop", action="store_true"); s.add_argument("--every", type=int, default=60)
    s = sub.add_parser("decide", help="the Arbiter decides a finding (Rules 2, 14)")
    s.add_argument("id", type=int); s.add_argument("verdict"); s.add_argument("--reason", required=True)
    s = sub.add_parser("appeal", help="appeal a verdict once, with new evidence (Rule 17)")
    s.add_argument("id", type=int); s.add_argument("--side", required=True, choices=["owner", "client"])
    s.add_argument("--evidence", required=True)
    s = sub.add_parser("report"); s.add_argument("--round", type=int)
    sub.add_parser("status")
    a = ap.parse_args(argv)
    c = _court(a)
    try:
        if a.cmd == "accept":
            print(json.dumps(c.accept(a.commit, a.owner, a.client)))
        elif a.cmd == "open":
            print(json.dumps(c.open_round(a.commit, a.hours)))
        elif a.cmd == "close":
            print(f"round {c.close_round()} closed")
        elif a.cmd == "submit":
            print(json.dumps(c.submit(a.reviewer, json.loads(Path(a.file).read_text()))))
        elif a.cmd == "work":
            while True:
                rows = c.s.db.execute("SELECT id FROM findings WHERE stage IN ('machine','judges')"
                                      " ORDER BY id").fetchall()
                for row in rows:
                    print(json.dumps(c.process(row["id"])), flush=True)
                if not a.loop:
                    break
                time.sleep(a.every)
        elif a.cmd == "decide":
            print(json.dumps(c.decide(a.id, a.verdict, a.reason)))
        elif a.cmd == "appeal":
            print(json.dumps(c.appeal(a.id, a.side, a.evidence)))
        elif a.cmd == "report":
            r = c.s.round(a.round) if a.round else (c.s.open_now(c.release) or (c.s.rounds(c.release) or [None])[-1])
            if not r:
                print("No round has been held yet.")
            else:
                print(round_report(c.s, r["id"]))
                print()
                print(release_status(c.s, c.release))
        elif a.cmd == "status":
            print(release_status(c.s, c.release))
    except RuntimeError as e:
        print(f"refused: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
