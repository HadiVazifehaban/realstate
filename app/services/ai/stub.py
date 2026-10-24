"""AI engine interfaces -- *stubbed* for the commercial (deterministic) release.

The commercial build ships with ``FEATURE_FLAG_AI_ENGINE = False``.  These
stubs define the contract future AI modules must implement while guaranteeing
that no non-deterministic processing runs in production today.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class AiDisabledError(RuntimeError):
    """Raised when an AI feature is invoked while the engine is disabled."""


@dataclass
class AiPredictionResult:
    label: str = ""
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    ai_enabled: bool = False


class AiEngineStub:
    """No-op AI engine used until the feature flag is switched on."""

    def __init__(self, *, enabled: bool = False) -> None:
        self.enabled = enabled

    def _guard(self) -> None:
        if not self.enabled:
            raise AiDisabledError(
                "AI engine is disabled (FEATURE_FLAG_AI_ENGINE=False). "
                "Current release performs deterministic spatial matching only."
            )

    # -- Ready-to-implement interfaces -----------------------------------------
    def describe_property(self, payload: dict[str, Any]) -> AiPredictionResult:
        """Generate a marketing description for a listing (LLM hook)."""
        self._guard()
        raise NotImplementedError  # pragma: no cover - future work

    def score_demand_match(self, demand: dict[str, Any], prop: dict[str, Any]) -> AiPredictionResult:
        """Learned re-ranking on top of the deterministic score."""
        self._guard()
        raise NotImplementedError  # pragma: no cover - future work

    def price_estimate(self, payload: dict[str, Any]) -> AiPredictionResult:
        """Automated valuation model (AVM) hook."""
        self._guard()
        raise NotImplementedError  # pragma: no cover - future work
