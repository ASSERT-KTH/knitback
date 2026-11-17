# Pre-registration: does a visible context cost make selfctx prune? (run 3)

Committed before run 3.

## Question
In run 2 the model went back only to undo failed calls (1-3 items each), never to discard explored
material. Does showing context cost and explaining compaction change that, without hurting resolution?

## Changes since run 2 (the treatment)
- Item headers carry an estimated size (`[i] kind ~N tokens`); a trailing status message gives the
  context size and a soft budget of 20 000 tokens.
- The system prompt no longer says kept items are cheap thanks to the prompt cache; it says every kept
  token is re-read every turn and describes compaction (conclusions in `thoughts`, then go back before the
  exploration).
- Per-tool argument schemas in the turn schema; calls with unknown or missing arguments are refused with
  the expected parameter list.

## Setup (unchanged from run 2 otherwise)
Same 5 tasks (`bench/tasks.json`), Kimi K3.1 Pro, `--network none`, file tools confined to the repository,
`max_turns` 100, one run per task, swebench 4.1.0 judge. Command:
`.venv/bin/python bench/run_swebench.py --out bench/results-run3 --context-budget 20000`.

## Measures (`bench/prune.py`, validated on runs 1 and 2: run 1 django turn 10 counts, run 2 has none)
- Prune turn: a turn whose `max_index` drops at least 5 items.
- B5: number of runs with at least one prune turn. Run 2: 0/5.
- M: median over the 5 runs of the run's peak prompt tokens (API-reported). Run 2: 22 303.
- R: resolved count. Run 2: 1 (sympy).
- E: protocol errors / turns. C: crashed runs.

## Predictions
- Q1: B5 >= 3.
- Q2: M < 22 303.
- Q3: R >= 1.
- Q4: E <= 5 % and C <= 1.

## Decision rule
- Q1 fails: prompt-level incentives are not enough; next step is a structural change (e.g. a compaction
  request that the host turns into a summary item), not more prompt wording.
- Q1 holds and Q3 fails: pruning loses needed information; inspect what was dropped before going further.
- Q1 and Q3 hold: keep the treatment as the default and test on more tasks.
- 5 tasks, one run each: R differences of 1 are noise and are reported, not interpreted.
