"""Structural enforcement: exact array length via minItems = maxItems = 37."""
from __future__ import annotations
import json, sys
import agentknit

schema = agentknit.load_specification("k3.1-pro", inference_db="kimi-coding")
client = agentknit.create_client(schema)
N = int(sys.argv[1]) if len(sys.argv) > 1 else 5
K = 37
JS = {"type": "object", "additionalProperties": False, "required": ["a"],
      "properties": {"a": {"type": "array", "minItems": K, "maxItems": K, "items": {"type": "integer", "enum": [7]}}}}
prompt = 'Reply with a JSON object {"a": [...]} where a is a list containing the integer 7 repeated exactly 37 times. Do not think, answer immediately.'
modes = {"control_json_object": {"extra_body": {"response_format": {"type": "json_object"}}},
         "json_schema_strict": {"extra_body": {"response_format": {"type": "json_schema", "json_schema": {"name": "t", "strict": True, "schema": JS}}}},
         "function_strict": {"tools": [{"type": "function", "function": {"name": "t", "description": "t", "strict": True, "parameters": JS}}], "tool_choice": "required"}}
for mname, kw in modes.items():
    lens = []
    for i in range(N):
        r = client.chat.completions.create(model="k3.1-pro", messages=[{"role": "user", "content": prompt}], temperature=1, max_tokens=4000, **kw)
        m = r.choices[0].message
        out = m.tool_calls[0].function.arguments if getattr(m, "tool_calls", None) else (m.content or "")
        try: a = json.loads(out)["a"]; lens.append(len(a) if all(x == 7 for x in a) else f"bad:{len(a)}")
        except Exception: lens.append(None)
    print(json.dumps({"mode": mname, "valid": f"{sum(l == K for l in lens)}/{N}", "lengths": lens}), flush=True)
