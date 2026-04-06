"""
langgraph_engine.nodes.viper_sa — Viper SA stage node

SA stage: performs SA work, signals DEV-ready.
"""

from gov_langgraph.langgraph_engine.nodes.viper_ba import make_viper_node

viper_sa_node = make_viper_node("SA", "DEV", "viper_sa")
