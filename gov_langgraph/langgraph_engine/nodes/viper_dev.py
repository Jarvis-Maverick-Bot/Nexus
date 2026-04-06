"""
langgraph_engine.nodes.viper_dev — Viper DEV stage node

DEV stage: performs DEV work, signals QA-ready.
"""

from gov_langgraph.langgraph_engine.nodes.viper_ba import make_viper_node

viper_dev_node = make_viper_node("DEV", "QA", "viper_dev")
