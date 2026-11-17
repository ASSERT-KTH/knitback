# selfctx

A coding agent whose model maintains its own context.
The context is a sequence of numbered items; each turn the model says which prefix to keep
(`max_index`), and which file excerpts and tool results to append, in which order.
The protocol is specified in `AGENTS.md`.

## Install

```
uv venv .venv && uv pip install -p .venv -e '.[dev]'
```

agentknit is an editable path dependency (`../agentknit`), and supplies the model client and the
tools (`write_file`, `str_replace`, `exec_shell`; files are read through file requests).

## Usage

```
selfctx "make the tests pass"            # prints the final answer
selfctx --json "make the tests pass"     # {"final", "turns", "items", "log"}
echo "task" | selfctx
selfctx --model k3.1-pro --inference-db kimi-coding --max-turns 50 --log-dir runs "task"
```

Defaults: Kimi K3.1 Pro through the agentknit inference-db entry `kimi-coding`.
Exit code 0 when the model sets `done`, 1 after `--max-turns` without an answer, 2 on an empty task.
Tool output is streamed to stderr; stdout carries only the answer.

Each run writes `runs/<timestamp>.jsonl`, one record per turn:
`turn`, `items_before`, `max_index`, `items_after`, `usage`, `finish_reason`, `reply`, and `error`
when the reply broke the protocol.

```
jq -c '[.turn, .items_before, .max_index, .items_after]' runs/*.jsonl
```

## Development

```
.venv/bin/pytest -q && .venv/bin/ruff check . && .venv/bin/mypy selfctx
```

The loop tests use a scripted fake model; `tests/fixtures/buggy/` is a small project with failing
tests for live runs.
