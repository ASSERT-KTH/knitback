"""The turn protocol: system prompt and parsing of the model output."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


class ProtocolError(ValueError):
    """The model output does not follow the protocol; the message is shown to the model."""


@dataclass(frozen=True)
class FileRequest:
    path: str
    lines: tuple[int, int] | None  # 1-based, inclusive; None = agentknit's default read


@dataclass(frozen=True)
class ToolRequest:
    tool: str
    args: dict[str, Any] = field(default_factory=dict)


Request = FileRequest | ToolRequest


@dataclass(frozen=True)
class Output:
    thoughts: str
    max_index: int
    requests: list[Request]
    done: str | None


SYSTEM_PROMPT = """\
You are a coding agent that maintains its own context.

Your context is a sequence of items numbered from 0. Each item is shown as a message whose
first line is `[index] kind ~N tokens`; kind is one of task, model_output, file, tool_result, error.
Your own previous replies are the model_output items.

Each reply of yours is exactly one JSON object, nothing else:
{{"thoughts": "<your reasoning; when you cut, also the summary of what you drop>",
 "max_index": <int>,
 "requests": [ {{"file": "<path>", "lines": [<first>, <last>]}},
               {{"tool": "<name>", "args": {{...}}}} ],
 "done": null}}

At the next turn your context is:
1. items 0..max_index (inclusive); every later item is discarded for good.
   Set max_index to the last item you still need, or the highest index to keep everything,
   or -1 to drop everything (including the task).
2. this reply of yours, as one model_output item;
3. one new item per request, in the order you list them. You control this order.

A file request appends an excerpt of the file, 1-based line numbers, both ends included
("lines": null gives the first 100 lines). It also counts as reading the file,
which write_file and str_replace require for existing files.
A tool request runs the tool and appends its result.

Your context has a cost: every kept token is re-read at every turn, and a long context dilutes
your attention. The last message of each turn, `[context] K items, ~T tokens (budget ~B tokens)`,
shows its current size. Stay near the budget.

Going back is not only for undoing mistakes; use it to compact. Your "thoughts" are your summary:
the reply that cuts is written while you still see the items it drops, and it is kept right after
the cut, so its thoughts are all that remains of them. Once exploration (file excerpts, search
results, test output) has served its purpose, write what you still need in "thoughts" (file paths,
line numbers, exact strings to edit, findings, the plan) and set max_index to the last item before
that exploration. The conclusions survive and the raw material is gone.
A dropped item cannot be fetched back. A file excerpt can be requested again (exact text, as long
as the file is unchanged); a command can be run again, at its cost and with its side effects.
So copy into "thoughts" whatever you cannot cheaply regenerate: error messages, test failures,
outputs of slow commands. Anything you need later must be in a kept item.

When the task is finished, set "done" to your final answer for the user; requests are then ignored.

