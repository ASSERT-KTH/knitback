## Goal

Design and implement a coding agent with a radically different loop:
the model is aware of its own context and maintains it itself.

## Context model

- The context is a sequence of items, indexed from 0.
- Items are only ever appended or truncated, never edited in place,
  so every turn's prompt shares a prefix with the previous one (prompt-cache friendly).

## Turn protocol

At each turn, the model outputs:

1. `max_index`: the last item (inclusive) kept for the next turn.
   Items after it are discarded, which lets the model go "back" in context
   and drop recent additions it no longer needs.
2. `files`: file excerpts to append at the next turn, each as a path plus line range.
3. `tool_calls`: tool calls to execute; their results are appended at the next turn.

The next turn's context is items `0..max_index`, followed by the new items
produced by step 2 and step 3.
