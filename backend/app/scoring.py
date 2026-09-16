"""
Compatibility shim.

The scoring logic that used to live entirely in this file has been
decomposed into app/agents.py (SymptomExtractionAgent, RiskScoringAgent,
ResourcePlanningAgent + TriagePipeline orchestrator), with the NEWS2 trend
scoring in app/clinical_scores.py, the fuzzy complaint matching in
app/nlp.py, and the ML second-opinion model in app/ml/. This module just
re-exports the same names other modules already import, so nothing else
in the codebase needed to change.
"""
from .signals import PatientSignals, signals_from_patient  # noqa: F401
from .agents import (  # noqa: F401
    AnalyzeResult,
    Recommendation,
    analyze,
    recommend,
    analyze_and_recommend,
)
