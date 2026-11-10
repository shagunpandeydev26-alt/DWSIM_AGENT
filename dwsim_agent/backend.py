"""DWSIM .NET bridge — verified patterns for DWSIM 8.8.2 via pythonnet.

All attribute names here were empirically verified against the installed
DWSIM 8.8.2 build (see tests/test_ammonia_loop.py for the reference proof).
"""
from __future__ import annotations

import os
import sys
from typing import Any

DWSIM_PATH = os.environ.get(
    "DWSIM_PATH",
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "DWSIM"),
)

_loaded = False


def _load_assemblies() -> None:
    global _loaded
    if _loaded:
        return
    if DWSIM_PATH not in sys.path:
        sys.path.append(DWSIM_PATH)
    import clr  # type: ignore

    for asm in [
        "DWSIM.Automation",
        "DWSIM.Interfaces",
        "DWSIM.SharedClasses",
        "DWSIM.Thermodynamics",
        "DWSIM.UnitOperations",
        "DWSIM.MathOps",
    ]:
        try:
            clr.AddReference(asm)
        except Exception:
            pass  # ThermoC/G11n helper warnings are non-fatal
    _loaded = True


class DWSIMBackend:
    """Thin wrapper around DWSIM Automation3 for one flowsheet run."""

    def __init__(self) -> None:
        _load_assemblies()
        from DWSIM.Automation import Automation3
        from DWSIM.Interfaces.Enums.GraphicObjects import ObjectType

        self._Automation3 = Automation3
        self.ObjectType = ObjectType
        self.auto = Automation3()
        self.sim = self.auto.CreateFlowsheet()

        from System.Collections.Generic import Dictionary
        from System import String, Double, Enum as SysEnum

        self._Dict = Dictionary
        self._Str = String
        self._Dbl = Double
        self._SysEnum = SysEnum

    # ---------------- setup ----------------

    def add_compound(self, name: str) -> None:
        self.sim.AddCompound(name)

    def add_property_package(self, name: str) -> None:
        self.sim.CreateAndAddPropertyPackage(name)

    def available_property_packages(self) -> list[str]:
        return list(self.sim.AvailablePropertyPackages.Keys)

    def available_compounds(self) -> list[str]:
        return list(self.sim.AvailableCompounds.Keys)

    # ---------------- objects & connections ----------------

    def add_object(self, obj_type, tag: str):
        return self.sim.AddObject(obj_type, 0, 0, tag)

    def connect(self, src_tag: str, dst_tag: str, sport: int = 0, dport: int = 0) -> None:
        src = self.sim.GetFlowsheetSimulationObject(src_tag)
        dst = self.sim.GetFlowsheetSimulationObject(dst_tag)
        self.sim.ConnectObjects(src.GraphicObject, dst.GraphicObject, sport, dport)

    # ---------------- reactions ----------------

    def create_conversion_reaction(
        self, name: str, stoich: dict[str, float], base: str, phase: str, conv_percent: str
    ) -> None:
        d = self._Dict[self._Str, self._Dbl]()
        for k, v in stoich.items():
            d.Add(k, v)
        rxn = self.sim.CreateConversionReaction(name, name, d, base, phase, conv_percent)
        self.sim.AddReaction(rxn)
        self.sim.AddReactionToSet(rxn.ID, "DefaultSet", True, 0)

    # ---------------- solving ----------------

    def solve(self) -> list[str]:
        """Run the solver; returns list of error message strings (empty = ok)."""
        errors = self.auto.CalculateFlowsheet4(self.sim)
        out = []
        if errors is not None:
            for e in errors:
                out.append(str(e.Message))
        return out

    @property
    def solved(self) -> bool:
        return bool(self.sim.Solved)

    # ---------------- reading results ----------------

    def get_object(self, tag: str) -> Any:
        return self.sim.GetFlowsheetSimulationObject(tag)

    def stream_summary(self, tag: str) -> dict:
        o = self.get_object(tag).GetAsObject()
        ph = o.Phases[0]
        p = ph.Properties
        return {
            "T_K": float(p.temperature),
            "P_Pa": float(p.pressure),
            "molar_flow_mol_s": _f(p.molarflow),
            "mass_flow_kg_s": _f(p.massflow),
            "composition": {c.Name: float(c.MoleFraction) for c in ph.Compounds.Values},
        }


def _f(v) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0
