from __future__ import annotations

import json

import pytest

from selfctx._protocol import FileRequest, ProtocolError, ToolRequest, parse, system_prompt, turn_schema

TOOLS = {"exec_shell", "write_file"}


def _reply(**kw: object) -> str:
    return json.dumps({"thoughts": "t", "max_index": 0, "requests": [], "done": None} | kw)


def test_parses_requests_in_order() -> None:
    out = parse(_reply(max_index=2, requests=[
        {"tool": "exec_shell", "args": {"command": "ls"}},
        {"file": "a.py", "lines": [3, 9]},
        {"file": "b.py"}]), 3, TOOLS)
    assert out.max_index == 2
    assert out.requests == [ToolRequest("exec_shell", {"command": "ls"}),
                            FileRequest("a.py", (3, 9)), FileRequest("b.py", None)]


def test_json_surrounded_by_text_is_accepted() -> None:
    assert parse("[4] model_output\n" + _reply() + "\n", 1, TOOLS).max_index == 0


@pytest.mark.parametrize("max_index", [-1, 0, 4])
def test_max_index_in_range(max_index: int) -> None:
    assert parse(_reply(max_index=max_index), 5, TOOLS).max_index == max_index


@pytest.mark.parametrize("max_index", [-2, 5, "3", True, None])
def test_invalid_max_index_rejected(max_index: object) -> None:
    with pytest.raises(ProtocolError, match="max_index"):
        parse(_reply(max_index=max_index), 5, TOOLS)


@pytest.mark.parametrize("request_", [
    {"tool": "rm_rf"}, {"tool": "exec_shell", "args": "ls"}, {"file": "a", "lines": [5, 2]},
    {"file": "a", "lines": [0, 2]}, {"file": 3}, {"x": 1}, "ls"])
def test_invalid_request_rejected(request_: object) -> None:
    with pytest.raises(ProtocolError):
        parse(_reply(requests=[request_]), 1, TOOLS)


def test_not_json_rejected() -> None:
    with pytest.raises(ProtocolError, match="JSON"):
        parse("I will now run ls", 1, TOOLS)


def test_done() -> None:
    assert parse(_reply(done="fixed"), 1, TOOLS).done == "fixed"


def test_system_prompt_lists_tools() -> None:
    spec = [{"type": "function", "function": {"name": "exec_shell", "description": "run",
                                              "parameters": {"type": "object"}}}]
    assert '"name": "exec_shell"' in system_prompt(spec)


def test_turn_schema_lists_tools_and_requires_all_fields() -> None:
    js = turn_schema({"write_file", "exec_shell"})
    assert js["required"] == ["thoughts", "max_index", "requests", "done"]
    tool = js["properties"]["requests"]["items"]["anyOf"][1]
    assert tool["properties"]["tool"]["enum"] == ["exec_shell", "write_file"]


def test_schema_valid_reply_parses() -> None:
    reply = json.dumps({"thoughts": "", "max_index": 0, "done": None,
                        "requests": [{"file": "a", "lines": None}, {"tool": "exec_shell", "args": {}}]})
    assert parse(reply, 1, TOOLS).requests == [FileRequest("a", None), ToolRequest("exec_shell", {})]
