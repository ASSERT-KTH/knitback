# knitback

A coding agent with a radically different loop: the model is aware of its own context and maintains it
itself. The context is a sequence of numbered items; at each turn the model says which prefix to keep
(`max_index`), and which file excerpts and tool results to append, in which order.
Related work is surveyed in [PRIOR-ART.md](PRIOR-ART.md).

The name comes from knitting: to knit back is to undo stitches to an earlier point, which is what
`max_index` does; it is built on [agentknit](../agentknit). Before 2026-11-18 the tool was called
`selfctx`, the name used in `prereg/` and the run logs under `bench/`.

## Context model

- The context is a sequence of items, indexed from 0.
- One item is one file excerpt, one tool result, or one model output
  (its reasoning plus `max_index` and the request list).
- Every item is shown to the model with its index and estimated size (e.g. `[17] file ~850 tokens`),
  so the model knows what to keep.
- After the last item, a status message that is not an item gives the context size and a soft budget
  (`[context] 42 items, ~23000 tokens (budget ~20000 tokens)`).
- No item is protected: the model may truncate down to and including the task description.

## Caching awareness

The core concept is that the context is prompt-cache aware by construction:

- Items are only ever appended or truncated, never edited in place. The request of every turn is
  therefore the previous request's prefix up to `max_index`, followed by new items: a provider's
  prefix cache serves everything kept, and only what follows the cut is processed anew.
- One chat message per item, so a kept item renders byte-identically from turn to turn.
- The system prompt and the turn schema (`response_format`) are constant across turns.
- The only text that changes every turn (the `[context]` status) is the last message, after the
  cached prefix.

The cost of a turn is thus driven by where the model cuts: keeping a long stable prefix is cheap,
while cutting deep and re-requesting material sends it uncached again. The current system prompt
says that every kept token is re-read each turn and explains compaction; it gives no cue about the
cache. Cache hits are logged per turn (`usage.cached_tokens`) for measuring how well the model's cuts
fit the cache.

## Turn protocol

At each turn, the model outputs one JSON object:

1. `max_index`: the last item (inclusive) kept for the next turn.
   Items after it are discarded, which lets the model go "back" in context
   and drop recent additions it no longer needs, or compact: write its conclusions in `thoughts`,
   then cut before the exploration that produced them.
2. `requests`, an ordered list, each one either:
   - a file excerpt: a path plus line range, or
   - a tool call, whose result is the new item.
3. `thoughts`, and `done` (the final answer, which ends the run).

The reasoning is the summary. The reply that cuts is written while the model still sees the items it
drops, and it is appended right after the cut, so its `thoughts` carry whatever survives of them;
there is no separate summary operation. A dropped item cannot be fetched back: a file excerpt can be
requested again (exact text while the file is unchanged), a command can be run again (at its cost,
with its side effects), and anything else must have been copied into `thoughts`.

The next turn's context is items `0..max_index`, followed by the model output as one item,
then one new item per request, in the order the model listed them.
The prompt tells the model that it controls this order.

## Implementation

The `knitback` package: `_items.py` (items, rendering, truncation), `_protocol.py` (system prompt,
turn schema, output parsing), `_loop.py` (the turn loop), `__main__.py` (CLI).

agentknit (`../agentknit`, editable path dependency) supplies only the model client and the tools
(`write_file`, `str_replace`, `exec_shell`; files are read through file requests). No agentknit
session runs, so none of its compaction or awareness features interfere: the model alone manages
its context.

Each request carries the turn schema as `response_format: json_schema`, with one argument schema
per tool. Kimi K3.1 (kimi-coding) accepts it but does not enforce it at decoding
(`probes/kimi-constrained-decoding/`), so replies are parsed and validated, and tool calls with
unknown or missing arguments are refused with the expected parameter list. Tool outputs longer than
30 000 characters keep their head and tail.

## Install

```
uv venv .venv && uv pip install -p .venv -e '.[dev]'
```

## Usage

```
knitback "make the tests pass"            # prints the final answer
knitback --json "make the tests pass"     # {"final", "turns", "items", "log"}
echo "task" | knitback
knitback --model k3.1-pro --inference-db kimi-coding --max-turns 50 --context-budget 20000 --log-dir runs "task"
```

Defaults: Kimi K3.1 Pro through the agentknit inference-db entry `kimi-coding`.
Exit code 0 when the model sets `done`, 1 after `--max-turns` without an answer, 2 on an empty task.
Tool output is streamed to stderr; stdout carries only the answer.
`--no-schema` omits the turn schema, for endpoints without `json_schema`.
The context budget is soft: it is shown to the model, never enforced.

Each run writes `runs/<timestamp>.jsonl`, one record per turn:
`turn`, `items_before`, `max_index`, `items_after`, `new_items` (kind and estimated tokens of each
appended item), `usage` (`prompt_tokens`, `completion_tokens`, `cached_tokens`), `finish_reason`,
`reply`, and `error` when the reply broke the protocol.

```
jq -c '[.turn, .items_before, .max_index, .items_after]' runs/*.jsonl
```

## Benchmark

`bench/run_swebench.py` runs knitback on SWE-bench Verified instances (`bench/tasks.json`) in their
Docker images, without network and with file tools confined to the repository, and judges them with
the official harness (swebench 4.1.0, `bench/.venv`). `bench/prune.py` measures go-backs and prunes.
Every run is pre-registered in `prereg/`; results and verdicts are in `bench/results*/README.md`.

## Development

```
.venv/bin/pytest -q && .venv/bin/ruff check . && .venv/bin/mypy knitback
```

The loop tests use a scripted fake model; `tests/fixtures/buggy/` is a small project with failing
tests for live runs.
