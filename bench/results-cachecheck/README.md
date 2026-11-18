# Cache check: real Kimi cache hits on two pruning tasks

2026-11-18, run-3 prompt and budget (20 000), code at db8bcc8 (as in run 3, plus the `cached_tokens` logging
fix; runs 2 and 3 logged it as null). Not pre-registered: an instrument check, not a comparison.

- pytest-dev__pytest-10356: resolved, 10 turns, prompt 89 821 tokens, cached 68 352 (76 %).
- sympy__sympy-14248: not resolved, 81 turns, prompt 917 492 tokens, cached 590 134 (64 %),
  uncached 327 358.

## The cache behaves as the design assumes
- Kimi caches in 256-token blocks (every partial hit is a multiple of 256).
- After a turn without a cut, the next request is served from cache except ~570 tokens
  (median over 49 turns; range 495-678): the trailing status message plus block rounding.
  Appending and keeping a stable prefix is nearly free.
- After a cut to item k, the next hit falls to the prefix 0..k: 768-1 024 tokens after a cut to the
  task, i.e. system prompt plus task.

## The model's cuts ignore the cache
sympy shows a saw-tooth: the context grows to ~18-23k prompt tokens (the 20k budget), then the model
cuts back to 3-8 items (turns 9, 21, 32, 38, 54, 62, 79 drop 25-38 items), and rebuilds by
re-requesting files and re-running commands, all uncached. The cache hit ratio follows the same
saw-tooth (16-30 % after a deep cut, ~90 % just before it).

Cause: the model optimises the only cost it is shown, the token count against the budget. Nothing
tells it that a cut at k makes everything after k uncached, nor that its summaries, being written
after the material they summarise, must themselves be cut at the next compaction.
