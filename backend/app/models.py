"""ORM models: Patient and TriageEvent (the audit log)."""
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Boolean, ForeignKey, Text, JSON
)
from sqlalchemy.orm import relationship

from .database import Base


def now_utc():
    return datetime.now(timezone.utc)


def gen_id():
    return str(uuid.uuid4())


class Patient(Base):
    __tablename__ = "patients"

    id = Column(String, primary_key=True, default=gen_id)
    name = Column(String, nullable=False)
    age = Column(Integer, nullable=True)
    sex = Column(String, nullable=True)

    arrival_time = Column(DateTime, default=now_utc)

    chief_complaint = Column(Text, nullable=False, default="")

    # Vitals
    hr = Column(Integer, nullable=True)  # heart rate
    bp_sys = Column(Integer, nullable=True)
    bp_dia = Column(Integer, nullable=True)
    rr = Column(Integer, nullable=True)  # respiratory rate
    spo2 = Column(Integer, nullable=True)
    temp = Column(Float, nullable=True)  # Fahrenheit

    # Flags relevant to forced escalation
    unconscious = Column(Boolean, default=False)
    non_verbal = Column(Boolean, default=False)
    pediatric = Column(Boolean, default=False)  # can also be inferred from age < 18

    # Simulated EHR match
    ehr_matched = Column(Boolean, default=False)
    known_conditions = Column(JSON, default=list)
    medications = Column(JSON, default=list)
    prior_ed_visits = Column(Integer, nullable=True)
    last_vitals_trend = Column(String, nullable=True)  # e.g. "worsening", "stable", "improving"

    # Triage state
    current_esi_tier = Column(Integer, nullable=True)  # nurse-confirmed, nullable until confirmed
    ai_suggested_tier = Column(Integer, nullable=True)
    ai_confidence = Column(Float, nullable=True)  # 0-1
    ai_reason = Column(Text, nullable=True)
    ai_resource_path = Column(String, nullable=True)
    ai_suggested_orders = Column(JSON, default=list)  # staged order-set suggestion for tier <=2
    ai_model_tier = Column(Integer, nullable=True)  # ML model's own vote, before blending with rules
    ai_model_confidence = Column(Float, nullable=True)

    status = Column(String, default="waiting")  # waiting / in_progress / seen
    last_rechecked_at = Column(DateTime, default=now_utc)
    recheck_interval_minutes = Column(Integer, default=60)

    flags = Column(JSON, default=list)  # e.g. ["low_confidence", "missing_data", "deteriorating"]

    ack_required = Column(Boolean, default=False)  # tier 1-2 suggestion needing explicit ack
    acknowledged = Column(Boolean, default=False)

    # Demo-only: when true, the Keep Watching job nudges this patient's vitals
    # to worsen slightly on each recheck tick, so a seeded "quietly
    # deteriorating" patient can be flagged live without manual intervention.
    sim_decline = Column(Boolean, default=False)

    events = relationship(
        "TriageEvent", back_populates="patient",
        cascade="all, delete-orphan", order_by="TriageEvent.timestamp"
    )


class TriageEvent(Base):
    __tablename__ = "triage_events"

    id = Column(String, primary_key=True, default=gen_id)
    patient_id = Column(String, ForeignKey("patients.id"), nullable=False)
    timestamp = Column(DateTime, default=now_utc)
    actor = Column(String, nullable=False)  # "AI" / "nurse"
    action = Column(String, nullable=False)  # suggested / confirmed / overridden / escalated / rechecked / flagged
    from_tier = Column(Integer, nullable=True)
    to_tier = Column(Integer, nullable=True)
    reason = Column(Text, nullable=True)
    confidence = Column(Float, nullable=True)

    patient = relationship("Patient", back_populates="events")
