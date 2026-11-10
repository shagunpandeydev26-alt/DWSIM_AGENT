"""Verifier — deterministic sanity checks on a converged run envelope.

Convergence is not correctness: runs can converge with broken mass balance,
trivial flows, or unphysical values. These checks catch that and produce
repair hints for the agent loop.
"""
from __future__ import annotations

MASS_CLOSURE_PCT = 97.0
TRIVIAL_FLOW_KG_S = 1e-6


def verify(envelope: dict) -> dict:
    """Returns {'passed': bool, 'findings': [{'severity', 'check', 'message', 'hint'}]}"""
    findings: list[dict] = []

    def add(sev, check, msg, hint=None):
        findings.append({"severity": sev, "check": check,
                         "message": msg, "hint": hint})

    if envelope.get("status") != "ok":
        # already a failure envelope; nothing more to check
        return {"passed": False, "findings": []}

    streams = envelope.get("streams", {}) or {}

    # 1. trivial solution (all feeds zero)
    feeds = {t: s for t, s in streams.items() if s.get("is_feed")}
    if streams and all(s.get("mass_flow_kg_s", 0) < TRIVIAL_FLOW_KG_S
                       for s in streams.values()):
        add("error", "trivial_solution",
            "All stream flows are ~zero; solver returned the trivial solution.",
            "Confirm every fresh feed stream has mass_flow_kg_s set.")

    # 2. mass balance
    mb = envelope.get("mass_balance") or {}
    closure = mb.get("closure_pct")
    if closure is not None and closure < MASS_CLOSURE_PCT:
        add("error" if closure < 90 else "warning", "mass_balance",
            f"Mass balance closes at {closure:.2f}% (in={mb.get('in_kg_s')} "
            f"out={mb.get('out_kg_s')} kg/s).",
            "Usually an unconverged recycle, or a product stream is not "
            "connected to a terminal position.")

    # 3. unphysical values
    for tag, s in streams.items():
        if s.get("T_K", 1) <= 0:
            add("error", "unphysical",
                f"Stream {tag!r} has T <= 0 K.", "Check heater/cooler T_out_C values.")
        x = s.get("composition") or {}
        bad = [c for c, f in x.items() if f < -1e-9 or f > 1 + 1e-6]
        if bad:
            add("error", "unphysical",
                f"Stream {tag!r} has invalid fractions for {bad}.",
                "Check reaction stoichiometry and feed composition.")
        if s.get("mass_flow_kg_s", 0) > TRIVIAL_FLOW_KG_S:
            total = sum(x.values())
            if abs(total - 1.0) > 5e-3:
                add("warning", "composition_sum",
                    f"Stream {tag!r} composition sums to {total:.4f}, not 1.0.",
                    "Ensure feed compositions sum to exactly 1.0.")

    # 4. NaN anywhere
    for tag, s in streams.items():
        vals = [s.get("T_K"), s.get("P_Pa"), s.get("mass_flow_kg_s")] + \
               list((s.get("composition") or {}).values())
        if any(v is not None and v != v for v in vals):  # NaN != NaN
            add("error", "nan",
                f"Stream {tag!r} contains NaN values.",
                "Property package may be wrong for this chemistry; "
                "or specs are out of range.")

    passed = not any(f["severity"] == "error" for f in findings)
    return {"passed": passed, "findings": findings}


def as_llm_message(v: dict) -> str:
    lines = []
    for f in v["findings"]:
        tag = "ERROR" if f["severity"] == "error" else "WARN"
        lines.append(f"[{tag}] {f['check']}: {f['message']}")
        if f.get("hint"):
            lines.append(f"  -> {f['hint']}")
    if not lines:
        lines.append("All verification checks passed.")
    return "\n".join(lines)
