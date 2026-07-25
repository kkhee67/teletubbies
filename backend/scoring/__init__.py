"""Public interface for the data-analysis and risk-rule module."""

from .risk_rules import (
    RISK_RULES_VERSION,
    analyze_property,
    calculate_deposit_ratio,
    determine_risk_stage,
)
from .service import analyze_sample, list_sample_properties

__all__ = [
    "RISK_RULES_VERSION",
    "analyze_property",
    "calculate_deposit_ratio",
    "determine_risk_stage",
    "analyze_sample",
    "list_sample_properties",
]
