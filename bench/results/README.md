# Run 2: selfctx on 5 SWE-bench Verified tasks (isolated)

2026-11-17, commit 8b25fa0, Kimi K3.1 Pro, `--network none`, file tools confined to the repository.
Pre-registration: `prereg/2026-11-17-swebench-handpicked.md` (with amendment 1). Wall time 49 min.

| instance | resolved | FAIL_TO_PASS | turns | go-back turns | peak items | peak prompt tokens |
|---|---|---|---|---|---|---|
| django__django-11400 | no | 4/6 | 15 | 3 | 35 | 22 303 |
| pytest-dev__pytest-10356 | no | 0/1 | 14 | 5 | 47 | 20 245 |
| sympy__sympy-14248 | yes | 2/2 | 20 | 6, 8, 12, 18 | 58 | 47 779 |
| pylint-dev__pylint-8898 | no | 0/1 | 14 | 3, 14 | 37 | 20 993 |
| sphinx-doc__sphinx-9461 | no | 0/3 | 23 | none | 78 | 44 332 |

PASS_TO_PASS: no regression in any instance. Every run ended with `done`, far below 100 turns.

## Predictions
- P1 (1 <= R <= 4): R = 1. Holds.
- P2 (B >= 3): B = 4. Holds formally, but every go-back drops only 1 to 3 items, all of them a failed or
  malformed tool call and its error: go-back is used as "undo", not to prune context. No run discarded
  explored material the way run 1 did (turn 10: summarise the upstream fix, drop 11 items).
  Context grows almost monotonically (peak 78 items for sphinx, which never went back).
- P3 (E <= 5 %): 0 protocol errors in 86 turns. Holds. Malformed *tool arguments* still occur
  (sympy turns 6, 12, 18: "the previous shell requests were malformed"); the schema leaves `args` free-form.
- P4 (C <= 1): 0 crashes. Holds.
- P5 (peak < 100k tokens in >= 4/5): peak 47 779. Holds.

## Other observations
- Without being told it had no network, the model tried to fetch the upstream fix or related issues in
  3 of 5 runs (pylint: GitHub search API; sphinx: github.com and raw.githubusercontent.com;
  sympy: `curl` GitHub search). All failed.
- Per decision rule: P2 holds as registered, but its substance (pruning) is not observed; the
  pre-registered measure B was too weak to capture pruning, since one undo of a failed call counts.
