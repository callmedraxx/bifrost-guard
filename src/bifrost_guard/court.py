"""The Court: hands findings through intake, the machine check and the judges (Law Parts 3-6)."""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from . import judges as J
from .machine import run_machine_check
from .plain import is_plain
from .profile import LAW_PATH, Profile, fingerprints, resolve_commit
from .scope import in_scope, scope
from .store import Store

REQUIRED = ["title", "file", "line", "steps", "happens", "should", "harm", "test"]

PLAIN = {
    "question": ("This report has no test the Court can run, or it is missing a part the Law asks for, so it "
                 "was not judged.", "It is only a question. It cannot block anything.",
                 "Nothing, unless you want to answer it."),
    "note": ("The reviewer says this is not one of the harms the project cares about.",
             "This cannot cause a wrong trade, a wrong money record or lost money.", "Nothing."),
    "out_of_scope": ("This is about code that the current round is not checking.",
                     "It is not a harm, so it cannot block anything.", "Nothing."),
    "machine_fail": ("The Court ran the reviewer's test itself, and it did not show the harm every time.",
                     "The harm was not proven, so it does not count.", "Nothing."),
}


class Court:
    def __init__(self, profile: Profile, store: Store, release: str):
        self.p, self.s, self.release = profile, store, release

    # Rule 1
    def accept(self, ref: str, by_owner: str, by_client: str) -> dict:
        commit = resolve_commit(self.p.repo, ref)
        fp = fingerprints(self.p, commit)
        self.s.accept(self.release, commit, fp, by_owner, by_client)
        return {"release": self.release, "commit": commit, "fingerprint": fp["all"]}

    def _accepted(self):
        a = self.s.accepted(self.release)
        if not a:
            raise RuntimeError("the rules have not been accepted for this release yet (Rule 1)")
        return a

    # Rules 3, 4
    def open_round(self, ref: str, hours: float) -> dict:
        a = self._accepted()
        commit = resolve_commit(self.p.repo, ref)
        fp = fingerprints(self.p, commit)
        if fp["all"] != a["fingerprint"]:
            changed = [k for k, v in fp.items() if k != "all" and json.loads(a["detail"]).get(k) != v]
            raise RuntimeError("the rules or pinned files changed since they were accepted: "
                               + ", ".join(changed) + " (Rule 1: accept the new version first)")
        if self.s.open_now(self.release):
            raise RuntimeError("a round is already open")
        prior = self.s.rounds(self.release)
        full_done = any(r["scope"] == "full" for r in prior)
        scope_kind = "fixes" if full_done else "full"
        since = prior[-1]["commit_sha"] if full_done else None
        rid = self.s.open_round(self.release, commit, scope_kind, since, hours, fp["all"])
        for f in self.s.db.execute("SELECT id FROM findings WHERE round_id IS NULL").fetchall():
            self.s.update(f["id"], round_id=rid)
        return {"round": rid, "commit": commit, "scope": scope_kind, "since": since}

    def close_round(self) -> int:
        r = self.s.open_now(self.release)
        if not r:
            raise RuntimeError("no round is open")
        self.s.close_round(r["id"])
        return r["id"]

    # intake (Rules 3, 5, 7, 9, 15)
    def submit(self, reviewer: str, data: dict) -> dict:
        r = self.s.open_now(self.release)
        missing = [k for k in REQUIRED if not str(data.get(k) or "").strip()]
        harm_code = str(data.get("harm") or "").strip()
        claims_harm = bool(harm_code) and self.p.harm(harm_code) is not None
        rid = r["id"] if r else None
        out_of_scope = False
        if r and r["scope"] == "fixes" and data.get("file") and str(data.get("line", "")).isdigit():
            sc = scope(self.p.repo, r["since_commit"], r["commit_sha"])
            out_of_scope = not in_scope(sc, data["file"], int(data["line"]))
        if harm_code and not claims_harm:
            fid = self.s.add_finding(rid, reviewer, data, "done", "Note", [6, 7], _plain(PLAIN["note"]))
            return {"id": fid, "verdict": "Note", "why": f"'{harm_code}' is not a harm in the Profile (Rule 6)"}
        if not claims_harm:
            if out_of_scope:
                fid = self.s.add_finding(rid, reviewer, data, "done", "Not valid", [4, 15],
                                         _plain(PLAIN["out_of_scope"]), out_of_scope=True)
                return {"id": fid, "verdict": "Not valid", "why": "a Note outside the round's scope (Rule 4)"}
            fid = self.s.add_finding(rid, reviewer, data, "done", "Note", [7], _plain(PLAIN["note"]))
            return {"id": fid, "verdict": "Note", "why": "no harm from the Profile is claimed (Rule 7)"}
        if missing:
            fid = self.s.add_finding(rid, reviewer, data, "done", "Question", [9], _plain(PLAIN["question"]))
            return {"id": fid, "verdict": "Question", "why": "missing: " + ", ".join(missing) + " (Rule 9)"}
        fid = self.s.add_finding(rid, reviewer, data, "machine" if r else "waiting-for-round",
                                 out_of_scope=out_of_scope)
        note = "accepted; the Court will run the test (Rule 13)" if r else \
            "no round is open; it will be checked in the next round (Rules 3, 5)"
        if out_of_scope:
            note += ". It is outside this round's scope, but a harm is always heard (Rule 5)"
        return {"id": fid, "verdict": None, "why": note}

    # Rule 13
    def machine(self, fid: int) -> dict:
        f = self.s.finding(fid)
        data = json.loads(f["data"])
        r = self.s.round(f["round_id"])
        res = run_machine_check(self.p, r["commit_sha"], data["test"])
        info = {"passed": res.passed, "reason": res.reason,
                "runs": [x.outcome for x in res.runs],
                "stand_ins": res.stand_ins.__dict__ if res.stand_ins else None}
        if res.passed:
            self.s.update(fid, machine=info, stage="judges")
        else:
            self.s.update(fid, machine=info, stage="done", verdict="Not valid", rules=[13],
                          plain=_plain((PLAIN["machine_fail"][0] + " " + res.reason[:1].upper() + res.reason[1:] + ".",
                                        PLAIN["machine_fail"][1], PLAIN["machine_fail"][2])))
        return info

    # Rules 12, 14, 19
    def judge(self, fid: int) -> dict:
        f = self.s.finding(fid)
        data = json.loads(f["data"])
        r = self.s.round(f["round_id"])
        earlier = [dict(id=e["id"], **{k: json.loads(e["data"]).get(k) for k in ("title", "file", "line")})
                   for e in self.s.findings(release=self.release)
                   if e["verdict"] == "Material" and e["id"] != fid]
        specs = self.p.judges or [{"kind": "claude-code", "model": "claude-opus-5-5"},
                                  {"kind": "claude-code", "model": "claude-sonnet-5-5"}]
        law = LAW_PATH.read_text()
        prof = self.p.source.read_text()
        machine_reason = json.loads(f["machine"])["reason"] if f["machine"] else "not run"
        answers = []
        with tempfile.TemporaryDirectory(prefix="guard-judge-") as tmp:
            code = Path(tmp)
            arch = subprocess.run(["git", "-C", str(self.p.repo), "archive", r["commit_sha"]],
                                  check=True, capture_output=True).stdout
            subprocess.run(["tar", "-x", "-C", str(code)], input=arch, check=True)
            prompt = J.build_prompt(law, prof, {k: v for k, v in data.items()}, machine_reason, earlier, code)
            for spec in specs[:2]:
                a = J.run_judge(spec, prompt, code)
                if a.verdict and not _answer_plain(a.data):
                    a = _rewrite_plain(spec, a, code)
                answers.append(a)
        rec = [{"judge": a.judge, "verdict": a.verdict, "error": a.error, **a.data} for a in answers]
        vs = [a.verdict for a in answers]
        if len(vs) == 2 and vs[0] and vs[0] == vs[1]:
            best = answers[0].data
            dup = best.get("duplicate_of") if vs[0] == "Duplicate" else None
            self.s.update(fid, judges=rec, stage="done", verdict=vs[0],
                          rules=sorted({*best.get("rules", []), *answers[1].data.get("rules", [])}),
                          plain=_plain((best.get("what_happens", ""), best.get("what_it_means", ""),
                                        best.get("what_to_do", ""))), duplicate_of=dup)
            return {"verdict": vs[0], "judges": rec}
        self.s.update(fid, judges=rec, stage="arbiter")
        return {"verdict": None, "judges": rec, "why": "the judges did not agree; the Arbiter decides (Rule 14)"}

    def process(self, fid: int) -> dict:
        f = self.s.finding(fid)
        if f["stage"] == "machine":
            self.machine(fid)
            f = self.s.finding(fid)
        if f["stage"] == "judges":
            self.judge(fid)
        f = self.s.finding(fid)
        return {"id": fid, "stage": f["stage"], "verdict": f["verdict"]}

    # Rules 2, 14, 17
    def decide(self, fid: int, verdict: str, reason: str) -> dict:
        f = self.s.finding(fid)
        machine_ok = bool(f["machine"]) and json.loads(f["machine"]).get("passed")
        kind = "overrule" if machine_ok and verdict != "Material" else "decide"
        self.s.decide(fid, kind, verdict, reason)
        self.s.update(fid, verdict=verdict, stage="done")
        return {"id": fid, "verdict": verdict, "overruled": kind == "overrule"}

    def appeal(self, fid: int, side: str, evidence: str) -> dict:
        if not evidence.strip():
            raise RuntimeError("an appeal needs new evidence (Rule 17)")
        if any(d["kind"] == f"appeal:{side}" for d in self.s.decisions(fid)):
            raise RuntimeError(f"{side} has already appealed this finding (Rule 17)")
        self.s.decide(fid, f"appeal:{side}", None, evidence)
        self.s.update(fid, stage="arbiter")
        return {"id": fid, "stage": "arbiter"}


def _plain(parts) -> str:
    return json.dumps({"what_happens": parts[0], "what_it_means": parts[1], "what_to_do": parts[2]})


def _answer_plain(d: dict) -> bool:
    return all(is_plain(str(d.get(k, ""))) for k in ("what_happens", "what_it_means", "what_to_do"))


def _rewrite_plain(spec, a: J.JudgeAnswer, code: Path) -> J.JudgeAnswer:
    ask = ("Rewrite these three fields so a 12-year-old understands them: short sentences, everyday words, "
           "no code names. Keep the meaning. Answer with the same JSON object, all fields included.\n\n"
           + json.dumps(a.data))
    b = J.run_judge(spec, ask, code, timeout=600)
    if b.verdict == a.verdict:
        return J.JudgeAnswer(a.judge, a.verdict, {**a.data, **{k: b.data[k] for k in
                             ("what_happens", "what_it_means", "what_to_do") if k in b.data}}, a.raw)
    return a
