"""Pruning measures for knitback run logs.

Usage: python bench/prune.py RESULTS_DIR [RESULTS_DIR ...]
Prints one JSON line per run: go-back turns, pruning turns (go-back dropping >= 5 items),
and, when the log has `new_items`, the estimated tokens dropped per go-back.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

PRUNE_MIN_ITEMS = 5


def tokens(text: str) -> int:
    return (len(text) + 3) // 4  # same estimate as knitback._items.tokens


def measure(log: Path) -> dict[str, object]:
    records = [json.loads(line) for line in log.read_text().splitlines()]
    sizes: list[int] | None = [0]  # item sizes, reconstructed when new_items is logged; task size unknown
    go_backs, prunes, dropped_tokens = [], [], []
    for r in records:
        before, max_index = r["items_before"], r.get("max_index")
        if max_index is None:  # protocol error: output and error item appended
            if sizes is not None:
                sizes += [tokens(r["reply"]), 0]
            continue
        dropped = before - 1 - max_index
        if dropped > 0:
            go_backs.append([r["turn"], dropped])
            if dropped >= PRUNE_MIN_ITEMS:
                prunes.append(r["turn"])
            if sizes is not None:
                dropped_tokens.append([r["turn"], sum(sizes[max_index + 1:])])
        if sizes is not None:
            if "new_items" in r:
                sizes = sizes[: max_index + 1] + [tokens(r["reply"])] + [n for _, n in r["new_items"]]
            elif r.get("items_after") != max_index + 2:  # no new_items: sizes cannot be tracked
                sizes = None
    prompts = [r["usage"]["prompt_tokens"] for r in records if (r.get("usage") or {}).get("prompt_tokens")]
    return {"run": log.parent.name, "turns": len(records), "go_backs": go_backs, "prune_turns": prunes,
            "dropped_tokens": dropped_tokens if sizes is not None else None,
            "peak_prompt_tokens": max(prompts, default=None),
            "median_prompt_tokens": statistics.median(prompts) if prompts else None}


def main() -> int:
    for d in sys.argv[1:]:
        for log in sorted(Path(d).glob("*/run.jsonl")):
            print(json.dumps(measure(log)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
