"""Multi-agent simulation orchestrator."""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

from app.agents import BearAnalyst, BullAnalyst, GeopoliticalAnalyst, MacroAnalyst, Moderator
from app.models.domain import AnalystView, Article, Entity

logger = logging.getLogger(__name__)


@dataclass
class SimulationResult:
    views: list[AnalystView]
    synthesis: str


def run_simulation(articles: list[Article], entities: list[Entity]) -> SimulationResult:
    """Run all analyst agents in parallel, then synthesize with the moderator."""
    analysts = [
        BullAnalyst(),
        BearAnalyst(),
        GeopoliticalAnalyst(),
        MacroAnalyst(),
    ]

    views: list[AnalystView] = []

    # Run analysts in parallel
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(analyst.analyze, articles, entities): analyst
            for analyst in analysts
        }
        for future in as_completed(futures):
            analyst = futures[future]
            try:
                view = future.result()
                views.append(view)
                logger.info("%s completed: %s (%.0f%% confidence)",
                           analyst.name, view.stance, view.confidence * 100)
            except Exception as e:
                logger.error("Agent %s failed: %s", analyst.name, e)
                views.append(
                    AnalystView(
                        analyst=analyst.name,
                        stance="neutral",
                        prediction=f"Analysis unavailable: {e}",
                        confidence=0.0,
                        reasoning="Agent failed to produce analysis.",
                    )
                )

    # Synthesize with moderator
    moderator = Moderator()
    synthesis = moderator.synthesize(views)

    return SimulationResult(views=views, synthesis=synthesis)
