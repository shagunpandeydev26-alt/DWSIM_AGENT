"""Debug: check IsAttached after ConnectObjects + add energy streams if needed."""
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
from System.Collections.Generic import Dictionary
from System import String, Double

auto = Automation3()
sim = auto.CreateFlowsheet()
for name in ["Nitrogen", "Hydrogen", "Ammonia"]:
    sim.AddCompound(name)
sim.CreateAndAddPropertyPackage("Peng-Robinson (PR)")

stoich = Dictionary[String, Double]()
stoich.Add("Nitrogen", -1.0)
stoich.Add("Hydrogen", -3.0)
stoich.Add("Ammonia", 2.0)
rxn = sim.CreateConversionReaction("NH3_conv", "N2+3H2->2NH3", stoich, "Nitrogen", "Vapor", "0.25")
sim.AddReaction(rxn)
sim.AddReactionToSet(rxn.ID, "DefaultSet", True, 0)

def add(ot, tag):
    return sim.AddObject(ot, 0, 0, tag)

fin = add(ObjectType.MaterialStream, "Fin")
rxr = add(ObjectType.RCT_Conversion, "Rx")
fout = add(ObjectType.MaterialStream, "Fout")
fout2 = add(ObjectType.MaterialStream, "Fout2")

sim.ConnectObjects(fin.GraphicObject, rxr.GraphicObject, 0, 0)
sim.ConnectObjects(rxr.GraphicObject, fout.GraphicObject, 0, 0)
sim.ConnectObjects(rxr.GraphicObject, fout2.GraphicObject, 1, 0)

print("after connect:")
ins, outs = rxr.GraphicObject.InputConnectors, rxr.GraphicObject.OutputConnectors
for i in range(ins.Count):
    print(f"  in[{i}]: attached={ins[i].IsAttached}, connobj={ins[i].AttachedConnector is not None}")
for i in range(outs.Count):
    ac = outs[i].AttachedConnector
    print(f"  out[{i}]: attached={outs[i].IsAttached}")

# spec + solve
ph = fin.GetAsObject().Phases[0]
ph.Properties.temperature = 298.15
ph.Properties.pressure = 200e5
ph.Properties.molarflow = 100.0
for c, f in {"Nitrogen": 0.25, "Hydrogen": 0.75, "Ammonia": 0.0}.items():
    ph.Compounds[c].MoleFraction = f

rxr_o = rxr.GetAsObject()
rxr_o.ReactionSetID = "DefaultSet"
rxr_o.OutletTemperature = 723.15

errors = auto.CalculateFlowsheet4(sim)
print("errors:", errors.Count if errors else 0)
if errors:
    for e in errors:
        print("  ERR:", e.Message[:300])
print("Solved:", sim.Solved)
p = fout.GetAsObject().Phases[0].Properties
print(f"Fout: T={p.temperature} K, n={p.molarflow} mol/s")
xf = {c.Name: c.MoleFraction for c in fout.GetAsObject().Phases[0].Compounds.Values}
print("x:", xf)
print("DONE")
