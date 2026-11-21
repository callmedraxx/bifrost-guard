import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from bifrost_guard.court import Court
from bifrost_guard.machine import check_stand_ins
from bifrost_guard.plain import grade, is_plain
from bifrost_guard.profile import load_profile
from bifrost_guard.report import release_status, round_report
from bifrost_guard.store import Store

LEDGER = '''
class Ledger:
    def __init__(self):
        self.rows = []

    def record(self, ticket, profit):
        self.rows.append((ticket, profit))
        if profit > 100:  # the bug: big trades are written twice
            self.rows.append((ticket, profit))

    def total(self):
        return sum(p for _, p in self.rows)
'''

HARM_TEST = '''
from toybot.ledger import Ledger

def test_big_trade_once():
    l = Ledger()
    l.record(7, 150)
    assert l.total() == 150, "HARM: a big trade's profit is counted twice"
'''


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def world(tmp_path):
    repo = tmp_path / "toy"
    (repo / "toybot").mkdir(parents=True)
    (repo / "toybot" / "__init__.py").write_text("")
    (repo / "toybot" / "ledger.py").write_text(LEDGER)
    (repo / "toybot" / "clock.py").write_text("import time\ndef now():\n    return time.time()\n")
    (repo / "docs").mkdir()
    (repo / "docs" / "KNOWN_LIMITS.md").write_text("# Known\n- none\n")
    git(repo, "init", "-q", "-b", "main")
    git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
    git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init")
    judge = tmp_path / "judge.py"
    judge.write_text(textwrap.dedent('''
        import json, os, sys
        sys.stdin.read()
        v = os.environ.get("JUDGE_" + sys.argv[1], "Material")
        print(json.dumps({"verdict": v, "rules": [6, 13], "harm": "H2", "duplicate_of": None,
            "what_happens": "The same trade is written down twice.",
            "what_it_means": "The profit is counted two times, so the total is wrong.",
            "what_to_do": "Fix it before use.", "reasons": "test shows it"}))
    '''))
    prof = tmp_path / "profile.yaml"
    prof.write_text(textwrap.dedent(f'''
        name: toy
        version: "1"
        repo: {repo}
        harms:
          - {{code: H1, title: Wrong trade, meaning: wrong trade}}
          - {{code: H2, title: Wrong money record, meaning: profit wrong or doubled}}
        pinned_files: [docs/KNOWN_LIMITS.md]
        known_problems: docs/KNOWN_LIMITS.md
        machine_check:
          python: {sys.executable}
          runs: 3
          no_network: false
          reviewed_packages: [toybot]
          allowed_stand_ins: [toybot.clock]
        judges:
          - {{kind: command, run: "{sys.executable} {judge} A", name: A}}
          - {{kind: command, run: "{sys.executable} {judge} B", name: B}}
    '''))
    p = load_profile(prof)
    c = Court(p, Store(tmp_path / "guard.db"), "1")
    return c, repo


def finding(**kw):
    base = dict(title="big trades counted twice", file="toybot/ledger.py", line=8, steps="record 150",
                happens="two rows", should="one row", harm="H2", test=HARM_TEST)
    base.update(kw)
    return base


def test_intake_sorts_notes_and_questions(world):
    c, _ = world
    c.accept("HEAD", "op", "client")
    c.open_round("HEAD", 1)
    assert c.submit("r", finding(harm=""))["verdict"] == "Note"
    assert c.submit("r", finding(harm="LOGS"))["verdict"] == "Note"
    assert c.submit("r", finding(test=""))["verdict"] == "Question"
    assert c.submit("r", finding())["verdict"] is None


def test_machine_check_and_judges_material(world, monkeypatch):
    c, _ = world
    c.accept("HEAD", "op", "client")
    rid = c.open_round("HEAD", 1)["round"]
    fid = c.submit("r", finding())["id"]
    out = c.process(fid)
    assert out["verdict"] == "Material"
    rep = round_report(c.s, rid)
    assert rep.splitlines()[0] == "Material findings: 1"
    assert "The same trade is written down twice." in rep


def test_machine_rejects_passing_unmarked_and_rigged_tests(world):
    c, _ = world
    c.accept("HEAD", "op", "client")
    c.open_round("HEAD", 1)
    passing = HARM_TEST.replace("l.record(7, 150)", "l.record(7, 50)").replace("== 150", "== 50")
    unmarked = HARM_TEST.replace(', "HARM: a big trade\'s profit is counted twice"', "")
    rigged = HARM_TEST.replace("def test_big_trade_once():",
                               "def test_big_trade_once(monkeypatch):\n"
                               "    monkeypatch.setattr('toybot.ledger.Ledger.total', lambda self: 999)")
    for src in (passing, unmarked, rigged):
        fid = c.submit("r", finding(test=src))["id"]
        assert c.process(fid)["verdict"] == "Not valid", src


