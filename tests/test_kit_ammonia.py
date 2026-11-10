"""Test the dwsim_kit by building the ammonia loop declaratively."""
import sys
sys.path.insert(0, r"C:\Users\AMAN\Desktop\shagun1")

from dwsim_agent.kit import Flowsheet

sim = Flowsheet("ammonia_loop")

sim.use_compounds(["Nitrogen", "Hydrogen", "Ammonia"])
sim.use_property_package("Peng-Robinson (PR)")

sim.add_stream("FreshFeed", T_C=25, P_bar=1, mass_flow_kg_s=0.85,
               composition={"Nitrogen": 0.25, "Hydrogen": 0.75})

sim.add_unit("Mixer", "M1")
sim.add_unit("Compressor", "C1", P_out_bar=200)
sim.add_unit("ConversionReactor", "R1",
             T_out_C=450,
             reactions=[{"stoich": {"Nitrogen": -1, "Hydrogen": -3, "Ammonia": 2},
                         "base": "Nitrogen", "conversion_pct": 25, "phase": "Vapor"}])
sim.add_unit("Cooler", "E1", T_out_C=-10)
sim.add_unit("Flash", "V1", P_bar=199, T_C=-10)
sim.add_unit("Recycle", "RC1")

sim.connect("FreshFeed", "M1")
sim.connect("M1", "C1")
sim.connect("C1", "R1")
sim.connect("R1", "E1")
sim.connect("E1", "V1")
sim.add_stream("Product")           # product stream
sim.connect("V1.liquid", "Product") # flash liquid -> product
sim.connect("V1.vapor", "RC1")      # flash vapor -> recycle
sim.add_recycle("RC1", "M1")        # recycle back to mixer

print("validate:", sim.validate())
result = sim.solve()
print("converged:", result.converged)
if result.errors:
    print("errors:", result.errors)

for tag in ["FreshFeed", "V1.vapor", "V1.liquid"]:
    try:
        s = result.stream(tag)
        print(f"{tag}: T={s['T_K']-273.15:.1f}C P={s['P_Pa']/1e5:.0f}bar "
              f"m={s['mass_flow_kg_s']:.3f}kg/s "
              f"x={ {k: round(v,4) for k,v in s['composition'].items()} }")
    except Exception as e:
        print(f"{tag}: {e}")

print("mass balance:", result.mass_balance())
