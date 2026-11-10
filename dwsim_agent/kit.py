"""dwsim_kit — declarative LLM-facing wrapper around DWSIM.

The LLM writes short declarative Python against this kit. Friendly units at
the boundary (°C, bar, kg/s, %); SI internally. All errors are loud and
actionable BEFORE DWSIM runs.
"""
from __future__ import annotations

import math
from typing import Any, Optional

from .backend import DWSIMBackend


class KitError(ValueError):
    """Raised before any DWSIM call. Always actionable."""


# ------------------------------------------------------------------
# Unit conversions (kit boundary only)
# ------------------------------------------------------------------

def _to_K(T: float, unit: str = "C") -> float:
    if unit == "K":
        return T
    if unit == "C":
        return T + 273.15
    raise KitError(f"unknown temperature unit {unit!r}")


def _to_Pa(P: float, unit: str = "bar") -> float:
    f = {"Pa": 1.0, "kPa": 1e3, "bar": 1e5, "MPa": 1e6, "atm": 101325.0}
    if unit not in f:
        raise KitError(f"unknown pressure unit {unit!r}")
    return P * f[unit]


def _to_kg_s(m: float, unit: str = "kg/s") -> float:
    f = {"kg/s": 1.0, "kg/h": 1.0 / 3600.0, "t/h": 1000.0 / 3600.0}
    if unit not in f:
        raise KitError(f"unknown flow unit {unit!r}")
    return m * f[unit]


# ------------------------------------------------------------------
# Catalog — the agent introspects this to know what it can use
# ------------------------------------------------------------------

UNIT_CATALOG: dict[str, dict] = {
    "Mixer":             {"inlets": "many", "outlets": 1, "params": {}},
    "Splitter":          {"inlets": 1, "outlets": ["out0", "out1", "out2"], "params": {"ratios": "list of fractions per outlet (sums to 1), e.g. [0.95, 0.05]"}},
    "Compressor":        {"inlets": 1, "outlets": 1, "params": {"P_out_bar": "discharge pressure (bar)"}},
    "Pump":              {"inlets": 1, "outlets": 1, "params": {"P_out_bar": "discharge pressure (bar)"}},
    "Heater":            {"inlets": 1, "outlets": 1, "params": {"T_out_C": "outlet temperature (°C)", "dP_bar": "optional pressure drop (bar, default 0)"}},
    "Cooler":            {"inlets": 1, "outlets": 1, "params": {"T_out_C": "outlet temperature (°C)", "dP_bar": "optional pressure drop (bar, default 0)"}},
    "Valve":             {"inlets": 1, "outlets": 1, "params": {"P_out_bar": "outlet pressure after letdown (bar)"}},
    "Flash":             {"inlets": 1, "outlets": ["vapor", "liquid"], "params": {"P_bar": "operating pressure (bar)", "T_C": "optional operating temperature (°C); omit for adiabatic"}},
    "ConversionReactor": {"inlets": 1, "outlets": ["out0", "out1"], "params": {"T_out_C": "outlet temperature (°C)", "reactions": "list of dicts: {'stoich': {compound: coeff (neg reactants, pos products)}, 'base': base compound, 'conversion_pct': percent conversion of base compound, 'phase': 'Vapor'|'Liquid'|'Mixture'}"}},
    "Recycle":           {"inlets": 1, "outlets": 1, "params": {"max_iterations": "optional solver iterations (default 100, raise if the loop struggles to converge)", "tolerance": "optional convergence tolerance (default 0.001)"}},
}

PROPERTY_PACKAGES_HINT = {
    "Peng-Robinson (PR)": "hydrocarbons, non-polar, high pressure",
    "Soave-Redlich-Kwong (SRK)": "hydrocarbons, non-polar",
    "NRTL": "polar mixtures, alcohols, water",
    "UNIQUAC": "polar mixtures",
    "Raoult's Law": "ideal, low pressure",
    "Steam Tables (IAPWS-IF97)": "pure water/steam",
}

# output port name -> index (verified against DWSIM 8.8.2)
_PORT_NAMES = {"vapor": 0, "liquid": 1, "out0": 0, "out1": 1}


