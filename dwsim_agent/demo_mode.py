"""Demo mode — template-matching agent without any LLM.

Maps natural-language prompts to the process template library and runs the
canonical script through the executor + verifier. Used when Gemini is
unavailable or the user selects the 'demo' model. Keeps the product fully
functional offline; the LLM layer enhances it when available.
"""
from __future__ import annotations

import re

from . import templates as tpl
from .executor import run_flowsheet_script
from .verifier import verify, as_llm_message

# keyword -> template id (strongest first)
_RULES = [
    (r"ammonia|haber|nh3", "ammonia-synthesis-loop"),
    (r"methanol|ch3oh", "methanol-synthesis-loop"),
    (r"reform|smr|syngas from methane|steam.{0,10}methane", "steam-methane-reforming"),
    (r"compress|intercool", "gas-compression-train"),
    (r"flash|separat|knock.?out|condens", "simple-flash-separation"),
]


def _match_template(prompt: str) -> tuple[str | None, str]:
    p = prompt.lower()
    for pattern, tid in _RULES:
        if re.search(pattern, p):
            return tid, f"matched template '{tid}' by pattern /{pattern}/"
    return None, "no template matched the request"


def _extract_number(prompt: str, patterns: list[str]) -> float | None:
    for pat in patterns:
        m = re.search(pat, prompt, re.IGNORECASE)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                pass
    return None


def run_demo(prompt: str, on_event=None) -> dict:
    """LLM-free run: pick template, adapt obvious parameters, execute."""
    def emit(kind, data):
        if on_event:
            on_event(kind, data)

    emit("demo_start", {"prompt": prompt})
    tid, why = _match_template(prompt)
    if tid is None:
        return {
            "model": "demo",
            "final_text": (
                "I couldn't match this request to a process in my template "
                "library. Try one of: ammonia loop, methanol loop, steam-methane "
                "reforming, gas compression train, or a flash separation. "
                "(Demo mode — connect a Gemini model for open-ended requests.)"
            ),
            "attempts": [],
            "last_envelope": {},
            "transcript": [{"tool": "demo_match", "result_summary": why}],
        }

    t = tpl.get_template(tid)
    emit("template_found", {"template": tid, "description": t["description"]})

    script = t["example_script"]

    # light parameter adaptation from the prompt (conversions/pressures)
    conv = _extract_number(prompt, [r"(\d+(?:\.\d+)?)\s*%\s*(?:single.?pass\s*)?conversion",
                                     r"conversion[^(]{0,20}(\d+(?:\.\d+)?)\s*%"])
    p_out = _extract_number(prompt, [r"(\d+(?:\.\d+)?)\s*bar"])
    if conv is not None:
        script = re.sub(r'"conversion_pct":\s*\d+(?:\.\d+)?',
                       f'"conversion_pct": {conv}', script)
    if p_out is not None and "Compressor" in script:
        script = re.sub(r'P_out_bar=\d+(?:\.\d+)?', f'P_out_bar={p_out}', script)

    emit("tool_call", {"name": "run_flowsheet", "args": {"label": f"{tid}_demo"}})
    envelope = run_flowsheet_script(script, f"{tid}_demo")
    if envelope.get("status") == "ok" and envelope.get("converged"):
        v = verify(envelope)
        envelope["verification"] = v
        envelope["verification_message"] = as_llm_message(v)
        emit("run_result", {"label": f"{tid}_demo", "converged": True,
                            "status": "ok", "verification": v})

    # build a plain-language report
    if envelope.get("converged"):
        streams = envelope.get("streams", {})
        mb = envelope.get("mass_balance", {})
        lines = [f"Built and solved the {t['description'].split('(')[0].strip()}.",
                 "", "Key results:"]
        for tag, s in list(streams.items())[:8]:
            main = max(s.get("composition", {}), key=s.get("composition", {}).get,
                       default=None)
            lines.append(
                f"  {tag}: {s['T_K']-273.15:.1f} °C, {s['P_Pa']/1e5:.0f} bar, "
                f"{s.get('mass_flow_kg_s') or 0:.3f} kg/s"
                + (f" (main: {main} {s['composition'][main]:.1%})" if main else "")
            )
        if mb:
            lines += ["", f"Mass balance closure: {mb.get('closure_pct')}%"]
        if envelope.get("verification"):
            lines += ["Verification: " + ("PASSED" if envelope["verification"]["passed"] else "HAD WARNINGS")]
        lines += ["", "(Demo mode: template-matched. Switch to a Gemini model for "
                      "custom topologies.)"]
        final_text = "\n".join(lines)
    else:
        final_text = ("The template run failed:\n  " +
                     "; ".join(envelope.get("issues", [])[:3]) +
                     "\n(demo mode — try a Gemini model for repair loops)")

    return {
        "model": "demo",
        "final_text": final_text,
        "attempts": [{"label": f"{tid}_demo", "script": script, "envelope": envelope}],
        "last_envelope": envelope,
        "transcript": [{"tool": "demo_match", "result_summary": why},
                        {"tool": "run_flowsheet", "result_summary": {"status": envelope.get("status")}}],
    }
