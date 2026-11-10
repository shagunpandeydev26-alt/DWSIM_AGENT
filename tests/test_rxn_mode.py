"""Debug reactor calc mode + conversion reaction details."""
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
print("=== rxn fields ===")
for attr in ["ID", "Name", "ReactionType", "BaseCompound", "ConversionRate", "ReactionPhase", "StoichCoeffs"]:
    try:
        print(f"  {attr} = {getattr(rxn, attr)}")
    except Exception as e:
        print(f"  {attr} -> ERR {e}")

sim.AddReaction(rxn)
sim.AddReactionToSet(rxn.ID, "DefaultSet", True, 0)

rxr = sim.AddObject(ObjectType.RCT_Conversion, 0, 0, "Rx")
ro = rxr.GetAsObject()
print("\n=== reactor fields ===")
for attr in ["CalculationMode", "ReactionSetID", "ReactionSetName", "OutletTemperature", "ReactionsSequence"]:
    try:
        print(f"  {attr} = {getattr(ro, attr)}")
    except Exception as e:
        print(f"  {attr} -> ERR {e}")

print("\n=== set ReactionSetID then re-check ===")
ro.ReactionSetID = "DefaultSet"
print("  ReactionSetID =", ro.ReactionSetID)
print("  ReactionsSequence =", ro.ReactionsSequence)

print("\n=== reactor dir calc-mode candidates ===")
print([n for n in dir(ro) if "calc" in n.lower() or "mode" in n.lower() or "isotherm" in n.lower() or "adiab" in n.lower()])
print("DONE")
