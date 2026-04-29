"""
Lazy tool exports.
"""

from importlib import import_module

__all__ = [
    "retrieve_knowledge",
    "get_current_time",
]


def __getattr__(name):
    if name == "retrieve_knowledge":
        return import_module("app.tools.knowledge_tool").retrieve_knowledge
    if name == "get_current_time":
        return import_module("app.tools.time_tool").get_current_time
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
