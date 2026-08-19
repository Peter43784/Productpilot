"""Sourced RICE opportunity sizing.

RICE = (Reach x Impact x Confidence) / Effort.

Reach is derived from actual mention volume / segment share in the ingested corpus —
not gut feel. Every option ships with the inputs, a confidence label (Low/Med/High),
and the rationale tracing each number back to its source cluster.
"""
from __future__ import annotations

from .. import config

_IMPACT_SCALE = {"low": 1, "medium": 2, "high": 3}
_EFFORT_SCALE = {"small": 1, "medium": 2, "large": 3}


def _confidence_label(value: float) -> str:
    if value >= 0.8:
        return "High"
    if value >= 0.6:
        return "Med"
    return "Low"


def _confidence_from_sources(support_count: int, total_volume: int, saturated: bool) -> tuple[float, str]:
    if saturated:
        return 0.5, "Low"
    coverage = support_count / max(total_volume, 1)
    base = min(1.0, 0.5 + coverage)
    return round(base, 2), _confidence_label(base)


def rice_scores(
    themes: list[dict],
    total_volume: int,
    pm_input: str,
    saturated: bool = False,
    deprecation: bool = False,
) -> list[dict]:
    """Build RICE options from the theme clusters. Deterministic given the same themes."""
    ranked = sorted(themes, key=lambda t: t.get("frequency", 0), reverse=True)
    options = []
    for i, theme in enumerate(ranked[: config.TOP_OPTIONS]):
        freq = theme.get("frequency", 1)
        name = theme.get("name", f"option_{i}")
        reach = max(1, round(freq / max(total_volume, 1) * 1000))
        impact = _IMPACT_SCALE.get(theme.get("impact", "medium"), 2)
        effort = _EFFORT_SCALE.get(theme.get("effort", "medium"), 2)
        support_count = freq
        confidence, label = _confidence_from_sources(support_count, total_volume, saturated)
        rice = round((reach * impact * confidence) / effort, 2)
        options.append(
            {
                "name": name,
                "reach": reach,
                "impact": impact,
                "confidence": confidence,
                "confidence_label": label,
                "effort": effort,
                "rice": rice,
                "rationale": (
                    f"reach={freq} mentions / {total_volume} total; impact={impact}; effort={effort}; "
                    f"confidence={label} from source coverage"
                    + ("; market saturated — parity play" if saturated else "")
                ),
                "sources": theme.get("sources", []),
            }
        )
    return options