class Flowsheet:
    """The only class the LLM uses."""

    def __init__(self, name: str = "flowsheet") -> None:
        self.name = name
        self.compounds: list[str] = []
        self.pp: Optional[str] = None
        self.streams: dict[str, dict] = {}
        self.units: dict[str, dict] = {}
        self.connections: list[tuple[str, str]] = []
        self._backend: Optional[DWSIMBackend] = None

    # ---------------- setup ----------------

    def use_compounds(self, compounds: list[str]) -> None:
        for c in compounds:
            if not isinstance(c, str):
                raise KitError(f"compound {c!r} is not a string")
        self.compounds = list(compounds)

    def use_property_package(self, pp: str) -> None:
        if pp not in PROPERTY_PACKAGES_HINT:
            raise KitError(
                f"unknown property package {pp!r}. Valid: {list(PROPERTY_PACKAGES_HINT)}"
            )
        self.pp = pp

    # ---------------- objects ----------------

    def add_stream(
        self,
        tag: str,
        T_C: Optional[float] = None,
        P_bar: Optional[float] = None,
        mass_flow_kg_s: Optional[float] = None,
        composition: Optional[dict[str, float]] = None,
    ) -> None:
        self._check_tag_unused(tag)
        if composition is not None:
            unknown = [c for c in composition if c not in self.compounds]
            if unknown:
                raise KitError(
                    f"composition of {tag!r} refers to undeclared compounds: {unknown}. "
                    f"Declared: {self.compounds}"
                )
            s = sum(composition.values())
            if not math.isclose(s, 1.0, abs_tol=1e-3):
                raise KitError(
                    f"composition of stream {tag!r} sums to {s:.4f}, not 1.0"
                )
        self.streams[tag] = {
            "T_C": T_C, "P_bar": P_bar,
            "mass_flow_kg_s": mass_flow_kg_s, "composition": composition or {},
        }

    def add_unit(self, kind: str, tag: str, **params: Any) -> None:
        if kind not in UNIT_CATALOG:
            raise KitError(
                f"unknown unit type {kind!r}. Valid: {list(UNIT_CATALOG)}. "
                f"Call Flowsheet.catalog() to see parameters."
            )
        self._check_tag_unused(tag)
        spec = UNIT_CATALOG[kind]["params"]
        for req in spec:
            if req not in params and req not in ("dP_bar", "T_C"):
                raise KitError(
                    f"{kind} requires parameter {req!r}. "
                    f"See catalog: {spec}"
                )
        self.units[tag] = {"kind": kind, "params": params}

    def connect(self, src: str, dst: str) -> None:
        """Connect outlet to inlet. Use 'UnitTag.vapor' / 'UnitTag.liquid'
        to pick a specific outlet port of Flash units."""
        self._check_endpoint(src)
        self._check_endpoint(dst)
        self.connections.append((src, dst))

    def add_recycle(self, from_: str, to: str) -> None:
        """Close a recycle loop through a Recycle tear unit. Use INSTEAD of
        plain connect() for streams that loop back."""
        self._check_endpoint(from_)
        self._check_endpoint(to)
        self.connections.append((from_, to))

    # ---------------- introspection ----------------

    @staticmethod
    def catalog() -> dict:
        return UNIT_CATALOG

    @staticmethod
    def property_packages() -> dict:
        return PROPERTY_PACKAGES_HINT

    # ---------------- validation ----------------

    def validate(self) -> list[str]:
        issues: list[str] = []
        if not self.compounds:
            issues.append("no compounds declared (call use_compounds)")
        if not self.pp:
            issues.append("no property package declared (call use_property_package)")

        dsts = {self._split_ref(c[1])[0] for c in self.connections}
        srcs = {self._split_ref(c[0])[0] for c in self.connections}
        for tag, s in self.streams.items():
            if tag in dsts:
                continue  # not a feed
            for f, fname in (("T_C", "temperature"), ("P_bar", "pressure"), ("mass_flow_kg_s", "mass flow")):
                if s[f] is None:
                    issues.append(f"feed stream {tag!r} missing {fname}")
            if not s["composition"]:
                issues.append(f"feed stream {tag!r} missing composition")
        if self.streams and not self.connections:
            issues.append("no connections defined (call connect)")
        # terminal check: every unit needs at least one inbound and outbound
        for tag in self.units:
            if tag not in srcs:
                issues.append(f"unit {tag!r} has no outbound connection")
        return issues

    # ---------------- solve ----------------

    def solve(self, timeout_s: int = 120) -> "SolveResult":
        issues = self.validate()
        if issues:
            raise KitError("flowsheet invalid:\n  - " + "\n  - ".join(issues))
        return _build_and_solve(self)

    # ---------------- private ----------------

    def _check_tag_unused(self, tag: str) -> None:
        if tag in self.streams or tag in self.units:
            raise KitError(f"tag {tag!r} already used")

    @staticmethod
    def _split_ref(ref: str) -> tuple[str, Optional[str]]:
        parts = ref.split(".")
        if len(parts) > 2:
            raise KitError(f"bad endpoint reference {ref!r}")
        return parts[0], (parts[1] if len(parts) == 2 else None)

    def _check_endpoint(self, ref: str) -> None:
        tag, port = self._split_ref(ref)
        if tag not in self.streams and tag not in self.units:
            raise KitError(f"unknown endpoint {ref!r} — no stream or unit with that tag")
        if port is not None:
            if tag in self.streams:
                raise KitError(f"streams have no ports — bad reference {ref!r}")
            if port not in _PORT_NAMES:
                raise KitError(
                    f"unknown port {port!r} on {tag!r}. Valid: {list(_PORT_NAMES)}"
                )