Tools:
{tools}
"""


def system_prompt(tool_specs: list[dict[str, Any]]) -> str:
    """Constant across turns, so it never breaks the prompt-cache prefix."""
    tools = "\n".join(
        json.dumps({"name": t["function"]["name"], "description": t["function"]["description"],
                    "parameters": t["function"]["parameters"]})
        for t in tool_specs)
    return SYSTEM_PROMPT.format(tools=tools)


def _json_object(reply: str) -> dict[str, Any]:
    start, end = reply.find("{"), reply.rfind("}")
    if start < 0 or end < start:
        raise ProtocolError("no JSON object found in your reply")
    try:
        data = json.loads(reply[start:end + 1])
    except json.JSONDecodeError as exc:
        raise ProtocolError(f"invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ProtocolError("the reply must be a JSON object")
    return data


def _request(raw: Any, tools: set[str]) -> Request:
    if not isinstance(raw, dict):
        raise ProtocolError(f"request {raw!r} is not an object")
    if "file" in raw:
        path, lines = raw["file"], raw.get("lines")
        if not isinstance(path, str):
            raise ProtocolError(f"file request {raw!r}: file must be a string")
        if lines is None:
            return FileRequest(path, None)
        if (not isinstance(lines, list) or len(lines) != 2
                or not all(isinstance(n, int) and not isinstance(n, bool) for n in lines)
                or not 1 <= lines[0] <= lines[1]):
            raise ProtocolError(f"file request {raw!r}: lines must be [first, last] with 1 <= first <= last")
        return FileRequest(path, (lines[0], lines[1]))
    if "tool" in raw:
        name, args = raw["tool"], raw.get("args", {})
        if name not in tools:
            raise ProtocolError(f"unknown tool {name!r}; available: {', '.join(sorted(tools))}")
        if not isinstance(args, dict):
            raise ProtocolError(f"tool request {raw!r}: args must be an object")
        return ToolRequest(name, args)
    raise ProtocolError(f"request {raw!r} has neither 'file' nor 'tool'")


def parse(reply: str, n_items: int, tools: set[str]) -> Output:
    """Parse and validate a reply, given the current number of items and the tool names."""
    data = _json_object(reply)
    max_index = data.get("max_index")
    if not isinstance(max_index, int) or isinstance(max_index, bool):
        raise ProtocolError("max_index must be an integer")
    if not -1 <= max_index <= n_items - 1:
        raise ProtocolError(f"max_index {max_index} is out of range [-1, {n_items - 1}]")
    raw_requests = data.get("requests", [])
    if not isinstance(raw_requests, list):
        raise ProtocolError("requests must be a list")
    done = data.get("done")
    if done is not None and not isinstance(done, str):
        raise ProtocolError("done must be null or a string")
    thoughts = data.get("thoughts", "")
    return Output(thoughts if isinstance(thoughts, str) else json.dumps(thoughts), max_index,
                  [_request(r, tools) for r in raw_requests], done)


def _tool_branch(spec: dict[str, Any]) -> dict[str, Any]:
    """Schema of one tool request: the tool name as a constant, its own parameters, nothing else."""
    params = spec["function"]["parameters"]
    args = {**params, "additionalProperties": False}
    return {"type": "object", "additionalProperties": False, "required": ["tool", "args"],
            "properties": {"tool": {"type": "string", "const": spec["function"]["name"]}, "args": args}}


def turn_schema(tool_specs: list[dict[str, Any]]) -> dict[str, Any]:
    """JSON schema of one model output, for `response_format: json_schema`.

    Endpoints may only follow it as an instruction (Kimi does), so `parse` and `check_args` still validate.
    """
    file_request = {"type": "object", "additionalProperties": False, "required": ["file", "lines"],
                    "properties": {"file": {"type": "string"},
                                   "lines": {"type": ["array", "null"], "minItems": 2, "maxItems": 2,
                                             "items": {"type": "integer", "minimum": 1}}}}
    return {"type": "object", "additionalProperties": False,
            "required": ["thoughts", "max_index", "requests", "done"],
            "properties": {"thoughts": {"type": "string"},
                           "max_index": {"type": "integer", "minimum": -1},
                           "requests": {"type": "array", "items": {
                               "anyOf": [file_request] + [_tool_branch(t) for t in tool_specs]}},
                           "done": {"type": ["string", "null"]}}}


def response_format(tool_specs: list[dict[str, Any]]) -> dict[str, Any]:
    """The `response_format` request field carrying `turn_schema`; constant across turns."""
    return {"type": "json_schema",
            "json_schema": {"name": "turn", "strict": True, "schema": turn_schema(tool_specs)}}


def check_args(spec: dict[str, Any], args: dict[str, Any]) -> str | None:
    """Why `args` do not fit the tool's parameters (unknown or missing keys), or None if they do."""
    params = spec["function"]["parameters"]
    known, required = set(params.get("properties", {})), set(params.get("required", []))
    problems = []
    if unknown := sorted(set(args) - known):
        problems.append(f"unknown argument(s) {', '.join(unknown)}")
    if missing := sorted(required - set(args)):
        problems.append(f"missing argument(s) {', '.join(missing)}")
    if not problems:
        return None
    return f"{'; '.join(problems)}. {spec['function']['name']} takes: {', '.join(sorted(known))}" + (
        f" (required: {', '.join(sorted(required))})" if required else "")
