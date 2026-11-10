"""Find operation modes for compressor and cooler."""
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

for ot, label in [(ObjectType.Compressor, "COMPRESSOR"), (ObjectType.Cooler, "COOLER"), (ObjectType.Heater, "HEATER"), (ObjectType.Valve, "VALVE")]:
    o = sim.AddObject(ot, 0, 0, label)
    oo = o.GetAsObject()
    print(f"=== {label} ({type(oo).__name__}) ===")
    mode_attrs = [n for n in dir(oo) if "mode" in n.lower() and not n.startswith("_")]
    for m in mode_attrs:
        try:
            v = getattr(oo, m)
            print(f"  {m} = {v}", "| type:", type(v).__name__)
            if hasattr(v, "GetType"):
                print("     enum:", [n for n in dir(type(v)) if not n.startswith("_") and n[0].isupper()][:12])
        except Exception as e:
            print(f"  {m} -> ERR {e}")
    others = [n for n in dir(oo) if any(k in n.lower() for k in ("outletpressure", "pressureratio", "pressureincrease", "deltap")) and not n.startswith("_")]
    print("  spec attrs:", others)
print("DONE")
