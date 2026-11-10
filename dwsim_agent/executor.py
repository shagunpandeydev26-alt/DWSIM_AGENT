"""Executor — runs LLM-generated dwsim_kit scripts in an isolated subprocess.

The script convention: it must create a Flowsheet and end with
    result = sim.solve()
The executor appends serialization, runs with a timeout, and returns a
structured envelope (success / failure with actionable issues).
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import os
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

_ALLOWED_IMPORTS_NOTE = (
    "Scripts may only use: from dwsim_agent.kit import Flowsheet / KitError, "
    "and pure-Python stdlib (math, json)."
)

_TAIL = '''
import json as _json
_r = globals().get("result", None)
if _r is None:
    print("__RESULT__" + _json.dumps({"converged": False,
        "errors": ["script did not produce a 'result' variable from sim.solve()"]}))
else:
    print("__RESULT__" + _json.dumps(_r.summary()))
'''


class _RejectingFinder:
    """Blocks imports of network/subprocess modules in the worker."""
    BLOCKED = {"os", "sys", "subprocess", "socket", "urllib", "http",
               "requests", "ctypes", "shutil", "pathlib", "importlib"}

    def find_module(self, name, path=None):
        if name.split(".")[0] in self.BLOCKED:
            return self
        return None

    def load_module(self, name):
        raise ImportError(f"import of {name!r} is not allowed in flowsheet scripts")


def _wrap(script: str) -> str:
    header = (
        "import sys\n"
        f"sys.path.insert(0, r'{PROJECT_ROOT}')\n"
        "import math, json\n"
        "from dwsim_agent.kit import Flowsheet, KitError\n"
    )
    return header + script + "\n" + _TAIL


def run_flowsheet_script(script: str, label: str = "run",
                         timeout_s: int = 150) -> dict:
    """Execute an LLM-emitted dwsim_kit script. Returns a JSON envelope."""
    run_id = f"r_{uuid.uuid4().hex[:6]}"
    run_dir = Path(tempfile.gettempdir()) / "dwsim_agent_runs"
    run_dir.mkdir(exist_ok=True)
    script_path = run_dir / f"{run_id}.py"

    wrapped = _wrap(script)
    script_path.write_text(wrapped, encoding="utf-8")

    env = {
        "PATH": os.environ.get("PATH", ""),
        "LOCALAPPDATA": os.environ.get("LOCALAPPDATA", ""),
        "APPDATA": os.environ.get("APPDATA", ""),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", "C:\\Windows"),
        "SYSTEMDRIVE": os.environ.get("SYSTEMDRIVE", "C:"),
        "PROGRAMFILES": os.environ.get("PROGRAMFILES", "C:\\Program Files"),
        "COMSPEC": os.environ.get("COMSPEC", "C:\\Windows\\System32\\cmd.exe"),
        "TEMP": str(run_dir),
        "TMP": str(run_dir),
        "PYTHONIOENCODING": "utf-8",
        "PYTHONPATH": str(PROJECT_ROOT),
    }

    try:
        proc = subprocess.run(
            [sys.executable, "-X", "utf8", str(script_path)],
            capture_output=True, text=True, timeout=timeout_s,
            cwd=str(run_dir), env=env,
        )
    except subprocess.TimeoutExpired:
        return _envelope(run_id, label, status="error", error_class="timeout",
                         issues=[f"solver exceeded {timeout_s}s wall time"],
                         hint="Recycle loops or column specs may be ill-posed; "
                              "simplify the topology or relax specs.")

    stdout, stderr, rc = proc.stdout, proc.stderr, proc.returncode

    if rc != 0:
        return _envelope(run_id, label, status="error", error_class="crash",
                         issues=[_last_lines(stderr or stdout, 8)],
                         hint="Script raised an exception. Read the trace; "
                              "fix the specific line it points to.")

    for line in stdout.splitlines():
        if line.startswith("__RESULT__"):
            try:
                payload = json.loads(line[len("__RESULT__"):])
            except json.JSONDecodeError:
                return _envelope(run_id, label, status="error",
                                 error_class="crash",
                                 issues=["result payload was not valid JSON"])
            return _envelope(run_id, label, status="ok", payload=payload)

    return _envelope(run_id, label, status="error", error_class="no_result",
                     issues=["script finished but printed no result"],
                     hint="Ensure the script ends with: result = sim.solve()")


def _envelope(run_id, label, status, payload=None, error_class=None,
              issues=None, hint=None) -> dict:
    env = {"run_id": run_id, "label": label, "status": status}
    if status == "ok":
        env.update(payload)
        if env.get("converged") is False:
            env["status"] = "error"
            env["error_class"] = "solve"
            env.setdefault("issues", [])
    else:
        env["error_class"] = error_class
        env["issues"] = issues or []
        if hint:
            env["hint"] = hint
    return env


def _last_lines(text: str, n: int) -> str:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    return "\n".join(lines[-n:])
