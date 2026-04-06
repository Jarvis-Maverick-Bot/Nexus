"""
langgraph_engine.nodes.viper_qa — Viper QA stage node

QA stage: performs QA work, signals done.

For QA: next_stage is "QA" (terminal) — when QA advances, workitem is complete.
"""

from gov_langgraph.langgraph_engine.nodes.viper_ba import make_viper_node

viper_qa_node = make_viper_node("QA", "QA", "viper_qa")
