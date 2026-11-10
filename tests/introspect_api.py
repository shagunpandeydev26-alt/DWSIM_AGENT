"""Introspect DWSIM Automation API surface for v8.8.2."""
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
auto = Automation3()
sim = auto.CreateFlowsheet()

print("=== IFlowsheet methods (filtered) ===")
names = [n for n in dir(sim) if not n.startswith("_")]
interesting = [n for n in names if any(k in n.lower() for k in
              ("add", "connect", "object", "compound", "propertypackage", "prop", "calc", "solve", "save", "insert"))]
for n in sorted(interesting):
    print(" ", n)

print("\n=== AddObject signature ===")
import inspect
print(sim.AddObject.__doc__ if hasattr(sim.AddObject, "__doc__") else "?")

print("\n=== SelectedCompounds / PropertyPackages ===")
print("has SelectedCompounds:", hasattr(sim, "SelectedCompounds"))
print("has PropertyPackages:", hasattr(sim, "PropertyPackages"))
pp = sim.PropertyPackages
print("pp count:", pp.Count)
for p in list(pp.Keys)[:30]:
    print("  pp:", p)
