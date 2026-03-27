"""Macro analyst agent — focuses on macroeconomic trends and monetary policy."""

from app.agents.base import BaseAnalyst


class MacroAnalyst(BaseAnalyst):
    name = "Macro Analyst"
    prompt_file = "macro.txt"
