# bifrost-guard: The Law

Version 1.0. First accepted by both sides of a project on 23 November 2026 (GoldLab).

These are the rules for reviewing software, whether the reviewer is a person or an AI agent.
They say what counts as a real problem, what proof is needed, who decides, and when the review
is finished.

The Law is the same for every project. Each project adds a **Profile**, which lists what "harm"
means for that project, the conditions it runs under, and the problems both sides have accepted.

---

## Part 1. Words used here

- **Release**: the version of the software that is going to be used. It starts at one commit
  and changes only through fixes made under this Law.
- **Reviewer**: anyone looking for problems, person or AI.
- **Finding**: a problem a reviewer reports.
- **Court**: the tool and the judges that decide what each finding is.
- **Round**: one review session that the Court opens and closes (Rule 3).
- **Operator**: the person who runs the project and is responsible for it.
- **Arbiter**: the person who decides when the judges disagree, and who hears appeals. The
  Arbiter is always the Operator.
- **Both sides**: the owner of the software and the person it is built for.

## Part 2. Accepting the rules

**Rule 1. One accepted set of rules.** Both sides accept one exact version of the Law and the
Profile. Each file has a fingerprint (a hash of its contents). The fingerprint also covers every
file the Profile points to, such as its known-problems list and its runbook. Changing any of
them makes a new version, and both sides must accept it again.

**Rule 2. Only the Court's report counts.** By accepting the Law, both sides agree that the
result of a review is the Court's report, and nothing else. A reviewer's own words outside the
Court are not the result. Every decision the Arbiter makes is written in the Court's report with
its reason, so both sides can see it. If the Arbiter rules that a finding which passed the machine
check (Rule 13) is not Material, the report marks it **Overruled by the Arbiter**.

## Part 3. Rounds

**Rule 3. The Court runs the rounds.** Only the Court opens a round. Each round has a start
time, a closing time, and the commit it reviews. Findings must be handed to the Court before
the round closes. A finding that arrives later goes into the next round.

**Rule 4. One full review per Release.** The first round on a Release reviews the whole of it.
Every round after that reviews only what the fixes changed: the changed lines and the functions
that contain them. Fixing the code does not start a new full review.

**Rule 5. Harm found outside the current scope.** A real harm can be reported at any time and
is never thrown out for being out of scope. If it is found outside a round, or in code the
current round is not reviewing, it is handled under Rule 20. It is counted in the report of the round open when it was handed in, or
of the next round if none is open. It does not reopen the full review.

## Part 4. What counts as a problem

**Rule 6. Material means real harm.** A finding is **Material** only if it shows one of the
harms listed in the Profile. If the Profile's harms and the examples in Rule 7 disagree, the
Profile wins.

**Rule 7. Everything else is a Note.** Messages, logs, alerts, wording, documents, how things
look on screen, speed, style, test quality, and "a better way to write this" are all Notes. A
Note never blocks a Release. Notes are written down and can be fixed in a later version.

**Rule 8. Refusing is safe; failing to protect is not.** If the only effect of a problem is
that the software refuses, delays or skips **starting** something risky, such as opening a new
position, it is a Note. This is called "failing closed". Failing closed never covers
protective actions or records: closing a position, keeping its stop, or writing a money record.
If one of those is skipped, that is harm.

**Rule 9. Proof is required.** A Material finding must give all five of these:

1. the file and line;
2. the steps: the starting state, the inputs, and the order of events;
3. what happens, and what should happen instead;
4. which harm in the Profile it causes;
5. a test the Court can run (Rule 13).

A finding without a test is a **Question**. Questions get an answer, not a verdict. If a test
is truly impossible, the reviewer may give real records from the running software instead. The
Court treats them the same way as a test: the records must show the harm happening.

**Rule 10. Normal conditions only.** The harm must happen under the Operating Conditions in the
Profile. A finding that needs one of those conditions to be broken is **Not valid**.

**Rule 11. Accepted problems are not new.** A finding is **Known** only if the accepted
known-problems list (Rule 1) describes it and the facts still match. If they no longer match, or
the problem is not on the accepted list, the finding is judged like any other.

**Rule 12. One cause, one finding.** Two findings are the same if the smallest fix for the
first would also cure the second. The first one handed to the Court counts. The others are
**Duplicate**.

