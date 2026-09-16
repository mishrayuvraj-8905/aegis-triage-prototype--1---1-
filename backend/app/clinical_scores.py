"""
A NEWS2-inspired early warning score.

NEWS2 (National Early Warning Score 2, RCP UK) is standard clinical
methodology for detecting deterioration from a single set of vitals — it's
what a lot of real EWS/triage tooling is built on, not a hackathon
invention. We use a simplified version of its scoring bands here.

Separately, and this is the actual point of this module: `last_vitals_trend`
existed on PatientSignals from day one and was never read by analyze(). A
single-snapshot NEWS2 score is already useful, but the more clinically
meaningful signal is *directional* — two patients with an identical
snapshot NEWS2 of 4 are very different patients if one arrived at 6 and
is trending down, and the other arrived at 2 and is trending up. This
module scores the snapshot, then applies a trend adjustment.
"""
from dataclasses import dataclass, field
from typing import List, Optional


def _f_to_c(f: Optional[float]) -> Optional[float]:
    if f is None:
        return None
    return (f - 32) * 5.0 / 9.0


def _band_rr(rr):
    if rr is None:
        return None
    if rr <= 8:
        return 3
    if rr <= 11:
        return 1
    if rr <= 20:
        return 0
    if rr <= 24:
        return 2
    return 3


def _band_spo2(spo2):
    if spo2 is None:
        return None
    if spo2 <= 91:
        return 3
    if spo2 <= 93:
        return 2
    if spo2 <= 95:
        return 1
    return 0


def _band_sbp(sbp):
    if sbp is None:
        return None
    if sbp <= 90:
        return 3
    if sbp <= 100:
        return 2
    if sbp <= 110:
        return 1
    if sbp <= 219:
        return 0
    return 3


def _band_hr(hr):
    if hr is None:
        return None
    if hr <= 40:
        return 3
    if hr <= 50:
        return 1
    if hr <= 90:
        return 0
    if hr <= 110:
        return 1
    if hr <= 130:
        return 2
    return 3


def _band_temp_c(temp_c):
    if temp_c is None:
        return None
    if temp_c <= 35.0:
        return 3
    if temp_c <= 36.0:
        return 1
    if temp_c <= 38.0:
        return 0
    if temp_c <= 39.0:
        return 1
    return 2


@dataclass
class News2Result:
    score: int
    band: str  # "low" / "medium" / "high"
    any_single_param_critical: bool
    components_present: int
    components_total: int = 5
    trend_adjusted_band: str = ""
    trace: List[str] = field(default_factory=list)


def compute_news2(hr, rr, spo2, bp_sys, temp_f, trend: Optional[str] = None) -> News2Result:
    """Computes a simplified NEWS2 score from a single vitals snapshot, then
    nudges the band using the historical trend if one is known. Missing
    parameters are simply excluded from the score (they're handled
    separately by the analyze() missing-data escalation rule)."""
    temp_c = _f_to_c(temp_f)
    bands = {
        "RR": _band_rr(rr),
        "SpO2": _band_spo2(spo2),
        "SBP": _band_sbp(bp_sys),
        "HR": _band_hr(hr),
        "Temp": _band_temp_c(temp_c),
    }
    present = {k: v for k, v in bands.items() if v is not None}
    score = sum(present.values())
    any_critical = any(v == 3 for v in present.values())

    if score >= 7 or any_critical:
        band = "high"
    elif score >= 5:
        band = "medium"
    else:
        band = "low"

    trace = [f"NEWS2 snapshot score {score} ({', '.join(f'{k}={v}' for k, v in present.items())}) -> {band}"]

    trend_band = band
    if trend == "worsening":
        order = ["low", "medium", "high"]
        idx = min(order.index(band) + 1, len(order) - 1)
        trend_band = order[idx]
        if trend_band != band:
            trace.append(f"Vitals trend is 'worsening' -> band raised {band} -> {trend_band}")
        else:
            trace.append("Vitals trend is 'worsening' (already at highest band)")
    elif trend == "improving":
        trace.append("Vitals trend is 'improving' -- noted, but does not lower the score (never downgrade on a positive trend alone)")

    return News2Result(
        score=score,
        band=band,
        any_single_param_critical=any_critical,
        components_present=len(present),
        trend_adjusted_band=trend_band,
        trace=trace,
    )


NEWS2_BAND_TO_TIER = {"high": 1, "medium": 2, "low": None}
