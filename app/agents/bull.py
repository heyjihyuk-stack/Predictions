"""Bull analyst agent — focuses on upside opportunities and growth catalysts."""

from app.agents.base import BaseAnalyst


class BullAnalyst(BaseAnalyst):
    name = "Bull Analyst"
    prompt_file = "bull.txt"
