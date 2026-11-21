# Cases the Law is tested against

Each case is a situation the Law must handle. "Must" is the right answer. "Law" is the rule that
gives it. A case passes when the Law gives the right answer and the review still ends.

A proposal to change the Law (Rule 24) must add a case here that the current Law gets wrong.

## A. The review must end

| # | Situation | Must | Law | Result |
|---|---|---|---|---|
| A1 | The client runs fresh AI agents every day. | The review still ends. | Rules 3, 4: only the Court opens rounds, and after the full review a round covers only fixes. With no fixes there is nothing left to review. Real harm is still heard (Rule 5). | Pass |
| A2 | A fix creates a new commit. | The whole review does not restart. | Rule 4: fixes do not start a new full review. | Pass |
| A3 | During a fixes-only round, a reviewer reports harm in old code. | It is heard, but the full review does not reopen. | Rule 5: handled under Rule 20, counted in that round's report. | Pass |
| A4 | A finding arrives after a round closes. | It waits for the next round. | Rule 3. | Pass |
| A5 | Three rounds in a row each find real harm. | Fixing stops and a person decides. | Rule 23. | Pass |
| A6 | A reviewer argues that a rule is wrong. | The round is not blocked. | Rule 24. | Pass |
| A7 | A reviewer sends 500 small comments. | Nothing is blocked. | Rule 7: Notes never block. | Pass |
| A8 | Two judges disagree. | A person decides, once. | Rules 14, 17. | Pass |
| A9 | A losing side keeps arguing. | One appeal with new evidence, then final. | Rule 17. | Pass |
| A10 | A race test passes sometimes and fails sometimes. | Not counted. | Rule 13: it must fail all five runs. | Pass |
| A12 | A judge sees a Note that could be fixed in one line. | No agent touches it. It goes to the Operator. | Rule 21. | Pass |
| A13 | A fixing agent, while fixing a Material finding, notices a small unrelated problem. | It fixes only the Material finding. The rest goes to the Operator's list. | Rules 20, 21. | Pass |
| A14 | A judge reports a Note as "swallowed exception in _persist_quiet on store failure". | Rewritten in plain words, impact first. | Rule 19: for example "If the database hiccups, one save is skipped and nothing is written in the log. This cannot cause a wrong trade or lose money; new trades are paused until the next save works. You need to do nothing." | Pass |
| A11 | Rule 15 lists verdicts and Rule 9 creates "Question". | No verdict is missing from the table. | Rule 15 lists all six. | Pass |

## B. Real harm must not be hidden

| # | Situation | Must | Law | Result |
|---|---|---|---|---|
| B1 | A test rigs the reviewed code into a state that never really happens. | Not counted. | Rule 13: stand-ins only for the outside world. | Pass |
| B2 | A test makes the database slow, to show two writes overlapping. | Counted, if it fails five times. | Rule 13: the database server is outside world. | Pass |
| B3 | The owner writes a real bug into the known-problems list without the client agreeing. | It still counts. | Rules 1, 11: only the accepted, fingerprinted list counts. | Pass |
| B4 | The exit manager skips pulling in a stop. | Harm. | Rule 8: failing closed never covers protection. | Pass |
| B5 | The gate wrongly refuses entries for two minutes. | Note. | Rule 8: refusing to start something risky. | Pass |
| B6 | A close is skipped. | Harm. | Rule 8. | Pass |
| B7 | A fix is "rewrite the module", so every finding becomes a duplicate. | Not allowed. | Rule 12: the smallest fix decides. | Pass |
| B8 | Removing a late change brings back an old bug. | Caught. | Rule 20: every Material finding's test stays in the permanent tests. | Pass |
| B9 | A proven harm happens only rarely. | Counted. | Rule 13: rare still counts. | Pass |
| B10 | The Arbiter (the Operator) rules a machine-proven finding is not Material. | Both sides can see it. | Rule 2: the report marks it "Overruled by the Arbiter", with the reason. | Pass |
| B11 | The Court's report could hide the judges' thinking. | The reasons are shown. | Rule 18. | Pass |
| B12 | A dashboard figure is shown with the wrong currency sign, though the figure is right. | Note. | Profile H3: how a figure is shown is a Note. | Pass |
| B13 | A risk figure the gate uses is calculated wrongly. | Harm. | Profile H3. | Pass |

## C. Outside the Law

| # | Situation | Handled by |
|---|---|---|
| C1 | A reviewer never uses the Court and tells its owner "I found 10 issues". | Rule 2 makes the Court's report the only result, but only once both sides have accepted the Law. The tool itself (next step) makes the Court the way findings are handed in. |
