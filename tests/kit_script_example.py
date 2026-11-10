"""Example kit script used as executor test payload."""
from dwsim_agent.kit import Flowsheet

sim = Flowsheet("ammonia_loop")
sim.use_compounds(["Nitrogen", "Hydrogen", "Ammonia"])
sim.use_property_package("Peng-Robinson (PR)")
sim.add_stream("FreshFeed", T_C=25, P_bar=1, mass_flow_kg_s=0.85,
               composition={"Nitrogen": 0.25, "Hydrogen": 0.75})
sim.add_unit("Mixer", "M1")
sim.add_unit("Compressor", "C1", P_out_bar=200)
sim.add_unit("ConversionReactor", "R1", T_out_C=450,
             reactions=[{"stoich": {"Nitrogen": -1, "Hydrogen": -3, "Ammonia": 2},
                         "base": "Nitrogen", "conversion_pct": 25, "phase": "Vapor"}])
sim.add_unit("Cooler", "E1", T_out_C=-10)
sim.add_unit("Flash", "V1", P_bar=199, T_C=-10)
sim.add_unit("Recycle", "RC1")
sim.add_stream("Product")
sim.connect("FreshFeed", "M1")
sim.connect("M1", "C1")
sim.connect("C1", "R1")
sim.connect("R1", "E1")
sim.connect("E1", "V1")
sim.connect("V1.liquid", "Product")
sim.connect("V1.vapor", "RC1")
sim.add_recycle("RC1", "M1")
result = sim.solve()
