"""Turns a PatientSignals into a fixed-length numeric feature vector.

Deliberately reuses the same NEWS2 scorer and complaint matcher the rules
engine uses, rather than duplicating logic — the model and the rules engine
should see the same derived signals, they just combine them differently.
"""
import numpy as np

from ..signals import PatientSignals
from ..clinical_scores import compute_news2
from ..nlp import ComplaintMatcher

# Shared canonical phrase bank + matcher, built once at import time.
from ..scoring_phrases import RED_FLAG_TERMS, MODERATE_TERMS

_ALL_PHRASE_TIERS = {**RED_FLAG_TERMS, **MODERATE_TERMS}
_matcher = ComplaintMatcher(_ALL_PHRASE_TIERS)

FEATURE_NAMES = [
    "hr", "rr", "spo2", "bp_sys", "bp_dia", "temp_f", "age",
    "news2_score", "news2_critical",
    "complaint_tier",  # best fuzzy-matched tier from complaint text (6 = no match)
    "complaint_match_strength",
    "vitals_missing_count",
    "vague_complaint",
    "trend_worsening",
    "trend_improving",
    "pediatric",
    "unconscious_or_nonverbal",
    "prior_ed_visits",
]


def _missing_count(s: PatientSignals) -> int:
    return sum(1 for v in [s.hr, s.rr, s.spo2, s.bp_sys] if v is None)


def _is_vague(text: str) -> bool:
    t = (text or "").lower().strip()
    return len(t) < 6


def featurize(s: PatientSignals) -> np.ndarray:
    news2 = compute_news2(s.hr, s.rr, s.spo2, s.bp_sys, s.temp, s.last_vitals_trend)
    tier, matches = _matcher.best_tier(s.chief_complaint)
    complaint_tier = tier if tier is not None else 6
    match_strength = max((m.similarity for m in matches), default=0.0)

    vec = [
        s.hr if s.hr is not None else 85,
        s.rr if s.rr is not None else 16,
        s.spo2 if s.spo2 is not None else 98,
        s.bp_sys if s.bp_sys is not None else 120,
        s.bp_dia if s.bp_dia is not None else 78,
        s.temp if s.temp is not None else 98.6,
        s.age if s.age is not None else 40,
        news2.score,
        1.0 if news2.any_single_param_critical else 0.0,
        complaint_tier,
        match_strength,
        _missing_count(s),
        1.0 if _is_vague(s.chief_complaint) else 0.0,
        1.0 if s.last_vitals_trend == "worsening" else 0.0,
        1.0 if s.last_vitals_trend == "improving" else 0.0,
        1.0 if (s.pediatric or (s.age is not None and s.age < 18)) else 0.0,
        1.0 if (s.unconscious or s.non_verbal) else 0.0,
        s.prior_ed_visits if s.prior_ed_visits is not None else 0,
    ]
    return np.array(vec, dtype=float)
