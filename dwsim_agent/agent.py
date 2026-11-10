"""Gemini agent loop — plan -> emit dwsim_kit script -> run -> repair.

Uses Gemini function calling with a small tool surface; the kit keeps the
hallucination surface tiny, and every failure returns structured hints.
"""
from __future__ import annotations

import json
import os
from typing import Any, Callable

from dotenv import load_dotenv

load_dotenv()

from . import templates as tpl
from .executor import run_flowsheet_script
from .verifier import verify, as_llm_message

MAX_STEPS = 8
MAX_REPAIR_ATTEMPTS = 3

DEFAULT_MODELS = [
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
]

SYSTEM_PROMPT = """You are a chemical process engineer that builds and runs DWSIM flowsheets through Python.

WORKFLOW (follow strictly):
1. PLAN. Call find_template if the request resembles a known process. Call list_units and list_property_packages to ground yourself in what the kit supports. If you need exact compound names, call find_compounds.
2. EMIT. Write ONE complete dwsim_kit script. It must:
   - start with: from dwsim_agent.kit import Flowsheet
   - create sim = Flowsheet("name")
   - declare compounds and a property package
   - add streams, units, connections
   - close any recycle loop with a Recycle unit and sim.add_recycle(...)
   - end with: result = sim.solve()
3. RUN. Call run_flowsheet with the script.
4. REPAIR. If the envelope has status=error, read `issues` and `hint`, fix ONLY the named problem, and run again. Max repair attempts: 3. Do not rewrite the whole script unless the topology is wrong.
5. VERIFY. If status=ok but `verification.passed` is false, read the findings and fix the named checks.
6. REPORT. Give a final answer in plain language: what you built, key stream conditions (T, P, flow, main compositions), convergence and mass-balance status, and any assumptions you made.

HARD RULES:
- Never invent unit types or property packages — only what the tools list.
- Never guess compound names — DWSIM is strict (e.g. "Ammonia" not "NH3"). If unsure call find_compounds.
- Every feed stream needs T_C, P_bar, mass_flow_kg_s and a composition that sums to 1.0.
- Recycle loops must be closed with a Recycle unit: connect upstream to the Recycle, then sim.add_recycle("RC1", "MixerTag"). Never connect a unit back to itself with plain connect().
- If the user under-specifies, make ONE reasonable assumption per missing input and state it in your final report.
- Units: temperatures in °C, pressures in bar, flows in kg/s, conversions in percent.
- ConversionReactor reactions use NEGATIVE coefficients for reactants, POSITIVE for products.
"""


def _build_tools() -> list[dict]:
    return [
        {
            "name": "list_units",
            "description": "List every unit operation type the kit supports, with its required parameters.",
            "parameters": {"type": "object", "properties": {}},
        },
        {
            "name": "list_property_packages",
            "description": "List supported thermodynamic property packages with guidance on when to use each.",
            "parameters": {"type": "object", "properties": {}},
        },
        {
            "name": "find_compounds",
            "description": "Search DWSIM's compound database by substring (e.g. 'methanol', 'ammonia'). "
                           "Returns exact names the kit expects.",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string", "description": "name or formula substring"}},
                "required": ["query"]},
        },
        {
            "name": "find_template",
            "description": "Search the process template library for canonical topologies "
                           "(ammonia loop, methanol loop, reforming, flash, compression...).",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string", "description": "process description"}},
                "required": ["query"]},
        },
        {
            "name": "get_template",
            "description": "Get the full template entry including a worked example script for a template id.",
            "parameters": {"type": "object", "properties": {
                "template_id": {"type": "string"}},
                "required": ["template_id"]},
        },
        {
            "name": "run_flowsheet",
            "description": "Execute a dwsim_kit script in the sandboxed DWSIM runtime. "
                           "Returns a success envelope (streams, mass balance) or structured diagnostics.",
            "parameters": {"type": "object", "properties": {
                "script": {"type": "string", "description": "Complete Python program using dwsim_agent.kit."},
                "label": {"type": "string", "description": "short name e.g. 'ammonia_v1'"}},
                "required": ["script", "label"]},
        },
    ]


