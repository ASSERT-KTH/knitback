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


def render(items: list[Item], system: str) -> list[dict[str, str]]:
    """Chat messages for `items`: one message per item, tagged `[index] kind`.

    One message per item keeps every kept prefix byte-identical across turns,
    so truncation never invalidates the provider's prompt cache before the cut.
    """
    messages = [{"role": "system", "content": system}]
    for index, item in enumerate(items):
        role = "assistant" if item.kind == "model_output" else "user"
        messages.append({"role": role, "content": f"[{index}] {item.kind}\n{item.content}"})
    return messages


def apply(items: list[Item], max_index: int, output: Item, new: list[Item]) -> list[Item]:
    """Next context: items `0..max_index` (inclusive), the model output, then `new` in order."""
    return items[: max_index + 1] + [output] + new
