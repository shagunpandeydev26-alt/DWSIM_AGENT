"""Milestone 0b step 3: full flash test — feed -> vessel -> vapor/liquid, solve, read results."""
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

feed = sim.AddObject(ObjectType.MaterialStream, 50, 100, "Feed")
flash = sim.AddObject(ObjectType.Vessel, 150, 100, "Flash")
vap  = sim.AddObject(ObjectType.MaterialStream, 250, 60,  "Vapor")
liq  = sim.AddObject(ObjectType.MaterialStream, 250, 160, "Liquid")

# connections (port indices: 0=in, 0/1=out)
sim.ConnectObjects(feed.GraphicObject, flash.GraphicObject, 0, 0)
sim.ConnectObjects(flash.GraphicObject, vap.GraphicObject, 0, 0)
sim.ConnectObjects(flash.GraphicObject, liq.GraphicObject, 1, 0)

# spec the feed: 25C, 200 bar, 1 kmol/s N2:H2 = 1:3 (stoich), 10% NH3
ms = feed.GetAsObject()
ms.SetPropertyValue("temperature", 298.15)
ms.SetPropertyValue("pressure", 200e5)
comp = {"Nitrogen": 0.225, "Hydrogen": 0.675, "Ammonia": 0.10}
ph0 = ms.Phases[0]
for cname, frac in comp.items():
    ph0.Compounds[cname].MoleFraction = frac
ph0.Properties.molarflow = 100.0  # mol/s

# spec the vessel: check what properties exist
f = flash.GetAsObject()
print("vessel type:", type(f).__name__)

print("\n=== vessel property list (SetPropertyValue candidates) ===")
try:
    props = f.GetProperties(None)
except Exception as e:
    print("GetProperties err:", e)
    props = []
for p in props:
    print(" ", p)

# try setting outlet pressure on vessel
for prop, val in [("pressure", 200e5)]:
    try:
        f.SetPropertyValue(prop, val)
        print(f"vessel SetPropertyValue({prop}) OK")
    except Exception as e:
        print(f"vessel SetPropertyValue({prop}) FAILED: {e}")

print("\n=== SOLVE ===")
sim.RequestCalculation()
print("Solved:", sim.Solved)

for tag in ["Vapor", "Liquid"]:
    s = sim.GetFlowsheetSimulationObject(tag).GetAsObject()
    p = s.Phases[0].Properties
    print(f"\n{tag}: T={p.temperature:.2f} K, P={p.pressure:.3e} Pa, mflow={p.massflow:.4f} kg/s")
    xf = {c.Name: round(c.MoleFraction, 4) for c in s.Phases[0].Compounds.Values}
    print("  mole fracs:", xf)