class AgentSession:
    """One agent conversation bound to a Gemini model."""

    def __init__(self, model: str | None = None) -> None:
        from google import genai

        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key or api_key == "your-key-here":
            raise RuntimeError(
                "GEMINI_API_KEY not set. Create .env with GEMINI_API_KEY=... "
                "(free key from aistudio.google.com)"
            )
        self.model_id = model or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        self.client = genai.Client(api_key=api_key)
        self.tools = _build_tools()
        self._compound_cache: list[str] | None = None

    # ---------------- tool implementations ----------------

    def _tool_list_units(self, **_) -> dict:
        from .kit import UNIT_CATALOG
        return UNIT_CATALOG

    def _tool_list_pp(self, **_) -> dict:
        from .kit import PROPERTY_PACKAGES_HINT
        return PROPERTY_PACKAGES_HINT

    def _tool_find_compounds(self, query: str, **_) -> dict:
        if self._compound_cache is None:
            from .backend import DWSIMBackend
            be = DWSIMBackend()
            self._compound_cache = be.available_compounds()
        q = query.lower()
        return {"matches": [c for c in self._compound_cache if q in c.lower()][:15]}

    def _tool_find_template(self, query: str, **_) -> dict:
        return {"templates": tpl.find_template(query)}

    def _tool_get_template(self, template_id: str, **_) -> dict:
        t = tpl.get_template(template_id)
        return t if t else {"error": f"no template {template_id!r}"}

    def _tool_run_flowsheet(self, script: str, label: str = "run", **_) -> dict:
        envelope = run_flowsheet_script(script, label)
        if envelope.get("status") == "ok" and envelope.get("converged"):
            v = verify(envelope)
            envelope["verification"] = v
            envelope["verification_message"] = as_llm_message(v)
        return envelope

    def _execute_tool(self, name: str, args: dict) -> Any:
        dispatch: dict[str, Callable] = {
            "list_units": self._tool_list_units,
            "list_property_packages": self._tool_list_pp,
            "find_compounds": self._tool_find_compounds,
            "find_template": self._tool_find_template,
            "get_template": self._tool_get_template,
            "run_flowsheet": self._tool_run_flowsheet,
        }
        fn = dispatch.get(name)
        if fn is None:
            return {"error": f"unknown tool {name!r}"}
        try:
            return fn(**args)
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}

    # ---------------- main loop ----------------

    def run(self, user_prompt: str, on_event=None) -> dict:
        """Run the agent loop. on_event(kind, data) streams progress to the UI."""
        def emit(kind, data):
            if on_event:
                on_event(kind, data)

        history: list[dict] = []
        transcript: list[dict] = []
        script_attempts: list[dict] = []
        final_text = ""
        last_envelope: dict = {}

        contents = [
            {"role": "user", "parts": [{"text": user_prompt}]}
        ]

        for step in range(MAX_STEPS):
            emit("llm_call", {"step": step + 1, "model": self.model_id})
            try:
                resp = self.client.models.generate_content(
                    model=self.model_id,
                    contents=contents,
                    config={
                        "system_instruction": SYSTEM_PROMPT,
                        "tools": [{"function_declarations": self.tools}],
                        "temperature": 0.2,
                    },
                )
            except Exception as e:
                msg = str(e)
                if "503" in msg or "UNAVAILABLE" in msg or "high demand" in msg:
                    raise RuntimeError(
                        f"Model {self.model_id} is overloaded at Google's end "
                        f"(503). Try the 'demo' model or retry in a few minutes."
                    ) from e
                raise

            parts = []
            for p in resp.candidates[0].content.parts:
                if p.function_call:
                    parts.append({"type": "function_call", "name": p.function_call.name,
                                  "args": dict(p.function_call.args or {})})
                elif p.text:
                    parts.append({"type": "text", "text": p.text})

            if not parts:
                final_text = resp.text or "(no response)"
                emit("final", {"text": final_text})
                break

            contents.append({"role": "model", "parts": resp.candidates[0].content.parts})

            function_calls = [p for p in parts if p["type"] == "function_call"]
            texts = [p["text"] for p in parts if p["type"] == "text"]

            if texts:
                emit("assistant_text", {"text": "\n".join(texts)})

            if not function_calls:
                final_text = "\n".join(texts)
                emit("final", {"text": final_text})
                break

            tool_parts = []
            for fc in function_calls:
                emit("tool_call", {"name": fc["name"], "args": fc["args"]})
                result = self._execute_tool(fc["name"], fc["args"])
                if fc["name"] == "run_flowsheet":
                    script_attempts.append({
                        "label": fc["args"].get("label", "run"),
                        "script": fc["args"].get("script", ""),
                        "envelope": result,
                    })
                    last_envelope = result
                    emit("run_result", {
                        "label": fc["args"].get("label"),
                        "converged": result.get("converged", False),
                        "status": result.get("status"),
                        "verification": result.get("verification", {}),
                    })
                transcript.append({"tool": fc["name"], "args": fc["args"],
                                   "result_summary": _slim(result)})
                tool_parts.append({
                    "function_response": {
                        "name": fc["name"],
                        "response": _jsonable(result),
                    }
                })

            contents.append({"role": "user", "parts": tool_parts})

        return {
            "model": self.model_id,
            "final_text": final_text,
            "attempts": script_attempts,
            "last_envelope": last_envelope,
            "transcript": transcript,
        }


def _slim(result: Any) -> Any:
    if isinstance(result, dict):
        out = {k: v for k, v in result.items() if k not in ("streams",)}
        if "streams" in result:
            out["streams"] = f"({len(result['streams'])} streams)"
        return out
    return result


def _jsonable(result: Any) -> Any:
    try:
        json.dumps(result)
        return result
    except (TypeError, ValueError):
        return {"repr": repr(result)[:400]}
