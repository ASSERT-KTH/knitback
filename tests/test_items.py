from __future__ import annotations

from knitback._items import Item, apply, render


def _ctx() -> list[Item]:
    return [Item("task", "fix it"), Item("model_output", '{"max_index": 0}'), Item("tool_result", "ls output")]


def test_render_tags_each_item_with_its_index_and_kind() -> None:
    msgs = render(_ctx(), "SYS")
    assert msgs[0] == {"role": "system", "content": "SYS"}
    assert [m["content"].split("\n", 1)[0] for m in msgs[1:-1]] == [
        "[0] task ~2 tokens", "[1] model_output ~4 tokens", "[2] tool_result ~3 tokens"]


def test_model_output_is_assistant_everything_else_user() -> None:
    assert [m["role"] for m in render(_ctx(), "S")[1:-1]] == ["user", "assistant", "user"]


def test_truncate_then_append_keeps_prefix() -> None:
    items = _ctx()
    out = Item("model_output", "o")
    new = apply(items, 0, out, [Item("file", "f")])
    assert new[:1] == items[:1]
    assert render(new, "S")[:2] == render(items, "S")[:2]


def test_status_message_is_last_and_reports_size_and_budget() -> None:
    msgs = render(_ctx(), "S", budget=20000)
    assert msgs[-1] == {"role": "user", "content": "[context] 3 items, ~9 tokens (budget ~20000 tokens)"}
    assert render(_ctx(), "S")[-1]["content"] == "[context] 3 items, ~9 tokens"


def test_requests_appended_in_listed_order() -> None:
    a, b, c = Item("tool_result", "a"), Item("file", "b"), Item("tool_result", "c")
    out = Item("model_output", "o")
    assert apply(_ctx(), 2, out, [a, b, c])[3:] == [out, a, b, c]


def test_max_index_minus_one_drops_everything() -> None:
    out = Item("model_output", "o")
    assert apply(_ctx(), -1, out, []) == [out]


def test_apply_does_not_mutate_input() -> None:
    items = _ctx()
    apply(items, 0, Item("model_output", "o"), [])
    assert len(items) == 3
