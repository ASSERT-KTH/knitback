# Prior art

## The model manages its own context

- [Focus: Active Context Compression](https://arxiv.org/abs/2601.07190) (2026). The agent decides when
  to fold learnings into a persistent "Knowledge" block and drop raw history; reports that capable
  models self-regulate context with the right tools and prompting. Closest to knitback's
  summarise-then-cut, observed in run 3. Single-author preprint.
- [Scaling Long-Horizon LLM Agent via Context-Folding](https://arxiv.org/abs/2510.11967) (ByteDance Seed,
  CMU, Stanford, 2025; [project page](https://context-folding.github.io/)). Actions *branch* into a
  sub-trajectory and *return* it folded into a short summary; trained with RL (FoldGRPO); SWE and deep
  research tasks. knitback's compaction is an untrained, single-level form of this.
- [Self-GC: Self-Governing Context for Long-Horizon LLM Agents](https://arxiv.org/abs/2607.00692)
  (Xiaohongshu, 2026; [summary](https://www.deeplearning.ai/the-batch/llms-take-out-the-agents-trash)).
  Context items are addressable objects with fold, mask and prune operations, decided by a separate
  planner model rather than the acting model.
- [Beyond Compaction: Structured Context Eviction](https://arxiv.org/abs/2606.11213) (2026). The agent
  tags its trajectory as typed episodes; a deterministic policy evicts them when over budget.
- [MemGPT: Towards LLMs as Operating Systems](https://arxiv.org/abs/2310.08560) (2023), now
  [Letta](https://docs.letta.com/letta_memgpt). The LLM moves information between its context and
  external storage with memory tools. Conceptual ancestor, with external memory instead of prefix
  truncation.

## Going back: rewind and backtracking

- [Langroid `rewind_tool`](https://langroid.github.io/langroid/reference/agent/tools/rewind_tool).
  The LLM backtracks to its nth previous message and replaces it. Nearest equivalent of `max_index`,
  as an occasional tool rather than a per-turn field.
- [AgentRewind](https://www.alphaxiv.org/abs/2608.14380) (2026). The agent calls a rewind tool when
  stuck; reports that keeping failed attempts in context lowers success. Matches run 2, where going
  back was used only to undo failed calls.
- [Google ADK rewind](https://adk.iqai.com/docs/framework/runtime/rewind) and Claude Code's
  `/rewind`: checkpoint rollback triggered by the runtime or the user, not chosen by the model.

## Caching awareness

- [Don't Break the Cache: An Evaluation of Prompt Caching](https://arxiv.org/abs/2601.06007) (2026).
  Prompt caching cuts agent API cost by 45-80%; changing tool results can cause cache writes that are
  never reused. Supports the stable-prefix, changing-tail layout.
- [Inside the Scaffold: A Source-Code Taxonomy of Coding Agent Architectures](https://arxiv.org/abs/2604.03515)
  (2026). Reports that SWE-agent truncates observations only every N steps so that the cached prefix
  survives: the only cache-aware truncation in a coding agent found.
- [KVTether](https://arxiv.org/abs/2609.39819) (2026). Lifecycle-aware KV-cache management for ReAct
  agents, reclaiming discarded entries: the same concern on the serving side.
- [Anthropic context editing](https://docs.claude.com/en/docs/build-with-claude/context-editing).
  The API clears old tool results past a threshold and leaves placeholders: an edit in the middle
  of the context, which knitback avoids for cache reasons.

- [TokenPilot: Cache-Efficient Context Management for LLM Agents](https://arxiv.org/abs/2606.17016)
  (2026). Replaces volatile runtime values with stable placeholders and moves tool definitions
  downstream so the prompt prefix is byte-identical from the first turn, then evicts by lifecycle.
  The closest harness-side relative of knitback's append-or-truncate layout; the harness decides,
  not the model.
- [CliffCompaction: Cost-Efficient Compaction for Long-Horizon Coding Agents](https://arxiv.org/abs/2609.26779)
  (2026). Argues the cache cost of compaction is modest because the compacted context is small and
  compaction rare. knitback's measured saw-tooth (`bench/results-cachecheck/README.md`: compaction
  every 6-15 turns, each followed by an uncached rebuild) is a counter-case.
- [Cache-Aware Prompt Compression: A Two-Tier Cost Model for LLM API Caching](https://arxiv.org/abs/2607.15516)
  (2026). Prices cached and uncached input separately: the cost model a cache cue to the model
  would have to convey.
- [OpenAI prompt caching guide](https://developers.openai.com/api/docs/guides/prompt-caching).
  Compaction prevents reuse from the first changed token onward; writing a prefix once and reusing
  it once costs 1.35x its input price, against 2x for processing it twice.
- ObsDrop ([preprint](https://www.researchsquare.com/article/rs-11684582)). Drops stale tool
  observations from the serving engine's KV cache while the logical prefix stays unchanged: a
  serving-side option, unavailable through a hosted API.
- [Prompt Caching: Architectural Discipline for Agents](https://www.agentpatterns.ai/context-engineering/prompt-caching-architectural-discipline/)
  (practitioner guide). Cache-safe compaction keeps the identical prefix and appends the summary as
  a new message. In knitback terms: cut late and let the summary sit on a stable prefix, which the
  model did not do unprompted.

## Cost cues shown to the model

No work found shows the model its own cache hits or tells it that a cut makes everything after it
uncached: cache awareness lives in the harness or the serving engine. The nearest work shows the
model a resource count.

- [Budget-Aware Tool-Use Enables Effective Agent Scaling](https://arxiv.org/abs/2511.17006) (Google
  DeepMind, NYU, UCSB, 2025). Agents without budget awareness gain little from larger tool budgets;
  a Budget Tracker that shows the agent its remaining resources fixes it. Closest analogue of
  knitback's `[context] ... (budget ~B tokens)` status, with the same limit: the model optimises the
  cost it is shown, and knitback's status shows tokens, not cache.
- [INTENT](https://arxiv.org/abs/2602.11541) (2026). Forecasts tool costs with a learned world model
  to stay within an economic budget.
- [Token awareness](https://www.monperrus.net/martin/token-awareness), implemented in
  [agentknit](https://github.com/monperrus/agentknit). A true countdown of the token budget in the
  model's context: a count, not a cache cue.
