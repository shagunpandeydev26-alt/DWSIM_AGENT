"""End-to-end executor + verifier test (no LLM needed)."""
import sys
sys.path.insert(0, r"C:\Users\AMAN\Desktop\shagun1")

from dwsim_agent.executor import run_flowsheet_script
from dwsim_agent.verifier import verify, as_llm_message

script = open(r"C:\Users\AMAN\Desktop\shagun1\tests\kit_script_example.py", encoding="utf-8").read()
# strip the kit import — executor injects it
script = script.replace("from dwsim_agent.kit import Flowsheet", "")

env = run_flowsheet_script(script, "sandbox_test")
print("status:", env["status"], "| converged:", env.get("converged"))
print("mass balance:", env.get("mass_balance"))
v = verify(env)
print("verify passed:", v["passed"])
print(as_llm_message(v))