## Part 5. How the Court decides

**Rule 13. The machine checks first.** The Court runs the finding's test on the reviewed commit
itself:

- The test must end with a check that states the harm in plain terms, for example "this ticket
  has exactly one ledger row". That check must be the one that fails.
- The test may replace only the outside world with stand-ins: the broker, the network, the
  database server, the clock and the messaging services. It may not change or replace the code
  being reviewed.
- The Court runs the test five times. It must fail every time.

If any of these is not met, the verdict is **Not valid**. A proven harm counts however rare it
is.

**Rule 14. Two judges, then the Arbiter.** Two judges look at every finding that passes Rule 13.
Each one tries to disprove it. If they agree, that is the verdict. If they disagree, the Arbiter
decides.

**Rule 15. Six verdicts.** Every finding gets exactly one verdict, and the verdict names the
rules it used.

| Verdict | Meaning |
|---|---|
| **Material** | Real harm, proven (Rules 6, 9, 13) |
| **Note** | True, but not a harm (Rules 7, 8) |
| **Known** | On the accepted known-problems list (Rule 11) |
| **Duplicate** | Same cause as an earlier finding (Rule 12) |
| **Not valid** | Fails the machine check, needs broken conditions, is the owner's choice, or is a Note outside the round's scope (Rules 4, 10, 13, 16) |
| **Question** | No proof given (Rule 9) |

**Rule 16. Choices are not defects.** Business or strategy choices that the Profile lists as the
owner's to make are not problems to report.

**Rule 17. One appeal.** Either side may appeal a verdict once, to the Arbiter, and only with
evidence the judges did not have. The Arbiter's decision is final for that version.

**Rule 18. The report.** The first line of every Court report is:

    Material findings: N

It then lists each Material finding, the Operator's list (Rule 21), each judge's reasons, every
Arbiter decision with its reason, and the fingerprints of the commit, the Law and the Profile it
used.

**Rule 19. Plain words.** Every report, verdict, reason and item on the Operator's list is
written so that someone who is not a developer can understand it: short sentences, and words a
12-year-old knows. Each item says, in one or two sentences:

- what happens, as a real-world event ("the same trade is written down twice");
- what it means for the project: what can go wrong and how bad it is, or plainly "this cannot
  lose money or cause a wrong trade";
- what the Operator needs to do, or "nothing".

Technical details (file names, code, test output) come after that, under their own heading. A
term the Operator may not know is explained the first time it is used.

## Part 6. Fixing and finishing

**Rule 20. Fix only what is Material.** Before a Release is used, only Material findings are
fixed. Each fix is the smallest change that removes the harm. The finding's test joins the
software's permanent tests, so a later change cannot bring the harm back without a test
failing. Taking out a recent change is preferred to adding new code, as long as no permanent
test fails. If a Material harm is found while the Release is in use, the owner either fixes it
this way or stops using the affected feature until it is fixed.

**Rule 21. Agents do not act on anything that is not Material.** Reviewers, judges and any
agent that fixes code may act only on Material findings, under Rule 20. Everything else (Notes,
Questions, Known, Duplicate, Not valid, and proposals to change the rules) goes to the
**Operator's list** in the Court's report. No agent fixes, changes or decides anything on that
list, even when the change looks small or easy. Only the Operator decides what happens to it,
and when.

**Rule 22. When it is done.** A Release is ready when:

1. its full review (Rule 4) has been held;
2. all of its tests pass, including the permanent tests from Rule 20; and
3. the latest round ends with `Material findings: 0`.

The Release is then frozen. After that, only a Material finding may change it.

**Rule 23. Three strikes, then the Arbiter.** If three rounds in a row on the same Release each
end with at least one Material finding, the fixing stops. The Arbiter then decides: use the
Release with those problems listed, remove the feature, or redesign it. A redesign is a new
Release.

## Part 7. Changing the Law

**Rule 24. Disagreeing with the rules is not a finding.** Anyone may propose a change to the Law
or the Profile. A proposal must show a concrete case where the current rules give the wrong
answer. A proposal never blocks a round. Accepted changes apply only to rounds that open after
both sides accept the new version.

---

*The practice behind each rule is in `SOURCES.md`. The cases the Law was tested against are in
`CASES.md`.*
