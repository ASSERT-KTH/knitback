"""Run knitback on SWE-bench Verified instances listed in `tasks.json`, then judge with the official harness.

Per instance: pull the image, copy `/testbed` to the host, run a container with that copy bind-mounted at
`/testbed`, run the knitback loop with cwd = the copy (file requests and edits act on the host copy,
`exec_shell` runs inside the container, without network, in the `testbed` conda env), save the diff as a prediction,
evaluate it with `swebench.harness.run_evaluation` (bench/.venv), then remove container and image.

Usage (from the repo root, with the knitback venv):
    .venv/bin/python bench/run_swebench.py [INSTANCE_ID ...] [--max-turns 100] [--keep-image]
        [--out bench/results] [--context-budget TOKENS]
Outputs: <out>/<instance_id>/{run.jsonl, patch.diff, result.json, eval/}
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import agentknit
from agentknit.tool_library import TOOL_LIBRARY

from knitback._loop import run

BENCH = Path(__file__).resolve().parent
RESULTS = BENCH / "results"
DATASET = "princeton-nlp/SWE-bench_Verified"

PROMPT = """\
Resolve the following GitHub issue of the repository {repo}.

The repository is checked out in the current directory, at the commit where the issue was reported.
Shell commands run inside the repository's own environment (its Python and dependencies are installed),
with the repository as working directory. Change the non-test source files so that the issue is resolved;
do not modify the existing tests. When you are done, set "done" to a short summary of your change.

