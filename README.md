# bifrost-guard

A law, an enforcer and a court for code reviews done by AI agents (or people).

AI reviewers never run out of things to say. Ask one to "find issues" and it will, every time,
and each fix gives the next one something new to find. bifrost-guard stops that loop without
hiding real problems:

- **The Law** ([`LAW.md`](LAW.md)) says what counts. Only real harm, as the project defines it,
  can block a release. Everything else is a Note for the operator to read, and no agent acts on it.
- **The enforcer** is an MCP server. Every agent that connects is told the Law first, and a
  finding only counts if it is handed in through the server, with a test.
- **The court** runs each finding's test itself, five times, with no network, on the exact
  commit. A finding passes only if it fails on its `HARM:` check every time, and only if it fakes
  nothing but the outside world. Two AI judges then try to disprove it. If they disagree, the
  operator decides, and the report shows the decision.
- **The report** starts with `Material findings: N` and explains every item in plain words.

Each rule follows an industry practice: Google's "Nit:", Chromium's release blockers, bug bounty
scope and duplicate rules, SonarQube's new-code rule, Fedora and Ubuntu freezes. See
[`SOURCES.md`](SOURCES.md). The Law was tested against the cases in [`CASES.md`](CASES.md).

## Quick start

```bash
pip install -e .
cp profiles/example-trading.yaml my-profile.yaml      # list your project's harms, conditions, tests

bifrost-guard --profile my-profile.yaml accept --owner alice --client bob   # both sides accept (Rule 1)
bifrost-guard --profile my-profile.yaml open --hours 48                     # open a round (Rule 3)
GUARD_PROFILE=my-profile.yaml bifrost-guard-mcp --transport streamable-http # agents hand in findings here
bifrost-guard --profile my-profile.yaml work --loop                          # the court, in the background
bifrost-guard --profile my-profile.yaml report                               # the result
```

The operator decides disagreements with `decide`, and each side may `appeal` once with new
evidence.

## A finding's test

A pytest file that fails on the reviewed commit, on an assertion whose message starts with
`HARM:`:

```python
def test_big_trade_written_once():
    ledger = Ledger()
    ledger.record(ticket=7, profit=150)
    assert ledger.total() == 150, "HARM: a big trade's profit is counted twice"
```

It may replace only the outside world (the packages listed under `allowed_stand_ins`), never the
project's own code (`reviewed_packages`).

## Law-only mode: the court runs on the reviewer's side

A project that must stay read-only can hand out the Law without running a court. Mount
`register_law_only(server, profile_path)` on the project's own MCP server. Agents then get the
Law first (`INSTRUCTIONS_LAW_ONLY`) and one read-only tool, `guard_rules`, which returns the Law,
the Profile and how to run the court themselves. No findings are sent to the project's server,
and its machine never runs a reviewer's code.

## Judges

Judges are set in the profile. `claude-code` runs the local Claude Code CLI, so it needs no API
key. `command` runs any program that reads the prompt on stdin and prints a JSON answer, so you
can plug in another model.

## Limits

- The court can't make an outside agent obey. It decides what counts. Both sides agree once that
  only the court's report is the result.
- The machine check runs the finding's test as real code. Run the court only on a machine you
  are willing to run the reviewer's tests on, ideally a container with no secrets in it.
- The stand-in check reads `monkeypatch` and `mock.patch` calls. A test that passes in a
  hand-written fake of the project's own code is not caught by the machine. The judges are told
  to catch it under Rule 13.

## Licence

MIT
