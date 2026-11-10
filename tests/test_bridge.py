"""Milestone 0: DWSIM Automation bridge test via pythonnet."""
import sys, os

DWSIM_PATH = r"C:\Users\AMAN\AppData\Local\DWSIM"
sys.path.append(DWSIM_PATH)

import clr

for asm in [
    "DWSIM.Automation",
    "DWSIM.Interfaces",
    "DWSIM.SharedClasses",
    "DWSIM.Thermodynamics",
    "DWSIM.UnitOperations",
    "DWSIM.MathOps",
    "DWSIM.GlobalizationHelper",
]:
    try:
        clr.AddReference(asm)
        print(f"loaded: {asm}")
    except Exception as e:
        print(f"FAILED: {asm} -> {e}")

from DWSIM.Automation import Automation3

auto = Automation3()
print("Automation3 created OK")

# create empty flowsheet
sim = auto.CreateFlowsheet()
print(f"flowsheet created: {type(sim)}")

# list some available compounds
compounds = list(sim.AvailableCompounds.Keys)
print(f"available compounds: {len(compounds)}")
print("sample:", [c for c in compounds if "mmonia" in c or c in ("Nitrogen", "Hydrogen", "Methane", "Water")])

print("BRIDGE OK")
