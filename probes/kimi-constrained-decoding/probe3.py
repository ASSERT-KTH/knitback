"""Masking vs instruction-following: exact-count constraints that LLMs miscount on their own."""
from __future__ import annotations
import json, re, sys
import agentknit

schema = agentknit.load_specification("k3.1-pro", inference_db="kimi-coding")
client = agentknit.create_client(schema)
N = int(sys.argv[1]) if len(sys.argv) > 1 else 5

CASES = {
  "x73": ("^x{73}$", "a string made of exactly 73 lowercase letters x and nothing else"),
  "ab29c": ("^(ab){29}c$", "the string 'ab' repeated exactly 29 times followed by one 'c'"),
}
def js(pat): return {"type": "object", "additionalProperties": False, "required": ["s"], "properties": {"s": {"type": "string", "pattern": pat}}}
for cname, (pat, desc) in CASES.items():
    prompt = f'Reply with a JSON object {{"s": ...}} where s is {desc}. Do not think, answer immediately.'
    modes = {"control_json_object": {"extra_body": {"response_format": {"type": "json_object"}}},
             "json_schema_strict": {"extra_body": {"response_format": {"type": "json_schema", "json_schema": {"name": "t", "strict": True, "schema": js(pat)}}}},
             "function_strict": {"tools": [{"type": "function", "function": {"name": "t", "description": "t", "strict": True, "parameters": js(pat)}}], "tool_choice": "required"}}
    for mname, kw in modes.items():
        ok = 0
        lens = []
        for i in range(N):
            r = client.chat.completions.create(model="k3.1-pro", messages=[{"role": "user", "content": prompt}], temperature=1, max_tokens=4000, **kw)
            m = r.choices[0].message
            out = m.tool_calls[0].function.arguments if getattr(m, "tool_calls", None) else (m.content or "")
            try: s = json.loads(out)["s"]
            except Exception: s = None
            good = isinstance(s, str) and re.fullmatch(pat.strip("^$"), s) is not None
            ok += good; lens.append(len(s) if isinstance(s, str) else None)
        print(json.dumps({"case": cname, "mode": mname, "valid": f"{ok}/{N}", "lengths": lens}), flush=True)
