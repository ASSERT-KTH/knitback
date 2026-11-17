# Does Kimi K3.1 Pro (kimi-coding) support constrained decoding?

Probed 2026-11-17 against `https://api.kimi.com/coding/v1`, model `k3.1-pro`, `temperature=1`.
Run any probe with `../../.venv/bin/python probeN.py [trials]`; results are the committed `*-results.jsonl`.

## Verdict

The endpoint accepts JSON-schema-shaped output requests, but does not enforce them by masking:
a schema `pattern` is violated even with `strict: true`. There is no grammar support.

## Evidence

- `response_format`: only `text`, `json_object`, `json_schema` are accepted (HTTP 400 otherwise, probe 1).
- OpenAI custom tools with a Lark grammar: rejected, "only function and plugin are supported" (probe 1).
- `json_schema` (strict or not) and a forced strict function: schema-valid 3/3 against adversarial
  prompts asking for a wrong type, a forbidden enum value, a non-matching string, an unknown tool (probe 2).
  The model's `thoughts` cite "the required schema": the schema reaches the model as text, so this
  is compatible with plain instruction following.
- Discriminating test, pattern `^(ab){29}c$` (probe 3): valid 1/5 without a schema, 3/5 with strict
  `json_schema`, 2/5 with a strict function; invalid outputs have length 59 or 61. A masking decoder
  cannot emit them.
- Exact array length via `minItems = maxItems = 37` (probe 4) and `^x{73}$` (probe 3): 5/5 in every
  mode including the unconstrained control, so these do not discriminate; structural enforcement
  (keys, types, enums, item counts) is undetermined.

## Implication for selfctx

`json_schema` (or a forced function) lowers protocol errors but cannot replace `parse` validation.
Guaranteed-valid output needs an endpoint with real constrained decoding.
