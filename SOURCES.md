# Where each rule comes from

Every rule in `LAW.md` follows a practice used by real software teams. This file shows which
one, and where the Law chooses something different. "General practice" means the practice is
common, but no single source was checked for it.

| Rule | Practice it follows | Source |
|---|---|---|
| 1 (fixed, fingerprinted rules) | Each release is judged against one fixed set of rules, and policy changes are reviewed like code. | General practice |
| 2 (only the referee's result counts) | On bug bounty platforms the researcher reports, but the program's triage decides the result. | [Intigriti triage standards](https://kb.intigriti.com/en/articles/10335710-intigriti-triage-standards), [HackerOne platform standards](https://docs.hackerone.com/organizations/platform-standards.html) |
| 3 (the Court runs rounds) | Bug bounty programs set a published scope and the platform's own submission process. | [Bugcrowd: anatomy of a bounty brief](https://www.bugcrowd.com/wp-content/uploads/2023/11/Anatomy-of-a-Bounty-Brief.pdf) |
| 4 (one full review, then fixes only) | SonarQube's "Clean as You Code" judges only new code, so the review does not drift back into old code. | [SonarQube docs](https://docs.sonarsource.com/sonarqube-server/10.5/user-guide/clean-as-you-code/) |
| 6, 7 (Material vs Note) | Google reviewers mark small comments "Nit:" so the author knows they do not block. AI review tools are set to comment only on bugs, security and data loss. | [Google eng-practices](https://google.github.io/eng-practices/review/reviewer/comments.html), [CodeRabbit: reduce noise](https://docs.coderabbit.ai/configuration/guides/reduce-noise) |
| 6 (harm decides) | Chromium marks a bug as a release blocker only if the product must not ship with it. | [Chromium release blockers](https://chromium.googlesource.com/chromium/src/+/main/docs/process/release_blockers.md) |
| 7 (low impact closed as "informative") | Bug bounty platforms close low-impact reports as "informative" and keep a list of low-value issue types. | [Intigriti triage standards](https://kb.intigriti.com/en/articles/10335710-intigriti-triage-standards), [Bugcrowd VRT](https://bugcrowd.com/vulnerability-rating-taxonomy/1.10.pdf) |
| 8 (fail closed, but never on protection) | Safety design says a failure should leave a system in a safe state, and a skipped protection is never a safe state. | General practice |
| 9 (proof required) | Bug bounty programs expect clear steps to reproduce and demonstrated impact. | [HackerOne on report quality](https://www.hackerone.com/blog/ai-driven-report-volume-insights-and-actions) |
| 10, 3 (scope and conditions) | Anything outside a program's scope is out of scope. Out of scope is the most common reason reports are rejected. | [Study of invalid HackerOne reports](https://arxiv.org/html/2511.18608v1) |
| 10 (unusual conditions) | Chromium lowers the rating of bugs that need unusual settings or behaviour. | [Chromium severity guidelines](https://chromium.googlesource.com/chromium/src/+/main/docs/security/severity-guidelines.md) |
| 11 (accepted risks) | A known risk counts as accepted only when the owner has signed it off. | General practice (risk acceptance) |
| 12 (one cause, one finding) | HackerOne treats reports with the same root cause as duplicates. Intigriti asks whether the first fix would have fixed the other report too. | [HackerOne platform standards](https://docs.hackerone.com/organizations/platform-standards.html), [Intigriti: duplicate reports](https://kb.intigriti.com/en/articles/4917102-duplicate-related-or-known-vulnerability-reports) |
| 13 (runnable proof, run more than once) | TigerBeetle and FoundationDB rely on checks that replay the same way every time. Re-running a test to detect flakiness is general practice. | [TigerBeetle VOPR](https://docs.tigerbeetle.com/about/vopr), [FoundationDB testing](https://apple.github.io/foundationdb/testing.html) |
| 13 (fake only the outside world) | Tests replace outside systems with stand-ins, not the code under test. | General practice |
| 14 (judges try to disprove) | False positives fall sharply when each AI review comment is checked adversarially. | [DEV: AI code review engineers trust](https://dev.to/kirandeepjassalcrypto/ai-code-review-that-engineers-actually-trust-the-pipeline-we-run-on-every-pull-request-21fp) |
| 17 (one appeal) | Bug bounty platforms offer mediation when the two sides disagree on a ruling. | General practice |
| 19 (plain words) | Plain-language writing guidelines ask for short sentences, everyday words, and the main point first, for readers who are not experts. | General practice (plain-language guidelines) |
| 20 (smallest fix, prefer revert, keep the test) | Release teams accept only blocker fixes after a freeze and revert risky late changes. Studies find 15 to 25% of fixes in systems code are wrong (about 39% for concurrency). Keeping a regression test for every fixed bug is general practice. | [Fedora final freeze](https://fedoraproject.org/wiki/Final_Freeze_Policy), [Kubernetes release phases](https://git.k8s.io/sig-release/releases/release_phases.md), [Summary of "How do fixes become bugs?"](https://swreflections.blogspot.com/2011/11/incorrect-bug-fixes.html) |
| 21 (agents hand non-blockers to a person) | Non-blocking review comments are left for the author to decide on, not acted on by the reviewer. | [Google eng-practices](https://google.github.io/eng-practices/review/reviewer/comments.html) |
| 22 (freeze) | Ubuntu and Fedora freeze before release and allow only must-fix changes after it. | [Ubuntu freezes](https://documentation.ubuntu.com/project/release-team/freezes/) |
| 23 (cap, then a person) | Teams running AI review loops cap the number of rounds and hand over to a person. | [DEV: two years of AI-assisted coding](https://dev.to/yw1975/after-2-years-of-ai-assisted-coding-i-automated-the-one-thing-that-actually-improved-quality-ai-2njh), [freeCodeCamp: break the fix loop](https://www.freecodecamp.org/news/how-to-break-the-ai-coding-agent-fix-loop/) |

## Where the Law differs, and why

- **Two levels, not four or five.** Chromium, Mozilla and Bugcrowd use more severity levels, but
  their release decision is still yes or no. The Law keeps only that yes or no, Material or Note,
  so judges have less to argue about.
- **A rare bug is not marked down.** Chromium marks down bugs that need unusual conditions. The
  Law marks down only bugs that need broken Operating Conditions (Rule 10). When money is at
  stake, a proven wrong record is wrong however rare it is. Made-up risks are kept out by the
  proof rule and the machine check.
- **One clean round, not a falling trend.** Large projects watch the bug rate fall over weeks.
  A small project cannot wait that long. Strict proof, the machine check and the three-strikes
  cap keep a single round meaningful and stop it repeating forever.