# ------------------------------------------------------------------
# Build & solve (backend wiring, verified against DWSIM 8.8.2)
# ------------------------------------------------------------------

def _build_and_solve(fs: Flowsheet) -> "SolveResult":
    be = DWSIMBackend()
    fs._backend = be
    OT = be.ObjectType

    for c in fs.compounds:
        be.add_compound(c)
    be.add_property_package(fs.pp)

    # create + spec user streams
    for tag, s in fs.streams.items():
        obj = be.add_object(OT.MaterialStream, tag)
        if s["T_C"] is not None:
            ph = obj.GetAsObject().Phases[0]
            ph.Properties.temperature = _to_K(s["T_C"])
            ph.Properties.pressure = _to_Pa(s["P_bar"])
            ph.Properties.massflow = s["mass_flow_kg_s"]
            for cname in fs.compounds:
                ph.Compounds[cname].MoleFraction = (s["composition"] or {}).get(cname, 0.0)

    # reactions first (reactors reference them)
    for tag, u in fs.units.items():
        if u["kind"] == "ConversionReactor":
            for i, r in enumerate(u["params"].get("reactions", [])):
                be.create_conversion_reaction(
                    f"rxn_{tag}_{i}",
                    r.get("stoich", {}),
                    r.get("base", ""),
                    r.get("phase", "Vapor"),
                    str(r.get("conversion_pct", 0)),
                )

    KIND_MAP = {
        "Mixer": OT.NodeIn,
        "Splitter": OT.NodeOut,
        "Compressor": OT.Compressor,
        "Pump": OT.Pump,
        "Heater": OT.Heater,
        "Cooler": OT.Cooler,
        "Valve": OT.Valve,
        "Flash": OT.Vessel,
        "ConversionReactor": OT.RCT_Conversion,
        "Recycle": OT.OT_Recycle,
    }
    for tag, u in fs.units.items():
        be.add_object(KIND_MAP[u["kind"]], tag)

    # ---- wire connections with port resolution ----
    used_inlets: dict[str, int] = {t: 0 for t in fs.units}
    port_map: dict[str, str] = {}   # "UnitTag.portname" -> DWSIM stream tag

    def next_inlet(unit_tag: str) -> int:
        i = used_inlets.get(unit_tag, 0)
        used_inlets[unit_tag] = i + 1
        return i

    def record_port(stag: str, sport: Optional[str], target_stream: str) -> None:
        if sport:
            port_map[f"{stag}.{sport}"] = target_stream

    auto_count = 0
    for src_ref, dst_ref in fs.connections:
        stag, sport = fs._split_ref(src_ref)
        dtag, dport = fs._split_ref(dst_ref)
        src_is_unit = stag in fs.units
        dst_is_unit = dtag in fs.units

        if not src_is_unit and not dst_is_unit:
            raise KitError(f"cannot connect stream {src_ref!r} directly to stream {dst_ref!r}")

        if not src_is_unit:  # stream -> unit
            be.connect(stag, dtag, 0, next_inlet(dtag))
        elif not dst_is_unit:  # unit -> stream
            sp = _PORT_NAMES.get(sport, 0) if sport else 0
            be.connect(stag, dtag, sp, 0)
            record_port(stag, sport, dtag)
        else:  # unit -> unit : auto intermediate stream
            auto_count += 1
            mid = f"_auto_{stag}_{dtag}_{auto_count}"
            be.add_object(OT.MaterialStream, mid)
            sp = _PORT_NAMES.get(sport, 0) if sport else 0
            be.connect(stag, mid, sp, 0)
            record_port(stag, sport, mid)
            be.connect(mid, dtag, 0, next_inlet(dtag))

    # ConversionReactors in DWSIM require BOTH material outlets connected.
    used_rx_ports: dict[str, set] = {}
    for src_ref, dst_ref in fs.connections:
        stag, sport = fs._split_ref(src_ref)
        if stag in fs.units and fs.units[stag]["kind"] == "ConversionReactor":
            used_rx_ports.setdefault(stag, set()).add(_PORT_NAMES.get(sport, 0) if sport else 0)
    n = 0
    for tag, u in fs.units.items():
        if u["kind"] != "ConversionReactor":
            continue
        for port in (0, 1):
            if port not in used_rx_ports.get(tag, set()):
                n += 1
                dummy = f"_dummy_{tag}_out{port}"
                be.add_object(OT.MaterialStream, dummy)
                be.connect(tag, dummy, port, 0)

    # ---- unit specs ----
    from System import Enum as SysEnum

    for tag, u in fs.units.items():
        o = be.get_object(tag).GetAsObject()
        p = u["params"]
        k = u["kind"]
        if k in ("Compressor", "Pump"):
            o.POut = _to_Pa(p["P_out_bar"])
        elif k in ("Heater", "Cooler"):
            cm_type = o.CalcMode.GetType()
            o.CalcMode = SysEnum.Parse(cm_type, "OutletTemperature")
            o.OutletTemperature = _to_K(p["T_out_C"])
            if p.get("dP_bar"):
                o.PressureDrop = _to_Pa(p["dP_bar"])
        elif k == "Valve":
            o.OutletPressure = _to_Pa(p["P_out_bar"])
        elif k == "Flash":
            o.FlashPressure = _to_Pa(p["P_bar"])
            if p.get("T_C") is not None:
                o.FlashTemperature = _to_K(p["T_C"])
        elif k == "ConversionReactor":
            from DWSIM.UnitOperations.Reactors import OperationMode as RxMode
            o.ReactionSetID = "DefaultSet"
            if p.get("T_out_C") is not None:
                o.ReactorOperationMode = RxMode.OutletTemperature
                o.OutletTemperature = _to_K(p["T_out_C"])
        elif k == "Recycle":
            o.MaximumIterations = int(p.get("max_iterations", 100))
            if "tolerance" in p:
                try:
                    cp = o.ConvergenceParameters
                    cp.ConvTol = float(p["tolerance"])
                except Exception:
                    pass
        elif k == "Splitter":
            ratios = p.get("ratios") or (
                [p["split_fraction"], 1.0 - float(p["split_fraction"]), 0.0]
                if "split_fraction" in p else None)
            if ratios:
                arr = o.Ratios
                arr.Clear()
                for r in ratios:
                    arr.Add(float(r))
                # fill remaining outlets with 0
                while arr.Count < 3:
                    arr.Add(0.0)

    errors = be.solve()
    return SolveResult(be, fs, errors, port_map)


