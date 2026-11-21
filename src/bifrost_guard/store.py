"""The Court's record: accepted rules, rounds, findings, verdicts (SQLite)."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS acceptance (
  id INTEGER PRIMARY KEY, at REAL, release TEXT, base_commit TEXT, fingerprint TEXT,
  detail TEXT, by_owner TEXT, by_client TEXT);
CREATE TABLE IF NOT EXISTS rounds (
  id INTEGER PRIMARY KEY, release TEXT, commit_sha TEXT, scope TEXT, since_commit TEXT,
  opened REAL, closes REAL, closed REAL, fingerprint TEXT);
CREATE TABLE IF NOT EXISTS findings (
  id INTEGER PRIMARY KEY, round_id INTEGER, at REAL, reviewer TEXT, data TEXT,
  stage TEXT, verdict TEXT, rules TEXT, plain TEXT, machine TEXT, judges TEXT,
  duplicate_of INTEGER, out_of_scope INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS decisions (
  id INTEGER PRIMARY KEY, finding_id INTEGER, at REAL, kind TEXT, verdict TEXT, reason TEXT);
"""


class Store:
    def __init__(self, path: str | Path):
        self.db = sqlite3.connect(str(path))
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    # acceptance (Rule 1)
    def accept(self, release, base_commit, fp, by_owner, by_client):
        self.db.execute("INSERT INTO acceptance(at,release,base_commit,fingerprint,detail,by_owner,by_client)"
                        " VALUES(?,?,?,?,?,?,?)", (time.time(), release, base_commit, fp["all"],
                                                   json.dumps(fp), by_owner, by_client))
        self.db.commit()

    def accepted(self, release):
        return self.db.execute("SELECT * FROM acceptance WHERE release=? ORDER BY id DESC LIMIT 1",
                               (release,)).fetchone()

    # rounds (Rules 3, 4)
    def open_round(self, release, commit, scope, since, hours, fp):
        now = time.time()
        cur = self.db.execute("INSERT INTO rounds(release,commit_sha,scope,since_commit,opened,closes,fingerprint)"
                              " VALUES(?,?,?,?,?,?,?)", (release, commit, scope, since, now, now + hours * 3600, fp))
        self.db.commit()
        return cur.lastrowid

    def round(self, rid):
        return self.db.execute("SELECT * FROM rounds WHERE id=?", (rid,)).fetchone()

    def rounds(self, release):
        return self.db.execute("SELECT * FROM rounds WHERE release=? ORDER BY id", (release,)).fetchall()

    def open_now(self, release=None):
        now = time.time()
        q = "SELECT * FROM rounds WHERE closed IS NULL AND closes>?" + (" AND release=?" if release else "")
        args = (now, release) if release else (now,)
        return self.db.execute(q + " ORDER BY id DESC LIMIT 1", args).fetchone()

    def close_round(self, rid):
        self.db.execute("UPDATE rounds SET closed=? WHERE id=?", (time.time(), rid))
        self.db.commit()

    # findings
    def add_finding(self, round_id, reviewer, data, stage, verdict=None, rules=None, plain=None,
                    out_of_scope=False):
        cur = self.db.execute(
            "INSERT INTO findings(round_id,at,reviewer,data,stage,verdict,rules,plain,out_of_scope)"
            " VALUES(?,?,?,?,?,?,?,?,?)", (round_id, time.time(), reviewer, json.dumps(data), stage, verdict,
                                          json.dumps(rules or []), plain, int(out_of_scope)))
        self.db.commit()
        return cur.lastrowid

    def update(self, fid, **kw):
        for k in ("rules", "machine", "judges"):
            if k in kw and not isinstance(kw[k], str):
                kw[k] = json.dumps(kw[k])
        sets = ", ".join(f"{k}=?" for k in kw)
        self.db.execute(f"UPDATE findings SET {sets} WHERE id=?", (*kw.values(), fid))
        self.db.commit()

    def finding(self, fid):
        return self.db.execute("SELECT * FROM findings WHERE id=?", (fid,)).fetchone()

    def findings(self, round_id=None, release=None):
        if round_id is not None:
            return self.db.execute("SELECT * FROM findings WHERE round_id=? ORDER BY id", (round_id,)).fetchall()
        return self.db.execute("SELECT f.* FROM findings f JOIN rounds r ON r.id=f.round_id WHERE r.release=?"
                               " ORDER BY f.id", (release,)).fetchall()

    # Arbiter decisions and appeals (Rules 2, 14, 17)
    def decide(self, fid, kind, verdict, reason):
        self.db.execute("INSERT INTO decisions(finding_id,at,kind,verdict,reason) VALUES(?,?,?,?,?)",
                        (fid, time.time(), kind, verdict, reason))
        self.db.commit()

    def decisions(self, fid):
        return self.db.execute("SELECT * FROM decisions WHERE finding_id=? ORDER BY id", (fid,)).fetchall()
