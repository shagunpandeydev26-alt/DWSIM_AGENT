"""Milestone 0b step 5: direct attribute specs + error capture."""
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

sim.ConnectObjects(feed.GraphicObject, flash.GraphicObject, 0, 0)
sim.ConnectObjects(flash.GraphicObject, vap.GraphicObject, 0, 0)
sim.ConnectObjects(flash.GraphicObject, liq.GraphicObject, 1, 0)

# spec the feed via DIRECT attributes
ms = feed.GetAsObject()
ph0 = ms.Phases[0]
ph0.Properties.temperature = 298.15
ph0.Properties.pressure = 200e5
ph0.Properties.molarflow = 100.0
comp = {"Nitrogen": 0.225, "Hydrogen": 0.675, "Ammonia": 0.10}
for cname, frac in comp.items():
    ph0.Compounds[cname].MoleFraction = frac
print("feed specs set:", ph0.Properties.temperature, ph0.Properties.pressure, ph0.Properties.molarflow)

f = flash.GetAsObject()
f.FlashPressure = 200e5
print("vessel specs set:", f.FlashPressure)

print("\n=== SOLVE ===")
sim.RequestCalculation()
print("Solved:", sim.Solved)

# capture errors/messages from objects
for tag in ["Feed", "Flash", "Vapor", "Liquid"]:
    o = sim.GetFlowsheetSimulationObject(tag)
    err = o.ErrorMessage
    calc = o.Calculated
    print(f"{tag}: calculated={calc}, error={err!r}")

for tag in ["Feed", "Vapor", "Liquid"]:
    s = sim.GetFlowsheetSimulationObject(tag).GetAsObject()
    p = s.Phases[0].Properties
    print(f"\n{tag}: T={p.temperature:.2f} K, P={p.pressure:.3e} Pa, mflow={p.massflow:.4f} kg/s")
    xf = {c.Name: round(c.MoleFraction, 4) for c in s.Phases[0].Compounds.Values}
    print("  mole fracs:", xf)
