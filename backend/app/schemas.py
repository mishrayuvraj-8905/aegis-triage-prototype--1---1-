from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, field_serializer


def _as_utc_iso(dt: Optional[datetime]) -> Optional[str]:
    """SQLite stores naive datetimes (our code always writes UTC into them),
    but a timezone-less ISO string gets parsed as *local* time by JS's
    Date() constructor in the browser. Explicitly stamp UTC on the way out
    so the frontend's clock math is correct regardless of the user's
    timezone."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


class VitalsIn(BaseModel):
    hr: Optional[int] = None
    bp_sys: Optional[int] = None
    bp_dia: Optional[int] = None
    rr: Optional[int] = None
    spo2: Optional[int] = None
    temp: Optional[float] = None


class PatientCreate(BaseModel):
    name: str
    age: Optional[int] = None
    sex: Optional[str] = None
    chief_complaint: str = ""
    vitals: VitalsIn = VitalsIn()
    unconscious: bool = False
    non_verbal: bool = False
    pediatric: bool = False
    ehr_match_requested: bool = False
    dob: Optional[str] = None  # used only to look up the fake EHR


class ConfirmIn(BaseModel):
    acknowledged: bool = False


class OverrideIn(BaseModel):
    to_tier: int
    reason: str
    acknowledged: bool = False


class EscalateIn(BaseModel):
    reason: str


class TriageEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    patient_id: str
    timestamp: datetime
    actor: str
    action: str
    from_tier: Optional[int] = None
    to_tier: Optional[int] = None
    reason: Optional[str] = None
    confidence: Optional[float] = None

    @field_serializer("timestamp")
    def _ser_timestamp(self, dt: datetime, _info):
        return _as_utc_iso(dt)


class PatientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    age: Optional[int] = None
    sex: Optional[str] = None
    arrival_time: datetime
    chief_complaint: str
    hr: Optional[int] = None
    bp_sys: Optional[int] = None
    bp_dia: Optional[int] = None
    rr: Optional[int] = None
    spo2: Optional[int] = None
    temp: Optional[float] = None
    unconscious: bool
    non_verbal: bool
    pediatric: bool
    ehr_matched: bool
    known_conditions: List[str] = []
    medications: List[str] = []
    prior_ed_visits: Optional[int] = None
    last_vitals_trend: Optional[str] = None
    current_esi_tier: Optional[int] = None
    ai_suggested_tier: Optional[int] = None
    ai_confidence: Optional[float] = None
    ai_reason: Optional[str] = None
    ai_resource_path: Optional[str] = None
    ai_suggested_orders: List[str] = []
    ai_model_tier: Optional[int] = None
    ai_model_confidence: Optional[float] = None
    status: str
    last_rechecked_at: datetime
    recheck_interval_minutes: int
    flags: List[str] = []
    ack_required: bool
    acknowledged: bool

    @field_serializer("arrival_time", "last_rechecked_at")
    def _ser_dt(self, dt: datetime, _info):
        return _as_utc_iso(dt)


class PatientDetailOut(PatientOut):
    events: List[TriageEventOut] = []


class AnalyzePreviewOut(BaseModel):
    suggested_tier: int
    confidence: float
    confidence_label: str
    reason: str
    resource_path: str
    recheck_interval_minutes: int
    flags: List[str]
    ack_required: bool
    signal_trace: List[str]


class EHRLookupOut(BaseModel):
    matched: bool
    record: Optional[dict] = None
