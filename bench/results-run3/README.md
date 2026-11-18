# Run 3: pruning incentive (sizes, budget 20 000, compaction prompt, per-tool args)

2026-11-17/18, commit 6223bdc, Kimi K3.1 Pro, isolated as run 2.
Pre-registration: `prereg/2026-11-17-pruning-incentive.md`. Measures: `bench/prune.py bench/results-run3`.

| instance | resolved (run 2) | FAIL_TO_PASS | turns | prune turns (items dropped) | peak prompt tokens (run 2) |
|---|---|---|---|---|---|
| django__django-11400 | no (no) | 4/6 | 8 | none | 14 736 (22 303) |
| pytest-dev__pytest-10356 | yes (no) | 1/1 | 15 | 9 (12) | 19 757 (20 245) |
| sympy__sympy-14248 | no (yes) | 1/2 | 37 | 6 (20), 15 (37), 23 (36), 31 (24), 35 (14) | 20 686 (47 779) |
| pylint-dev__pylint-8898 | no (no) | 0/1 | 41 | 7 (5), 10 (19), 32 (25), 36 (5) | 16 559 (20 993) |
| sphinx-doc__sphinx-9461 | no (no) | 0/3 | 21, crashed | 6 (15), 10 (20), 12 (5), 15 (23), 16 (5), 21 (17) | 25 935 (44 332) |

## Predictions
- Q1 (B5 >= 3): B5 = 4 (run 2: 0). Holds.
- Q2 (M < 22 303): M = 19 757. Holds. Peaks fell most where run 2 was largest (sympy 47.8k → 20.7k, sphinx 44.3k → 25.9k).
- Q3 (R >= 1): R = 1 (pytest). Holds. The resolved task changed (sympy lost, pytest gained): with one run
  per task this is noise per the decision rule.
- Q4 (E <= 5 %, C <= 1): E = 1/122, C = 1. Holds. The crash is the host losing network during an API call
  (`ConnectError: Network is unreachable`); agentknit retries timeouts and 5xx, not connection errors.

Decision rule: Q1 and Q3 hold → keep the treatment as the default and test on more tasks.

## Observations
- Compaction is radical: the large prunes mostly set `max_index` to 0 (keep only the task) and carry a
  dense state summary in `thoughts` (files changed, functions, exact outputs, plan). Context then restarts
  small; the model re-requests file excerpts when it needs exact text.
- sympy (resolved in run 2, not here): the final `done` says remaining suite failures are "stale assertions
  expecting the old output"; `test_MatrixSymbol_printing` is one of the target tests. Whether pruning
  dropped the evidence or the model misjudged is not established.
- Download attempts without network persist (pylint 4 replies, sphinx 1 incl. `pip install Sphinx==4.2.0`,
  sympy 1); all failed.
- django stopped after 8 turns with 4/6 target tests, claiming success from the `admin_filters` tests only.
