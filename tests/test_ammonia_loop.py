"""Milestone 0b: simplified ammonia synthesis loop, end-to-end via DWSIM Automation.

FreshFeed -> Mixer <- RecOut(recycle) ; Mixer -> Comp -> Reactor -> Cooler -> Flash
Flash vapor -> Recycle -> back to Mixer ; Flash liquid -> Product

N2 + 3 H2 -> 2 NH3, 25% conversion on N2, PR EOS, 200 bar loop.
"""
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
from DWSIM.UnitOperations.Reactors import OperationMode as RxMode
from System.Collections.Generic import Dictionary
from System import String, Double

auto = Automation3()
sim = auto.CreateFlowsheet()

for name in ["Nitrogen", "Hydrogen", "Ammonia"]:
    sim.AddCompound(name)
sim.CreateAndAddPropertyPackage("Peng-Robinson (PR)")

# ---- reaction: N2 + 3 H2 -> 2 NH3, 25% conversion on N2 ----
stoich = Dictionary[String, Double]()
stoich.Add("Nitrogen", -1.0)
stoich.Add("Hydrogen", -3.0)
stoich.Add("Ammonia", 2.0)
rxn = sim.CreateConversionReaction("NH3_conv", "N2+3H2->2NH3", stoich,
                                   "Nitrogen", "Vapor", "25")
sim.AddReaction(rxn)
sim.AddReactionToSet(rxn.ID, "DefaultSet", True, 0)

# ---- objects ----
def add(ot, tag):
    return sim.AddObject(ot, 0, 0, tag)

def stream(tag, T=None, P=None, massflow=None, comp=None):
    s = add(ObjectType.MaterialStream, tag)
    if T is not None:
        ph = s.GetAsObject().Phases[0]
        ph.Properties.temperature = T
        ph.Properties.pressure = P
        ph.Properties.massflow = massflow
        for cname, frac in comp.items():
            ph.Compounds[cname].MoleFraction = frac
    return s

# feed: stoich N2/H2 1:3, 0.85 kg/s (~100 mol/s)
feed  = stream("FreshFeed", T=298.15, P=1e5, massflow=0.85,
               comp={"Nitrogen": 0.25, "Hydrogen": 0.75, "Ammonia": 0.0})
mix    = add(ObjectType.NodeIn, "Mixer")
mixout = stream("MixOut")
comp   = add(ObjectType.Compressor, "Comp")
compout = stream("CompOut")
rxr    = add(ObjectType.RCT_Conversion, "Reactor")
rxout  = stream("RxOut")
rxout2 = stream("RxOut2")
cool   = add(ObjectType.Cooler, "Cooler")
coolout = stream("CoolOut")
flash  = add(ObjectType.Vessel, "Flash")
prod   = stream("Product")
rcvap  = stream("RcVap")
rec    = add(ObjectType.OT_Recycle, "Recycle")
recout = stream("RecOut")

def connect(src, dst, sp=0, dp=0):
    sim.ConnectObjects(src.GraphicObject, dst.GraphicObject, sp, dp)

connect(feed, mix, 0, 0)
connect(recout, mix, 0, 1)
connect(mix, mixout, 0, 0)
connect(mixout, comp, 0, 0)
connect(comp, compout, 0, 0)
connect(compout, rxr, 0, 0)
connect(rxr, rxout, 0, 0)
connect(rxr, rxout2, 1, 0)       # reactor requires BOTH outlets connected
connect(rxout, cool, 0, 0)
connect(cool, coolout, 0, 0)
connect(coolout, flash, 0, 0)
connect(flash, rcvap, 0, 0)       # vapor -> recycle
connect(rcvap, rec, 0, 0)
connect(rec, recout, 0, 0)
connect(flash, prod, 1, 0)        # liquid -> product

# ---- unit specs ----
from System import Enum as SysEnum

comp.GetAsObject().POut = 200e5              # 200 bar discharge (CalcMode=OutletPressure default)

rxr_o = rxr.GetAsObject()
rxr_o.ReactionSetID = "DefaultSet"
rxr_o.ReactorOperationMode = RxMode.OutletTemperature
rxr_o.OutletTemperature = 723.15            # 450 C

cool_o = cool.GetAsObject()
CalcModeType = cool_o.CalcMode.GetType()
cool_o.CalcMode = SysEnum.Parse(CalcModeType, "OutletTemperature")
cool_o.OutletTemperature = 263.15           # -10 C
cool_o.PressureDrop = 0

flash.GetAsObject().FlashPressure = 199e5  # 199 bar

# ---- solve ----
print("\n=== SOLVE ===")
errors = auto.CalculateFlowsheet4(sim)
print("errors:", errors.Count if errors is not None else "None")
if errors:
    for e in errors:
        print("  ERR:", e.Message[:300])
print("Solved:", sim.Solved)

for tag in ["FreshFeed", "RxOut", "Product", "RecOut"]:
    try:
        s = sim.GetFlowsheetSimulationObject(tag).GetAsObject()
        p = s.Phases[0].Properties
        xf = {c.Name: round(c.MoleFraction, 4) for c in s.Phases[0].Compounds.Values}
        print(f"{tag}: T={p.temperature:.2f} K, P={p.pressure:.3e} Pa, n={p.molarflow:.2f} mol/s, m={p.massflow:.4f} kg/s, x={xf}")
    except Exception as e:
        print(f"{tag}: read error {e}")
