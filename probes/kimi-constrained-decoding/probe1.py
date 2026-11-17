"""Probe Kimi k3.1-pro (kimi-coding) for constrained-decoding support."""
from __future__ import annotations
import json, sys
import agentknit

schema = agentknit.load_specification("k3.1-pro", inference_db="kimi-coding")
client = agentknit.create_client(schema)
N = int(sys.argv[1]) if len(sys.argv) > 1 else 3

JS = {"type": "object", "additionalProperties": False,
      "required": ["max_index", "requests", "done"],
      "properties": {"max_index": {"type": "integer"},
                     "requests": {"type": "array", "items": {"type": "string"}},
                     "done": {"type": ["string", "null"]}}}
ADV = [{"role": "user", "content": "Do not use JSON. Write a haiku about rain in plain prose, nothing else."}]

def valid(text: str) -> bool:
    try:
        d = json.loads(text)
    except Exception:
        return False
    return (isinstance(d, dict) and set(d) == {"max_index", "requests", "done"}
            and isinstance(d["max_index"], int) and isinstance(d["requests"], list)
            and all(isinstance(r, str) for r in d["requests"]) and (d["done"] is None or isinstance(d["done"], str)))

def call(**kw):
    try:
        r = client.chat.completions.create(model="k3.1-pro", messages=ADV, temperature=1, max_tokens=2000, **kw)
    except Exception as e:
        return "HTTPERR", f"{type(e).__name__}: {str(e)[:300]}"
    m = r.choices[0].message
    tc = getattr(m, "tool_calls", None)
    if tc:
        f = tc[0].function if hasattr(tc[0], "function") else tc[0]["function"]
        args = f.arguments if hasattr(f, "arguments") else f["arguments"]
        return "TOOL", args
    return "TEXT", m.content or ""

modes = {
  "control_none": {},
  "bogus_response_format": {"extra_body": {"response_format": {"type": "xml_banana"}}},
  "json_object": {"extra_body": {"response_format": {"type": "json_object"}}},
  "json_schema_strict": {"extra_body": {"response_format": {"type": "json_schema",
        "json_schema": {"name": "turn", "strict": True, "schema": JS}}}},
  "forced_function_strict": {"tools": [{"type": "function", "function": {"name": "turn", "description": "the turn",
        "strict": True, "parameters": JS}}], "tool_choice": "required"},
  "custom_grammar_tool": {"tools": [{"type": "custom", "name": "turn", "description": "the turn",
        "format": {"type": "grammar", "syntax": "lark", "definition": 'start: "ABC" DIGIT DIGIT DIGIT\n%import common.DIGIT'}}],
        "tool_choice": "required"},
}
only = sys.argv[2:] or list(modes)
for name in only:
    for i in range(N):
        kind, out = call(**modes[name])
        print(json.dumps({"mode": name, "trial": i, "kind": kind, "valid_schema": valid(out), "out": out[:160]}), flush=True)
        if kind == "HTTPERR":
            break