def test_stand_in_rules():
    from types import SimpleNamespace
    p = SimpleNamespace(reviewed_packages=["toybot"], allowed_stand_ins=["toybot.clock"])
    ok = check_stand_ins("import toybot.clock as ck\ndef t(monkeypatch):\n"
                         "    monkeypatch.setattr(ck, 'now', lambda: 1)\n", p)
    bad = check_stand_ins("from toybot import ledger\ndef t(monkeypatch):\n"
                          "    monkeypatch.setattr(ledger.Ledger, 'total', lambda s: 1)\n", p)
    assert ok.ok and ok.replaced == ["toybot.clock.now"]
    assert not bad.ok and bad.forbidden == ["toybot.ledger.Ledger.total"]


def test_changed_pinned_file_blocks_a_round(world):
    c, repo = world
    c.accept("HEAD", "op", "client")
    (repo / "docs" / "KNOWN_LIMITS.md").write_text("# Known\n- the double count is fine\n")
    git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qam", "sneak")
    with pytest.raises(RuntimeError, match="KNOWN_LIMITS"):
        c.open_round("HEAD", 1)


def test_second_round_reviews_only_fixes(world):
    c, repo = world
    c.accept("HEAD", "op", "client")
    assert c.open_round("HEAD", 1)["scope"] == "full"
    c.close_round()
    (repo / "toybot" / "ledger.py").write_text(LEDGER.replace("profit > 100", "False"))
    git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qam", "fix")
    r2 = c.open_round("HEAD", 1)
    assert r2["scope"] == "fixes"
    note_far = c.submit("r", finding(harm="", file="toybot/clock.py", line=2))
    assert note_far["verdict"] == "Not valid"
    harm_far = c.submit("r", finding(file="toybot/clock.py", line=2))
    assert harm_far["verdict"] is None and "always heard" in harm_far["why"]


def test_disagreement_goes_to_arbiter_and_overrule_is_shown(world, monkeypatch):
    c, _ = world
    monkeypatch.setenv("JUDGE_B", "Note")
    c.accept("HEAD", "op", "client")
    rid = c.open_round("HEAD", 1)["round"]
    fid = c.submit("r", finding())["id"]
    assert c.process(fid)["stage"] == "arbiter"
    assert "need your decision" in round_report(c.s, rid)
    assert c.decide(fid, "Note", "only happens in a test setup")["overruled"]
    rep = round_report(c.s, rid)
    assert rep.splitlines()[0] == "Material findings: 0"
    assert "Overruled by the Arbiter" in rep


def test_one_appeal_per_side(world):
    c, _ = world
    c.accept("HEAD", "op", "client")
    c.open_round("HEAD", 1)
    fid = c.submit("r", finding(harm=""))["id"]
    c.appeal(fid, "client", "new log lines show it")
    with pytest.raises(RuntimeError, match="already appealed"):
        c.appeal(fid, "client", "more")
    with pytest.raises(RuntimeError, match="new evidence"):
        c.appeal(fid, "owner", " ")


def test_finding_without_a_round_waits(world):
    c, _ = world
    c.accept("HEAD", "op", "client")
    r = c.submit("r", finding())
    assert "no round is open" in r["why"]
    rid = c.open_round("HEAD", 1)["round"]
    assert c.s.finding(r["id"])["round_id"] == rid


def test_ready_and_three_strikes(world):
    c, repo = world
    c.accept("HEAD", "op", "client")
    c.open_round("HEAD", 1)
    c.close_round()
    assert "Ready" in release_status(c.s, "1")
    for i in range(3):
        if i:
            (repo / "toybot" / f"f{i}.py").write_text("x = 1\n")
            git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A")
            git(repo, "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", f"f{i}")
            c.open_round("HEAD", 1)
        else:
            c.s.db.execute("UPDATE rounds SET closed=NULL WHERE id=1")
        fid = c.submit("r", finding())["id"]
        c.process(fid)
        c.close_round()
    assert "Three rounds in a row" in release_status(c.s, "1")


def test_plain_words():
    assert is_plain("The same trade is written down twice. You need to do nothing.")
    assert not is_plain("Asynchronous concurrent persistence invocations nondeterministically "
                        "materialize duplicated ledger representations under contention.")
    assert grade("") == 0.0
