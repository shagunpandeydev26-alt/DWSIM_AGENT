"""Introspect ammonia loop unit ops (compressor, cooler, reactor, recycle, mixer)."""
import sys, traceback

DWSIM_PATH = r"C:\Users\AMAN\AppData\Local\DWSIM"
sys.path.append(DWSIM_PATH)

import clr
for asm in ["DWSIM.Automation", "DWSIM.Interfaces", "DWSIM.SharedClasses",
            "DWSIM.Thermodynamics", "DWSIM.UnitOperations", "DWSIM.MathOps"]:
    try:
        clr.AddReference(asm)
    except Exception:
        pass

from DWSIM.Automation import Automation3
from DWSIM.Interfaces.Enums.GraphicObjects import ObjectType

auto = Automation3()
sim = auto.CreateFlowsheet()
for name in ["Nitrogen", "Hydrogen", "Ammonia"]:
    sim.AddCompound(name)
sim.CreateAndAddPropertyPackage("Peng-Robinson (PR)")

objs = [
    ("Comp", ObjectType.Compressor, "COMPRESSOR"),
    ("Cool", ObjectType.Cooler, "COOLER"),
    ("Rx",   ObjectType.RCT_Conversion, "CONV-REACTOR"),
    ("Rec",  ObjectType.OT_Recycle, "RECYCLE"),
    ("Mix",  ObjectType.NodeIn, "MIXER"),
]
for tag, ot, label in objs:
    try:
        obj = sim.AddObject(ot, 50, 100, tag)
        o = obj.GetAsObject()
        print(f"=== {label} -> {type(o).__name__} ===")
        cands = [n for n in dir(o) if any(k in n.lower() for k in
                  ("outlet", "pressur", "temperatur", "reaction", "efficien", "energy", "deltap"))]
        print("  ", sorted(set(cands))[:30])
    except Exception as e:
        print(f"=== {label} FAILED: {type(e).__name__}: {e}")
print("\nDONE")
