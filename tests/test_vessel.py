"""Introspect Vessel unit op attributes."""
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
from DWSIM.SharedClasses.SystemsOfUnits import SI

auto = Automation3()
sim = auto.CreateFlowsheet()
for name in ["Nitrogen", "Hydrogen", "Ammonia"]:
    sim.AddCompound(name)
sim.CreateAndAddPropertyPackage("Peng-Robinson (PR)")

flash = sim.AddObject(ObjectType.Vessel, 150, 100, "Flash")
f = flash.GetAsObject()

print("=== Vessel properties via GetProperties(SI) ===")
su = SI()
try:
    props = f.GetProperties(su)
    for p in props:
        print(" ", p, "|", f.GetPropertyUnit(p, su))
except Exception as e:
    print("err:", e)

print("\n=== Vessel dir() outlet/pressure candidates ===")
cands = [n for n in dir(f) if any(k in n.lower() for k in ("outlet", "pressure", "delta", "flash"))]
for n in sorted(cands):
    print(" ", n)
