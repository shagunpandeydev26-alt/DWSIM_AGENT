"""Milestone 0b step 2: figure out property package + stream spec pattern."""
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

print("=== AvailablePropertyPackages ===")
for k in list(sim.AvailablePropertyPackages.Keys):
    print(" ", k)

print("\n=== CreateAndAddPropertyPackage try ===")
try:
    pp = sim.CreateAndAddPropertyPackage("Peng-Robinson (PR)")
    print("OK ->", pp)
    print("pp count:", sim.PropertyPackages.Count)
except Exception as e:
    print("failed:", type(e).__name__, e)

feed = sim.AddObject(ObjectType.MaterialStream, 50, 100, "Feed")
ms = sim.GetFlowsheetSimulationObject("Feed")

print("\n=== GetAsObject -> concrete stream ===")
mso = ms.GetAsObject()
print("type:", type(mso))
ph0 = mso.Phases[0]
print("phases count:", mso.Phases.Count)
print("phase0 props sample:", [n for n in dir(ph0.Properties) if any(
    k in n.lower() for k in ("temperature", "pressure", "massflow", "molarflow", "fraction"))][:20])
print("compounds in phase0:", [c.Name for c in ph0.Compounds.Values])

print("\n=== SetPropertyValue pattern ===")
try:
    ms.SetPropertyValue("temperature", 298.15)
    print("SetPropertyValue temperature OK")
    ms.SetPropertyValue("pressure", 101325)
    print("SetPropertyValue pressure OK")
except Exception as e:
    print("failed:", e)
