"""Debug methanol recycle: once-through check + convergence history."""
import sys
sys.path.insert(0, r"C:\Users\AMAN\Desktop\shagun1")
sys.path.append(r"C:\Users\AMAN\AppData\Local\DWSIM")

from dwsim_agent.backend import DWSIMBackend, _load_assemblies
from dwsim_agent.kit import _to_K, _to_Pa, _PORT_NAMES
_load_assemblies()
from DWSIM.Interfaces.Enums.GraphicObjects import ObjectType
from DWSIM.UnitOperations.Reactors import OperationMode as RxMode
from System.Collections.Generic import Dictionary
from System import String, Double, Enum as SysEnum
from DWSIM.Automation import Automation3

be = DWSIMBackend()
sim = be.sim
OT = be.ObjectType

for c in ["Carbon monoxide", "Carbon dioxide", "Hydrogen", "Methanol", "Water"]:
    be.add_compound(c)
be.add_property_package("Peng-Robinson (PR)")

# once-through: feed -> reactor -> cooler -> flash (NO recycle)
feed = be.add_object(OT.MaterialStream, "Feed")
ph = feed.GetAsObject().Phases[0]
ph.Properties.temperature = _to_K(40)
ph.Properties.pressure = _to_Pa(30)
ph.Properties.massflow = 1.0
for c, f in {"Carbon monoxide": 0.20, "Carbon dioxide": 0.05,
             "Hydrogen": 0.70, "Methanol": 0.0, "Water": 0.05}.items():
    ph.Compounds[c].MoleFraction = f

comp = be.add_object(OT.Compressor, "C1")
comp.GetAsObject().POut = _to_Pa(80)
cout = be.add_object(OT.MaterialStream, "COut")

# reactions
stoich = Dictionary[String, Double]()
stoich.Add("Carbon monoxide", -1.0); stoich.Add("Hydrogen", -2.0); stoich.Add("Methanol", 1.0)
rxn1 = sim.CreateConversionReaction("rxn1", "r1", stoich, "Carbon monoxide", "Vapor", "15")
sim.AddReaction(rxn1)
stoich2 = Dictionary[String, Double]()
stoich2.Add("Carbon dioxide", -1.0); stoich2.Add("Hydrogen", -3.0)
stoich2.Add("Methanol", 1.0); stoich2.Add("Water", 1.0)
rxn2 = sim.CreateConversionReaction("rxn2", "r2", stoich2, "Carbon dioxide", "Vapor", "10")
sim.AddReaction(rxn2)
sim.AddReactionToSet(rxn1.ID, "DefaultSet", True, 0)
sim.AddReactionToSet(rxn2.ID, "DefaultSet", True, 1)

rxr = be.add_object(OT.RCT_Conversion, "R1")
ro = rxr.GetAsObject()
ro.ReactionSetID = "DefaultSet"
ro.ReactorOperationMode = RxMode.OutletTemperature
ro.OutletTemperature = _to_K(250)
rout = be.add_object(OT.MaterialStream, "ROut")
rout2 = be.add_object(OT.MaterialStream, "ROut2")

cool = be.add_object(OT.Cooler, "E1")
co = cool.GetAsObject()
co.CalcMode = SysEnum.Parse(co.CalcMode.GetType(), "OutletTemperature")
co.OutletTemperature = _to_K(40)
eout = be.add_object(OT.MaterialStream, "EOut")

flash = be.add_object(OT.Vessel, "V1")
fo = flash.GetAsObject()
fo.FlashPressure = _to_Pa(79)
fo.FlashTemperature = _to_K(40)
vap = be.add_object(OT.MaterialStream, "Vap")
liq = be.add_object(OT.MaterialStream, "Liq")

be.connect("Feed", "C1", 0, 0)
be.connect("C1", "COut", 0, 0)
be.connect("COut", "R1", 0, 0)
be.connect("R1", "ROut", 0, 0)
be.connect("R1", "ROut2", 1, 0)
be.connect("ROut", "E1", 0, 0)
be.connect("E1", "EOut", 0, 0)
be.connect("EOut", "V1", 0, 0)
be.connect("V1", "Vap", 0, 0)
be.connect("V1", "Liq", 1, 0)

errors = be.solve()
print("errors:", errors)
print("Solved:", be.solved)
for tag in ["Feed", "ROut", "Vap", "Liq"]:
    s = be.stream_summary(tag)
    print(f"{tag}: T={s['T_K']-273.15:.1f}C P={s['P_Pa']/1e5:.0f}bar m={s['mass_flow_kg_s']:.3f}")
    print("   x:", {k: round(v, 4) for k, v in s["composition"].items()})

# vapor fraction at flash
vs = be.get_object("Vap").GetAsObject()
ls = be.get_object("Liq").GetAsObject()
print("\nvapor flow:", vs.Phases[0].Properties.massflow, "liquid flow:", ls.Phases[0].Properties.massflow)
print("vapor fraction:", vs.Phases[0].Properties.massflow /
      max(vs.Phases[0].Properties.massflow + ls.Phases[0].Properties.massflow, 1e-9))