<issue>
{problem_statement}
</issue>
"""


def sh(*cmd: str, check: bool = True, capture: bool = False) -> str:
    proc = subprocess.run(cmd, check=check, text=True,
                          stdout=subprocess.PIPE if capture else subprocess.DEVNULL,
                          stderr=subprocess.PIPE if capture else subprocess.DEVNULL)
    return proc.stdout if capture else ""


def image_of(instance_id: str) -> str:
    return f"swebench/sweb.eval.x86_64.{instance_id.replace('__', '_1776_').lower()}:latest"


def container_shell(container: str) -> Any:
    """exec_shell replacement: run the command in the container, testbed env, cwd /testbed."""
    t_run = TOOL_LIBRARY["t_run"]

    def exec_shell(command: str) -> Any:
        inner = f"source /opt/miniconda3/bin/activate testbed >/dev/null 2>&1; cd /testbed; {command}"
        return t_run(f"docker exec -w /testbed {container} bash -c {shlex.quote(inner)}")

    return exec_shell


def confined(name: str, root: Path) -> Any:
    """File tool `name`, refusing paths outside `root` (the host copy of the repo)."""
    fn = TOOL_LIBRARY[{"read_file": "t_read", "write_file": "t_write", "str_replace": "t_update"}[name]]

    def tool(path: str, **kwargs: Any) -> Any:
        resolved = (root / os.path.expanduser(path)).resolve()
        if not resolved.is_relative_to(root.resolve()):
            return f"ERROR: {path} is outside the repository", {"ok": False, "error": "outside repository"}
        return fn(path=str(resolved), **kwargs)

    return tool


def stats(log: Path) -> dict[str, Any]:
    records = [json.loads(line) for line in log.read_text().splitlines()]
    went_back = [r["turn"] for r in records
                 if r.get("max_index") is not None and r["max_index"] < r["items_before"] - 1]
    prompts = [r["usage"]["prompt_tokens"] for r in records if r.get("usage") and r["usage"].get("prompt_tokens")]
    return {"turns": len(records), "went_back_turns": went_back,
            "protocol_errors": sum(1 for r in records if r.get("error")),
            "peak_items": max((r["items_after"] for r in records), default=0),
            "peak_prompt_tokens": max(prompts, default=None), "total_prompt_tokens": sum(prompts)}


def run_instance(task: dict[str, Any], max_turns: int, keep_image: bool, results: Path,
                 context_budget: int | None) -> dict[str, Any]:
    iid, image = task["instance_id"], image_of(task["instance_id"])
    out = results / iid
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    workdir = out / "testbed"
    container = f"knitback-{iid.lower()}"
    sh("docker", "pull", "-q", image)
    sh("docker", "rm", "-f", container, check=False)
    tmp = sh("docker", "create", image, capture=True).strip()
    sh("docker", "cp", f"{tmp}:/testbed", str(workdir))
    sh("docker", "rm", tmp)
    # No network: the environment is preinstalled, and with network the model can fetch the upstream fix.
    sh("docker", "run", "-d", "--network", "none", "--name", container, "-v", f"{workdir}:/testbed", image,
       "sleep", "infinity")
    sh("docker", "exec", container, "git", "config", "--global", "--add", "safe.directory", "/testbed")

    schema = agentknit.load_specification("k3.1-pro", inference_db="kimi-coding")
    specs, tool_dispatch = agentknit.default_tool_spec()
    tool_specs: list[dict[str, Any]] = [s for s in specs if s["function"]["name"] != "read_file"]  # type: ignore[index]
    tool_dispatch = dict(tool_dispatch) | {"exec_shell": {"python_function": container_shell(container)}}
    for name in ("read_file", "write_file", "str_replace"):  # the host holds other runs' patches
        tool_dispatch[name] = {**tool_dispatch[name], "python_function": confined(name, workdir)}

    started = time.time()
    cwd = os.getcwd()
    os.chdir(workdir)
    try:
        result = run(PROMPT.format(**task), agentknit.create_client(schema), schema.get("model", "k3.1-pro"),
                     tool_specs, tool_dispatch, request_params=dict(schema.get("request_params") or {}),
                     max_turns=max_turns, log_path=out / "run.jsonl", context_budget=context_budget)
        final, crash = result.final, None
    except Exception as exc:  # noqa: BLE001 - a crashed run is a data point, not a harness failure
        final, crash = None, f"{type(exc).__name__}: {exc}"[:2000]
    finally:
        os.chdir(cwd)
    duration = round(time.time() - started)

    # Prediction: all changes except files the gold test patch touches (it is applied on top).
    sh("docker", "exec", container, "bash", "-c", "cd /testbed && git add -A")
    exclude = [f":(exclude){f}" for f in task["test_files"]]
    patch = sh("docker", "exec", container, "git", "-C", "/testbed", "diff", "--cached", "HEAD", "--", ".",
               *exclude, capture=True)
    (out / "patch.diff").write_text(patch)
    sh("docker", "rm", "-f", container)
    # Files written in the container are root-owned on the host: remove the copy from inside a container.
    sh("docker", "run", "--rm", "-v", f"{out}:/out", image, "rm", "-rf", "/out/testbed")

    pred = out / "prediction.jsonl"
    pred.write_text(json.dumps({"instance_id": iid, "model_name_or_path": "knitback-k3.1", "model_patch": patch}) + "\n")
    (out / "eval").mkdir()
    subprocess.run([str(BENCH / ".venv/bin/python"), "-m", "swebench.harness.run_evaluation",
                    "--dataset_name", DATASET, "--predictions_path", str(pred), "--instance_ids", iid,
                    "--run_id", "knitback", "--max_workers", "1"],
                   cwd=out / "eval", stdout=(out / "eval/eval.log").open("w"), stderr=subprocess.STDOUT, check=False)
    summary_file = out / "eval" / "knitback-k3.1.knitback.json"  # the harness's run summary
    resolved = None
    if summary_file.exists():
        resolved = iid in json.loads(summary_file.read_text()).get("resolved_ids", [])
    if not keep_image:
        sh("docker", "rmi", "-f", image, check=False)

    summary = {"instance_id": iid, "resolved": resolved, "final": final, "crash": crash,
               "duration_s": duration, "patch_lines": patch.count("\n"),
               **(stats(out / "run.jsonl") if (out / "run.jsonl").exists() else {})}
    (out / "result.json").write_text(json.dumps(summary, indent=1) + "\n")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("instance_ids", nargs="*", help="default: every task in tasks.json")
    parser.add_argument("--max-turns", type=int, default=100)
    parser.add_argument("--keep-image", action="store_true")
    parser.add_argument("--out", type=Path, default=RESULTS, help="results directory (default: bench/results)")
    parser.add_argument("--context-budget", type=int, default=None,
                        help="soft context budget shown to the model (default: none)")
    args = parser.parse_args()
    tasks = json.loads((BENCH / "tasks.json").read_text())
    if args.instance_ids:
        tasks = [t for t in tasks if t["instance_id"] in args.instance_ids]
    for task in tasks:
        # streamed tool output must not mix with the JSON lines on stdout
        with contextlib.redirect_stdout(sys.stderr):
            summary = run_instance(task, args.max_turns, args.keep_image, args.out.resolve(), args.context_budget)
        print(json.dumps({k: summary.get(k) for k in ("instance_id", "resolved", "turns", "went_back_turns",
                                                       "protocol_errors", "crash")}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
