"""Geopolitical analyst agent — focuses on international relations and political risk."""

from app.agents.base import BaseAnalyst


class GeopoliticalAnalyst(BaseAnalyst):
    name = "Geopolitical Analyst"
    prompt_file = "geopolitical.txt"
