"""Deterministic finance engine module.

Contains pure functions for state calculations, financial position evaluation,
missing field checks, and blocking issue calculations. Zero imports from Pipecat,
FastAPI, or LLM SDKs.
"""

try:
    from agent.app.state import (
        SessionState,
        compute_blocking_issues,
        compute_cash_position,
        compute_missing_fields,
    )
except ImportError:  # pragma: no cover
    from app.state import (
        SessionState,
        compute_blocking_issues,
        compute_cash_position,
        compute_missing_fields,
    )

__all__ = [
    "SessionState",
    "compute_cash_position",
    "compute_missing_fields",
    "compute_blocking_issues",
]
