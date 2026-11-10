"""Process template library — canonical topologies the agent adapts.

Each template: block diagram, compounds, property package, key parameters,
and a worked dwsim_kit example. The LLM retrieves these instead of inventing
topology from scratch.
"""

TEMPLATES: dict[str, dict] = {
    "ammonia-synthesis-loop": {
        "description": "Haber-Bosch ammonia synthesis loop (fresh feed -> mixer -> "
                       "compressor -> converter -> cooler -> condenser flash -> recycle)",
        "compounds": ["Nitrogen", "Hydrogen", "Ammonia"],
        "property_package": "Peng-Robinson (PR)",
        "typical_conditions": {
            "loop_pressure_bar": "150-250",
            "reactor_T_C": "400-500",
            "condenser_T_C": "-30 to 0",
            "single_pass_conversion_pct": "15-25",
        },
        "topology": [
            "FreshFeed(N2/H2 ~1:3) -> Mixer",
            "Recycle stream -> Mixer",
            "Mixer -> Compressor (to loop pressure)",
            "Compressor -> ConversionReactor (N2 + 3 H2 -> 2 NH3, conversion on N2)",
            "Reactor -> Cooler (to condensation T)",
            "Cooler -> Flash (condense NH3)",
            "Flash.vapor -> Recycle -> Mixer (unreacted N2/H2)",
            "Flash.liquid -> Product (liquid NH3)",
        ],
        "example_script": '''from dwsim_agent.kit import Flowsheet

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

result = sim.solve()''',
    },

    "methanol-synthesis-loop": {
        "description": "Methanol synthesis from syngas (CO/CO2/H2), Cu-catalyst loop "
                       "(feed -> mixer -> compressor -> reactor -> cooler -> flash -> recycle)",
        "compounds": ["Carbon monoxide", "Carbon dioxide", "Hydrogen", "Methanol", "Water"],
        "property_package": "Peng-Robinson (PR)",
        "typical_conditions": {
            "loop_pressure_bar": "50-100",
            "reactor_T_C": "200-280",
            "condenser_T_C": "25-40",
            "single pass conversion_pct": "10-20",
        },
        "topology": [
            "FreshFeed(syngas CO/CO2/H2) -> Mixer",
            "Recycle -> Mixer",
            "Mixer -> Compressor (to 50-100 bar)",
            "Compressor -> ConversionReactor (CO + 2 H2 -> CH3OH; CO2 + 3 H2 -> CH3OH + H2O)",
            "Reactor -> Cooler (to ~30 C)",
            "Cooler -> Flash (condense methanol/water)",
            "Flash.vapor -> Recycle -> Mixer",
            "Flash.liquid -> Product (crude methanol)",
        ],
        "example_script": '''from dwsim_agent.kit import Flowsheet

sim = Flowsheet("methanol_loop")
sim.use_compounds(["Carbon monoxide", "Carbon dioxide", "Hydrogen", "Methanol", "Water"])
sim.use_property_package("Peng-Robinson (PR)")

sim.add_stream("FreshFeed", T_C=40, P_bar=30, mass_flow_kg_s=1.0,
               composition={"Carbon monoxide": 0.20, "Carbon dioxide": 0.05,
                            "Hydrogen": 0.70, "Methanol": 0.0, "Water": 0.05})

sim.add_unit("Mixer", "M1")
sim.add_unit("Compressor", "C1", P_out_bar=80)
sim.add_unit("ConversionReactor", "R1", T_out_C=250,
             reactions=[
               {"stoich": {"Carbon monoxide": -1, "Hydrogen": -2, "Methanol": 1},
                "base": "Carbon monoxide", "conversion_pct": 15, "phase": "Vapor"},
               {"stoich": {"Carbon dioxide": -1, "Hydrogen": -3,
                           "Methanol": 1, "Water": 1},
                "base": "Carbon dioxide", "conversion_pct": 10, "phase": "Vapor"}])
sim.add_unit("Cooler", "E1", T_out_C=40)
sim.add_unit("Flash", "V1", P_bar=79, T_C=40)
sim.add_unit("Splitter", "SP1", ratios=[0.95, 0.05])
sim.add_unit("Recycle", "RC1", max_iterations=300, tolerance=0.05)

sim.add_stream("Product")
sim.add_stream("Purge")
sim.connect("FreshFeed", "M1")
sim.connect("M1", "C1")
sim.connect("C1", "R1")
sim.connect("R1", "E1")
sim.connect("E1", "V1")
sim.connect("V1.liquid", "Product")
sim.connect("V1.vapor", "SP1")
sim.connect("SP1.out0", "RC1")
sim.connect("SP1.out1", "Purge")
sim.add_recycle("RC1", "M1")

result = sim.solve()''',
    },

    "simple-flash-separation": {
        "description": "Single flash drum separating a mixed feed into vapor and "
                       "liquid products (e.g. partial condensation, knock-out drum)",
        "compounds": "depends on feed",
        "property_package": "Peng-Robinson (PR) for hydrocarbons / NRTL for polar",
        "typical_conditions": {"P": "at or below feed bubble pressure",
                                "T": "between bubble and dew point"},
        "topology": [
            "Feed -> Flash",
            "Flash.vapor -> VaporProduct",
            "Flash.liquid -> LiquidProduct",
        ],
        "example_script": '''from dwsim_agent.kit import Flowsheet

sim = Flowsheet("flash_sep")
sim.use_compounds(["Methane", "Propane", "N-butane"])
sim.use_property_package("Peng-Robinson (PR)")

sim.add_stream("Feed", T_C=25, P_bar=10, mass_flow_kg_s=1.0,
               composition={"Methane": 0.3, "Propane": 0.4, "N-butane": 0.3})

sim.add_unit("Flash", "V1", P_bar=5, T_C=25)

sim.add_stream("VaporProduct")
sim.add_stream("LiquidProduct")
sim.connect("Feed", "V1")
sim.connect("V1.vapor", "VaporProduct")
sim.connect("V1.liquid", "LiquidProduct")

result = sim.solve()''',
    },

    "gas-compression-train": {
        "description": "Multi-stage gas compression with intercoolers "
                       "(suction -> compressor -> cooler -> ... -> discharge)",
        "compounds": "depends on gas",
        "property_package": "Peng-Robinson (PR)",
        "typical_conditions": {"stage_pressure_ratio": "2-4",
                                "intercooler_T_C": "30-50"},
        "topology": [
            "Suction -> Compressor1 -> Cooler1 -> Compressor2 -> Cooler2 -> Discharge",
        ],
        "example_script": '''from dwsim_agent.kit import Flowsheet

sim = Flowsheet("compression_train")
sim.use_compounds(["Methane", "Ethane"])
sim.use_property_package("Peng-Robinson (PR)")

sim.add_stream("Suction", T_C=25, P_bar=10, mass_flow_kg_s=2.0,
               composition={"Methane": 0.8, "Ethane": 0.2})

sim.add_unit("Compressor", "K1", P_out_bar=30)
sim.add_unit("Cooler", "E1", T_out_C=40)
sim.add_unit("Compressor", "K2", P_out_bar=90)
sim.add_unit("Cooler", "E2", T_out_C=40)

sim.add_stream("Discharge")
sim.connect("Suction", "K1")
sim.connect("K1", "E1")
sim.connect("E1", "K2")
sim.connect("K2", "E2")
sim.connect("E2", "Discharge")

result = sim.solve()''',
    },

    "steam-methane-reforming": {
        "description": "SMR: steam + methane -> syngas over Ni catalyst "
                       "(feed mixer -> heater -> reformer -> cooler -> flash)",
        "compounds": ["Methane", "Water", "Carbon monoxide", "Carbon dioxide",
                      "Hydrogen"],
        "property_package": "Peng-Robinson (PR)",
        "typical_conditions": {
            "reformer_T_C": "800-900",
            "pressure_bar": "20-30",
            "steam_to_carbon_ratio": "3:1 molar",
        },
        "topology": [
            "Methane feed -> Mixer",
            "Steam feed -> Mixer",
            "Mixer -> Heater (to reforming T)",
            "Heater -> ConversionReactor (CH4 + H2O -> CO + 3 H2; "
            "CO + H2O -> CO2 + H2 water-gas shift)",
            "Reactor -> Cooler (syngas cooling)",
            "Cooler -> Flash (condense excess water)",
            "Flash.vapor -> SyngasProduct",
            "Flash.liquid -> WaterCondensate",
        ],
        "example_script": '''from dwsim_agent.kit import Flowsheet

sim = Flowsheet("smr")
sim.use_compounds(["Methane", "Water", "Carbon monoxide",
                   "Carbon dioxide", "Hydrogen"])
sim.use_property_package("Peng-Robinson (PR)")

sim.add_stream("CH4Feed", T_C=25, P_bar=25, mass_flow_kg_s=0.3,
               composition={"Methane": 1.0})
sim.add_stream("SteamFeed", T_C=300, P_bar=25, mass_flow_kg_s=0.5,
               composition={"Water": 1.0})

sim.add_unit("Mixer", "M1")
sim.add_unit("Heater", "H1", T_out_C=850)
sim.add_unit("ConversionReactor", "R1", T_out_C=850,
             reactions=[
               {"stoich": {"Methane": -1, "Water": -1,
                           "Carbon monoxide": 1, "Hydrogen": 3},
                "base": "Methane", "conversion_pct": 85, "phase": "Vapor"},
               {"stoich": {"Carbon monoxide": -1, "Water": -1,
                           "Carbon dioxide": 1, "Hydrogen": 1},
                "base": "Carbon monoxide", "conversion_pct": 40, "phase": "Vapor"}])
sim.add_unit("Cooler", "E1", T_out_C=40)
sim.add_unit("Flash", "V1", P_bar=24, T_C=40)

sim.add_stream("Syngas")
sim.add_stream("Condensate")
sim.connect("CH4Feed", "M1")
sim.connect("SteamFeed", "M1")
sim.connect("M1", "H1")
sim.connect("H1", "R1")
sim.connect("R1", "E1")
sim.connect("E1", "V1")
sim.connect("V1.vapor", "Syngas")
sim.connect("V1.liquid", "Condensate")

result = sim.solve()''',
    },
}


def find_template(query: str) -> list[dict]:
    """Keyword search over the template library."""
    q = query.lower()
    hits = []
    for tid, t in TEMPLATES.items():
        text = (tid + " " + t["description"]).lower()
        if any(w in text for w in q.split()):
            hits.append({"id": tid, "description": t["description"],
                         "compounds": t["compounds"],
                         "property_package": t["property_package"],
                         "topology": t["topology"]})
    return hits


def get_template(tid: str) -> dict | None:
    return TEMPLATES.get(tid)
