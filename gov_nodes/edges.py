# LangGraph Edges Definition
from typing import Literal


def route_after_maverick(state: dict) -> Literal["viper_ba", "halted"]:
    """
    Route after Maverick evaluation.
    """
    if state.get("pending_halt"):
        return "halted"
    return "viper_ba"


def route_after_qa(state: dict) -> Literal["nova", "halted"]:
    """
    Route after QA.
    """
    if state.get("qa_approved"):
        return "nova"
    return "halted"


def end_pipeline(state: dict) -> Literal["__end__"]:
    """
    End the pipeline.
    """
    return "__end__"
