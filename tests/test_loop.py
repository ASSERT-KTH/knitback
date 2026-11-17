from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from agentknit import default_tool_spec

from selfctx._loop import run


class Scripted:
    """Fake OpenAI client replaying canned replies and recording the messages it got."""

    def __init__(self, replies: list[str]) -> None:
        self.replies = list(replies)
        self.calls: list[list[dict[str, str]]] = []
        self.kwargs: list[dict[str, Any]] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, model: str, messages: list[dict[str, str]], **kw: Any) -> Any:
        self.calls.append(messages)
        self.kwargs.append(kw)
        msg = SimpleNamespace(content=self.replies.pop(0))
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=None)


def _r(max_index: int, requests: list[dict[str, Any]] | None = None, done: str | None = None) -> str:
    return json.dumps({"thoughts": "", "max_index": max_index, "requests": requests or [], "done": done})


def _heads(messages: list[dict[str, str]]) -> list[str]:
    return [m["content"].split("\n", 1)[0] for m in messages[1:]]


@pytest.fixture
def tools() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    specs, disp = default_tool_spec()
    return [s for s in specs if s["function"]["name"] != "read_file"], disp


def _run(client: Scripted, tools: Any, tmp_path: Path, **kw: Any) -> Any:
    return run("task", client, "m", tools[0], tools[1], log_path=tmp_path / "log.jsonl", **kw)


def test_go_back_discards_items(tools: Any, tmp_path: Path) -> None:
    client = Scripted([
        _r(0, [{"tool": "exec_shell", "args": {"command": "echo a"}}]),
        _r(0, [{"tool": "exec_shell", "args": {"command": "echo b"}}]),
        _r(2, done="ok")])
    result = _run(client, tools, tmp_path)
    assert _heads(client.calls[1]) == ["[0] task", "[1] model_output", "[2] tool_result"]
    assert _heads(client.calls[2]) == ["[0] task", "[1] model_output", "[2] tool_result"]
    assert "echo b" in client.calls[2][3]["content"]
    assert result.final == "ok" and result.turns == 3


def test_kept_prefix_is_byte_identical(tools: Any, tmp_path: Path) -> None:
    client = Scripted([
        _r(0, [{"tool": "exec_shell", "args": {"command": "echo a"}}]),
        _r(2, [{"tool": "exec_shell", "args": {"command": "echo b"}}]),
        _r(1, done="ok")])
    _run(client, tools, tmp_path)
    assert client.calls[2][:4] == client.calls[1]


def test_requests_appended_in_listed_order(tools: Any, tmp_path: Path) -> None:
    (tmp_path / "f.txt").write_text("l1\nl2\nl3\n")
    client = Scripted([
        _r(0, [{"tool": "exec_shell", "args": {"command": "echo first"}},
               {"file": str(tmp_path / "f.txt"), "lines": [2, 3]},
               {"tool": "exec_shell", "args": {"command": "echo third"}}]),
        _r(0, done="ok")])
    _run(client, tools, tmp_path)
    contents = [m["content"] for m in client.calls[1][3:]]
    assert "first" in contents[0] and "third" in contents[2]
    assert contents[1].endswith("f.txt lines 2-3\n2\tl2\n3\tl3\n")


def test_file_request_allows_edit(tools: Any, tmp_path: Path) -> None:
    f = tmp_path / "g.py"
    f.write_text("x = 1\n")
    client = Scripted([
        _r(0, [{"file": str(f)}]),
        _r(2, [{"tool": "str_replace", "args": {"path": str(f), "old_str": "1", "new_str": "2"}}]),
        _r(0, done="ok")])
    _run(client, tools, tmp_path)
    assert f.read_text() == "x = 2\n"
    assert client.calls[2][-1]["content"].split("\n", 1)[0] == "[4] tool_result"


def test_invalid_max_index_becomes_error_item(tools: Any, tmp_path: Path) -> None:
    client = Scripted([_r(7), _r(2, done="ok")])
    result = _run(client, tools, tmp_path)
    assert _heads(client.calls[1]) == ["[0] task", "[1] model_output", "[2] error"]
    assert "out of range" in client.calls[1][3]["content"]
    assert result.final == "ok"


def test_failed_tool_becomes_error_item(tools: Any, tmp_path: Path) -> None:
    client = Scripted([_r(0, [{"file": str(tmp_path / "missing")}]), _r(0, done="ok")])
    _run(client, tools, tmp_path)
    assert _heads(client.calls[1])[-1] == "[2] error"


def test_max_turns_without_done(tools: Any, tmp_path: Path) -> None:
    result = _run(Scripted([_r(0)] * 3), tools, tmp_path, max_turns=3)
    assert result.final is None and result.turns == 3


def test_log_has_one_record_per_turn(tools: Any, tmp_path: Path) -> None:
    _run(Scripted([_r(0), _r(1), _r(-1, done="ok")]), tools, tmp_path)
    records = [json.loads(line) for line in (tmp_path / "log.jsonl").read_text().splitlines()]
    assert [(r["turn"], r["max_index"], r["items_before"], r["items_after"]) for r in records] == [
        (1, 0, 1, 2), (2, 1, 2, 3), (3, -1, 3, 1)]


def test_echoed_tag_is_stripped_from_stored_output(tools: Any, tmp_path: Path) -> None:
    client = Scripted(["[1] model_output\n[1] model_output\n" + _r(0), _r(1, done="ok")])
    _run(client, tools, tmp_path)
    assert client.calls[1][2]["content"] == "[1] model_output\n" + _r(0)


def test_turn_schema_sent_as_response_format(tools: Any, tmp_path: Path) -> None:
    client = Scripted([_r(0, done="ok")])
    _run(client, tools, tmp_path, request_params={"temperature": 1})
    kw = client.kwargs[0]
    assert kw["temperature"] == 1
    fmt = kw["extra_body"]["response_format"]
    assert fmt["type"] == "json_schema" and fmt["json_schema"]["strict"] is True


def test_no_schema_sends_no_response_format(tools: Any, tmp_path: Path) -> None:
    client = Scripted([_r(0, done="ok")])
    _run(client, tools, tmp_path, schema=False)
    assert "extra_body" not in client.kwargs[0]
