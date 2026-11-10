"""Milestone 0b step 1: minimal flash test — N2/H2/NH3 feed -> Flash vessel."""
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

# compounds
for name in ["Nitrogen", "Hydrogen", "Ammonia"]:
    sim.AddCompound(name)
print("compounds added:", list(sim.SelectedCompounds.Keys))

# property package — check what AddPropertyPackage takes
try:
    pp = sim.AddPropertyPackage("Peng-Robinson (PR)")
    print("AddPropertyPackage(str) OK ->", pp)
except Exception as e:
    print("AddPropertyPackage(str) failed:", e)

print("pp count now:", sim.PropertyPackages.Count)

# objects
feed = sim.AddObject(ObjectType.MaterialStream, 50, 100, "Feed")
flash = sim.AddObject(ObjectType.Vessel, 150, 100, "Flash")
vap  = sim.AddObject(ObjectType.MaterialStream, 250, 60,  "Vapor")
liq  = sim.AddObject(ObjectType.MaterialStream, 250, 160, "Liquid")
print("objects added:", list(sim.SimulationObjects.Keys))

# inspect material stream API
print("\n=== feed stream methods (filtered) ===")
ms = sim.GetFlowsheetSimulationObject("Feed")
cands = [n for n in dir(ms) if any(k in n.lower() for k in
          ("set", "getproperty", "phase", "flow", "compound"))]
for n in sorted(cands)[:60]:
    print(" ", n)
