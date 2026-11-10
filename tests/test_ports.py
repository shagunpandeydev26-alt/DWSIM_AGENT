"""Check graphic ports of each unit op type."""
import sys

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

units = [
    (ObjectType.RCT_Conversion, "REACTOR"),
    (ObjectType.NodeIn, "MIXER"),
    (ObjectType.Compressor, "COMP"),
    (ObjectType.Cooler, "COOLER"),
    (ObjectType.Vessel, "VESSEL"),
    (ObjectType.OT_Recycle, "RECYCLE"),
]
for ot, label in units:
    o = sim.AddObject(ot, 0, 0, label)
    go = o.GraphicObject
    ins, outs = go.InputConnectors, go.OutputConnectors
    print(f"{label}: in={ins.Count} out={outs.Count}")
    for i in range(ins.Count):
        print(f"   in[{i}] type={ins[i].Type} connected={ins[i].IsAttached}")
    for i in range(outs.Count):
        print(f"   out[{i}] type={outs[i].Type} connected={outs[i].IsAttached}")
print("DONE")
