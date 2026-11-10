"""Introspect DWSIM reaction manager for conversion reactions."""
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

from DWSIM.SharedClasses import ReactorManager
print("=== ReactorManager contents ===")
print([n for n in dir(ReactorManager) if not n.startswith("_")])

print("\n=== Reaction class fields ===")
r = ReactorManager.Reaction()
rf = [n for n in dir(r) if not n.startswith("_") and not n.startswith("get_") and not n.startswith("set_")]
for n in sorted(rf):
    print(" ", n)

print("\n=== ReactionType enum ===")
print([n for n in dir(ReactorManager.Enums.ReactionType) if not n.startswith("_")])

print("\n=== ReactionSet class fields ===")
rs = ReactorManager.ReactionSet()
print([n for n in dir(rs) if not n.startswith("_") and not n.startswith("get_") and not n.startswith("set_")])
