## Goal

Design and implement a coding agent with a radically different loop:
the model is aware of its own context and maintains it itself.

## Context model

- The context is a sequence of items, indexed from 0.
- One item is one file excerpt, one tool result, or one model output
  (its reasoning plus `max_index` and the request list).
- Every item is shown to the model with its index (e.g. a `[17]` tag),
  so the model knows what to keep.
- Items are only ever appended or truncated, never edited in place,
  so every turn's prompt shares a prefix with the previous one (prompt-cache friendly).
- No item is protected: the model may truncate down to and including the task description.

## Turn protocol

At each turn, the model outputs:

1. `max_index`: the last item (inclusive) kept for the next turn.
   Items after it are discarded, which lets the model go "back" in context
   and drop recent additions it no longer needs.
2. An ordered list of requests, each one either:
   - a file excerpt: a path plus line range, or
   - a tool call, whose result is the new item.

The next turn's context is items `0..max_index`, followed by the model output as one item,
then one new item per request, in the order the model listed them.
The prompt tells the model that it controls this order.

## Implementation

The MVP is built on agentknit (`~/workspace/prototypes/agentknit`),
which provides LLM endpoint access and tool execution.
agentknit runs in bare mode (no compaction, no token or time awareness):
the model alone manages its context.

The implementation is the `selfctx` package: `_items.py` (items, rendering, truncation),
`_protocol.py` (system prompt, output parsing), `_loop.py` (the turn loop), `__main__.py` (CLI).
The model output is plain JSON parsed from the reply; constrained decoding is required after the MVP.
Kimi K3.1 (kimi-coding) accepts `response_format: json_schema` but does not enforce it at decoding
(see `probes/kimi-constrained-decoding/`), so `parse` validation stays mandatory with it.
