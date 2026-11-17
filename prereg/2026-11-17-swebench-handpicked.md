# Pre-registration: selfctx on 5 hand-picked SWE-bench Verified tasks

Committed before any agent run on these tasks.

## Question
Does the self-maintained-context loop work on non-trivial real-world tasks, and does the model actually
use the ability to discard context?

## Setup
- Agent: selfctx at the commit of this file, Kimi K3.1 Pro (`k3.1-pro`, inference-db `kimi-coding`,
  `temperature=1`), turn schema sent as `response_format: json_schema`, `max_item_chars` 30 000,
  `max_turns` 100, one run per task, no prompt change between tasks.
- Harness: `bench/run_swebench.py`; judge: official `swebench` 4.1.0 `run_evaluation`, images from the
  `swebench` Docker Hub namespace.
- Tasks (`bench/tasks.json`), all SWE-bench Verified difficulty "1-4 hours", one per repository, gold patch
  touching 1-3 files: `django__django-11400`, `pytest-dev__pytest-10356`, `sympy__sympy-14248`,
  `pylint-dev__pylint-8898`, `sphinx-doc__sphinx-9461`.
  Chosen by: difficulty, repository diversity, multi-file gold patch, image size (~1.1 GB).
- Instrument check: gold patch of `django__django-11400` resolved, a no-op patch (adds `noop.txt`) not resolved.

## Measures (from `bench/results/<id>/result.json` and `run.jsonl`)
- R: resolved count (official report).
- B: runs with at least one "go back" turn (`max_index < items_before - 1`).
- E: protocol errors / total turns, over all runs.
- C: runs ending with a crash (exception from the endpoint, e.g. context overflow).
- T: peak prompt tokens per run.

## Predictions
- P1: 1 <= R <= 4 (point guess 2).
- P2: B >= 3 (the model discards context in most runs when tasks are long).
- P3: E <= 5 %.
- P4: C <= 1.
- P5: peak prompt tokens < 100 000 in at least 4 of 5 runs.

## Decision rule
- P2 fails: next work is making discarding worthwhile to the model (prompt, visible context size), before
  any further benchmarking.
- P3 or P4 fails: fix robustness (schema, error handling) first.
- R = 0: inspect trajectories for a loop-level cause before attributing it to the model.
- With 5 tasks, R is reported, not compared to any leaderboard number.

## Amendment 1 (2026-11-17, before the rerun)
- Run 1 (`bench/results-run1-network/`) is excluded from the predictions. Its task containers had network
  access: at turn 9 of `django__django-11400` the model fetched the accepted upstream patch
  (`https://github.com/django/django/pull/11400.patch`) and copied it; its "resolved" is void.
  `pytest-dev__pytest-10356` (not resolved, no fetch found) finished too; the run was stopped during
  `sympy__sympy-14248`.
- Harness changes, the only ones: task containers run with `--network none`; host file tools
  (file requests, `write_file`, `str_replace`) refuse paths outside the task's repository copy, since the
  host holds run 1's patches.
- Agent, prompt, tasks, measures, predictions and decision rule are unchanged. All 5 tasks are rerun.