class SolveResult:
    def __init__(self, be: DWSIMBackend, fs: Flowsheet, errors: list[str],
                 port_map: dict[str, str]) -> None:
        self._be = be
        self._fs = fs
        self.errors = errors
        self._port_map = port_map
        self.converged = be.solved and not errors

    def _resolve(self, ref: str) -> str:
        if ref in self._port_map:
            return self._port_map[ref]
        return ref

    def stream(self, ref: str) -> dict:
        if not self.converged:
            raise KitError(
                f"cannot read stream {ref!r}: flowsheet did not converge. "
                f"Errors: {self.errors}"
            )
        return self._be.stream_summary(self._resolve(ref))

    def all_streams(self) -> dict[str, dict]:
        out = {tag: self._be.stream_summary(tag) for tag in self._fs.streams}
        for ref in self._port_map:
            out[ref] = self._be.stream_summary(self._port_map[ref])
        return out

    def mass_balance(self) -> dict:
        feeds = [t for t, s in self._fs.streams.items() if s["mass_flow_kg_s"] is not None]
        total_in = sum(self._fs.streams[t]["mass_flow_kg_s"] or 0 for t in feeds)
        srcs = {self._fs._split_ref(c[0])[0] for c in self._fs.connections}
        products = [t for t in self._fs.streams if t not in srcs]
        total_out = sum(self.stream(t)["mass_flow_kg_s"] for t in products) if self.converged else 0.0
        closure = 100.0 * total_out / total_in if total_in else 0.0
        return {
            "in_kg_s": total_in, "out_kg_s": round(total_out, 4),
            "closure_pct": round(closure, 2),
            "feed_streams": feeds, "product_streams": products,
        }

    def summary(self) -> dict:
        d = {"converged": self.converged, "errors": self.errors}
        if self.converged:
            d["streams"] = self.all_streams()
            d["mass_balance"] = self.mass_balance()
        return d
