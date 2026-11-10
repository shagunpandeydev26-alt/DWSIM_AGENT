"""Find ReactorOperationMode enum + current value."""
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
rxr = sim.AddObject(ObjectType.RCT_Conversion, 0, 0, "Rx")
ro = rxr.GetAsObject()
mode = ro.ReactorOperationMode
print("current mode:", mode, type(mode))
try:
    print("modes list:", ro.GetCalculationModes())
except Exception as e:
    print("GetCalculationModes err:", e)
print("mode type full name:", mode.GetType().FullName if hasattr(mode, "GetType") else "?")
try:
    print("enum members:", [n for n in dir(type(mode)) if not n.startswith("_")])
except Exception:
    pass
print("DONE")
