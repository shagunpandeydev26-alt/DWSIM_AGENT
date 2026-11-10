"""Milestone 0b step 4: full flash test with correct vessel specs."""
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

# spec the feed
ms = feed.GetAsObject()
ms.SetPropertyValue("temperature", 298.15)
ms.SetPropertyValue("pressure", 200e5)
comp = {"Nitrogen": 0.225, "Hydrogen": 0.675, "Ammonia": 0.10}
ph0 = ms.Phases[0]
for cname, frac in comp.items():
    ph0.Compounds[cname].MoleFraction = frac
ph0.Properties.molarflow = 100.0

# spec the vessel
f = flash.GetAsObject()
f.FlashPressure = 200e5     # Pa
print("FlashPressure set:", f.FlashPressure)
print("FlashTemperature (0 = adiabatic):", f.FlashTemperature)

print("\n=== SOLVE ===")
sim.RequestCalculation()
print("Solved:", sim.Solved)

for tag in ["Feed", "Vapor", "Liquid"]:
    s = sim.GetFlowsheetSimulationObject(tag).GetAsObject()
    p = s.Phases[0].Properties
    print(f"\n{tag}: T={p.temperature:.2f} K, P={p.pressure:.3e} Pa, mflow={p.massflow:.4f} kg/s")
    xf = {c.Name: round(c.MoleFraction, 4) for c in s.Phases[0].Compounds.Values}
    print("  mole fracs:", xf)

# mass balance check
fv = sim.GetFlowsheetSimulationObject("Vapor").GetAsObject().Phases[0].Properties.massflow
fl = sim.GetFlowsheetSimulationObject("Liquid").GetAsObject().Phases[0].Properties.massflow
ff = sim.GetFlowsheetSimulationObject("Feed").GetAsObject().Phases[0].Properties.massflow
print(f"\nmass balance: in={ff:.4f}, out={fv+fl:.4f} kg/s, closure={100*abs(fv+fl-ff)/max(ff,1e-9):.2f}%")
