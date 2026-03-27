"""Bear analyst agent — focuses on downside risks and threats."""

from app.agents.base import BaseAnalyst


class BearAnalyst(BaseAnalyst):
    name = "Bear Analyst"
    prompt_file = "bear.txt"
