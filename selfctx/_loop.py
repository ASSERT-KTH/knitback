"""The agent loop: the model rewrites its own context each turn."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from agentknit import dispatch

from ._items import Item, apply, render
from ._protocol import FileRequest, ProtocolError, Request, parse, system_prompt

_ECHOED_TAGS = re.compile(r"\A\s*(?:\[\d+\] \w+\s*\n)+")
_ENVELOPE = re.compile(r"\A<[0-9a-f]{8}[^>]*>\n?(.*?)</[0-9a-f]{8}>\s*\Z", re.DOTALL)


class Client(Protocol):
    """The subset of an OpenAI-compatible client the loop uses."""

    @property
    def chat(self) -> Any: ...


@dataclass
class Result:
    final: str | None
    items: list[Item]
    turns: int


def _read(req: FileRequest, tool_dispatch: dict[str, Any]) -> Item:
    args: dict[str, Any] = {"path": req.path}
    if req.lines:
        args |= {"offset": req.lines[0], "limit": req.lines[1] - req.lines[0] + 1}
    text, meta = dispatch("read_file", args, tool_dispatch)
    if meta.get("ok") is False:
        return Item("error", f"file {req.path}: {text}")
    match = _ENVELOPE.match(text)
    body = match.group(1) if match else text
    first = req.lines[0] if req.lines else 1
    numbered = "".join(f"{n}\t{line}" for n, line in enumerate(body.splitlines(keepends=True), first))
    last = first + max(0, len(body.splitlines()) - 1)
    return Item("file", f"{req.path} lines {first}-{last}\n{numbered}")


def _execute(req: Request, tool_dispatch: dict[str, Any]) -> Item:
    if isinstance(req, FileRequest):
        return _read(req, tool_dispatch)
    text, meta = dispatch(req.tool, req.args, tool_dispatch)
    header = f"{req.tool} {json.dumps(req.args)[:200]}"
    return Item("error" if meta.get("ok") is False else "tool_result", f"{header}\n{text}")


def _usage(response: Any) -> dict[str, Any] | None:
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    details = getattr(usage, "prompt_tokens_details", None)
    return {"prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
            "cached_tokens": getattr(details, "cached_tokens", None) if details else None}


def run(task: str, client: Client, model: str, tool_specs: list[dict[str, Any]],
        tool_dispatch: dict[str, Any], *, request_params: dict[str, Any] | None = None,
        max_turns: int = 50, log_path: Path | None = None) -> Result:
    """Run `task` until the model sets `done` or `max_turns` is reached."""
    tools = {t["function"]["name"] for t in tool_specs}
    system = system_prompt(tool_specs)
    items = [Item("task", task)]
    log = log_path.open("a") if log_path else None
    try:
        for turn in range(1, max_turns + 1):
            response = client.chat.completions.create(
                model=model, messages=render(items, system), **(request_params or {}))
            # Models imitate the `[i] kind` header of past outputs; the host adds it, so drop the echo.
            reply = _ECHOED_TAGS.sub("", response.choices[0].message.content or "")
            record: dict[str, Any] = {"turn": turn, "items_before": len(items),
                                      "usage": _usage(response),
                                      "finish_reason": getattr(response.choices[0], "finish_reason", None),
                                      "reply": reply}
            try:
                out = parse(reply, len(items), tools)
            except ProtocolError as exc:
                items = items + [Item("model_output", reply), Item("error", f"protocol error: {exc}")]
                record |= {"max_index": None, "error": str(exc)}
            else:
                record["max_index"] = out.max_index
                if out.done is not None:
                    items = apply(items, out.max_index, Item("model_output", reply), [])
                    record["items_after"] = len(items)
                    if log:
                        log.write(json.dumps(record) + "\n")
                    return Result(out.done, items, turn)
                new = [_execute(r, tool_dispatch) for r in out.requests]
                items = apply(items, out.max_index, Item("model_output", reply), new)
            record["items_after"] = len(items)
            if log:
                log.write(json.dumps(record) + "\n")
                log.flush()
        return Result(None, items, max_turns)
    finally:
        if log:
            log.close()
