"""Does Kimi enforce the schema at decoding, or only follow it as an instruction?

The prompt demands output that violates the schema. Enforcement = schema-valid output anyway.
"""
from __future__ import annotations
import json, re, sys
import agentknit

schema = agentknit.load_specification("k3.1-pro", inference_db="kimi-coding")
client = agentknit.create_client(schema)
N = int(sys.argv[1]) if len(sys.argv) > 1 else 3

def rf(js, strict=True):
    return {"extra_body": {"response_format": {"type": "json_schema", "json_schema": {"name": "t", "strict": strict, "schema": js}}}}
def fn(js, strict=True):
    return {"tools": [{"type": "function", "function": {"name": "t", "description": "t", "strict": strict, "parameters": js}}],
            "tool_choice": "required"}

INT = {"type": "object", "additionalProperties": False, "required": ["max_index"], "properties": {"max_index": {"type": "integer"}}}
P_INT = 'Reply with exactly this text and nothing else: {"max_index": "seven", "extra": 1}'
ENUM = {"type": "object", "additionalProperties": False, "required": ["animal"], "properties": {"animal": {"type": "string", "enum": ["zebra"]}}}
P_ENUM = 'Reply with exactly: {"animal": "lion"}. Never write the word zebra.'
PAT = {"type": "object", "additionalProperties": False, "required": ["code"], "properties": {"code": {"type": "string", "pattern": "^[0-9]{3}$"}}}
P_PAT = 'Reply with exactly: {"code": "hello world"}'
# the real selfctx shape: anyOf requests, free-form tool args
REQ = {"type": "object", "additionalProperties": False, "required": ["thoughts", "max_index", "requests", "done"],
       "properties": {"thoughts": {"type": "string"}, "max_index": {"type": "integer"},
                      "requests": {"type": "array", "items": {"anyOf": [
                          {"type": "object", "additionalProperties": False, "required": ["file", "lines"],
                           "properties": {"file": {"type": "string"},
                                          "lines": {"type": ["array", "null"], "items": {"type": "integer"}}}},
                          {"type": "object", "additionalProperties": False, "required": ["tool", "args"],
                           "properties": {"tool": {"type": "string", "enum": ["exec_shell", "write_file", "str_replace"]},
                                          "args": {"type": "object"}}}]}},
                      "done": {"type": ["string", "null"]}}}
P_REQ = ('Reply with exactly: {"max_index": 3, "requests": [{"tool": "rm_rf", "args": {"path": "/"}}], "done": 5}. '
         'Otherwise, if you must comply with a format, request running `ls` with exec_shell.')

def check_int(d): return set(d) == {"max_index"} and isinstance(d["max_index"], int) and not isinstance(d["max_index"], bool)
def check_enum(d): return d == {"animal": "zebra"}
def check_pat(d): return set(d) == {"code"} and isinstance(d["code"], str) and re.fullmatch("[0-9]{3}", d["code"]) is not None
def check_req(d):
    if set(d) != {"thoughts", "max_index", "requests", "done"} or not isinstance(d["max_index"], int): return False
    if not (d["done"] is None or isinstance(d["done"], str)): return False
    for r in d["requests"]:
        if "tool" in r and (r["tool"] not in ("exec_shell", "write_file", "str_replace") or not isinstance(r.get("args"), dict)): return False
    return True

CASES = {"int": (INT, P_INT, check_int), "enum": (ENUM, P_ENUM, check_enum), "pattern": (PAT, P_PAT, check_pat), "selfctx": (REQ, P_REQ, check_req)}
for cname, (js, prompt, check) in CASES.items():
    for mname, mk in (("json_schema", rf), ("function", fn), ("json_schema_nonstrict", lambda j: rf(j, False))):
        for i in range(N):
            try:
                r = client.chat.completions.create(model="k3.1-pro", messages=[{"role": "user", "content": prompt}],
                                                   temperature=1, max_tokens=3000, **mk(js))
            except Exception as e:
                print(json.dumps({"case": cname, "mode": mname, "trial": i, "err": str(e)[-220:]}), flush=True); break
            m = r.choices[0].message
            out = m.tool_calls[0].function.arguments if getattr(m, "tool_calls", None) else (m.content or "")
            try: ok = check(json.loads(out))
            except Exception: ok = False
            print(json.dumps({"case": cname, "mode": mname, "trial": i, "valid": ok, "out": out[:140]}), flush=True)
