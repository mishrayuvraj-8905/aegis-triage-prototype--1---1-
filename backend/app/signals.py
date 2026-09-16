"""PatientSignals: the shared input contract for every scoring approach
(rules engine, ML model, NEWS2). Kept in its own module so the rules engine
and the ML layer can both depend on it without importing each other."""
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class PatientSignals:
    """Everything the scoring layer can see about a patient at analysis time."""
    chief_complaint: str = ""
    hr: Optional[int] = None
    bp_sys: Optional[int] = None
    bp_dia: Optional[int] = None
    rr: Optional[int] = None
    spo2: Optional[int] = None
    temp: Optional[float] = None
    age: Optional[int] = None
    unconscious: bool = False
    non_verbal: bool = False
    pediatric: bool = False
    known_conditions: List[str] = field(default_factory=list)
    medications: List[str] = field(default_factory=list)
    prior_ed_visits: Optional[int] = None
    last_vitals_trend: Optional[str] = None  # "worsening" / "stable" / "improving"


def signals_from_patient(p) -> PatientSignals:
    """Build PatientSignals from a Patient ORM row (or any object with matching attrs)."""
    return PatientSignals(
        chief_complaint=p.chief_complaint or "",
        hr=p.hr, bp_sys=p.bp_sys, bp_dia=p.bp_dia, rr=p.rr, spo2=p.spo2, temp=p.temp,
        age=p.age,
        unconscious=bool(p.unconscious),
        non_verbal=bool(p.non_verbal),
        pediatric=bool(p.pediatric) or (p.age is not None and p.age < 18),
        known_conditions=p.known_conditions or [],
        medications=p.medications or [],
        prior_ed_visits=p.prior_ed_visits,
        last_vitals_trend=p.last_vitals_trend,
    )
