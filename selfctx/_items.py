"""Context items: the indexed sequence the model sees and maintains."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Kind = Literal["task", "model_output", "file", "tool_result", "error"]


@dataclass(frozen=True)
class Item:
    """One context item; its index is its position in the sequence."""

    kind: Kind
    content: str


def tokens(text: str) -> int:
    """Rough token estimate (4 characters per token): a relative signal, not a tokenizer."""
    return (len(text) + 3) // 4


def header(index: int, item: Item) -> str:
    return f"[{index}] {item.kind} ~{tokens(item.content)} tokens"


def render(items: list[Item], system: str, budget: int | None = None) -> list[dict[str, str]]:
    """Chat messages for `items`: one message per item, headed `[index] kind ~N tokens`.

    One message per item keeps every kept prefix byte-identical across turns,
    so truncation never invalidates the provider's prompt cache before the cut.
    A final status message (not an item) gives the context size; being last,
    it is the only part that changes from turn to turn.
    """
    messages = [{"role": "system", "content": system}]
    for index, item in enumerate(items):
        role = "assistant" if item.kind == "model_output" else "user"
        messages.append({"role": role, "content": f"{header(index, item)}\n{item.content}"})
    total = sum(tokens(item.content) for item in items)
    status = f"[context] {len(items)} items, ~{total} tokens"
    if budget is not None:
        status += f" (budget ~{budget} tokens)"
    messages.append({"role": "user", "content": status})
    return messages


def apply(items: list[Item], max_index: int, output: Item, new: list[Item]) -> list[Item]:
    """Next context: items `0..max_index` (inclusive), the model output, then `new` in order."""
    return items[: max_index + 1] + [output] + new
