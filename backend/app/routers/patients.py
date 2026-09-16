from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..ehr_data import find_ehr_match
from ..scoring import analyze_and_recommend, signals_from_patient

router = APIRouter(prefix="/api/patients", tags=["patients"])


def _now():
    return datetime.now(timezone.utc)


def _run_pipeline_and_store(db: Session, patient: models.Patient, actor_note: str = None):
    """Stages 2 & 3: Analyze -> Recommend. Writes results onto the patient and
    logs an AI 'suggested' TriageEvent. Does not touch current_esi_tier —
    that only ever changes via an explicit nurse action."""
    signals = signals_from_patient(patient)
    analyzed, rec = analyze_and_recommend(signals)

    prev_suggested = patient.ai_suggested_tier

    patient.ai_suggested_tier = rec.suggested_tier
    patient.ai_confidence = rec.confidence
    patient.ai_reason = rec.reason
    patient.ai_resource_path = rec.resource_path
    patient.ai_suggested_orders = rec.suggested_orders
    patient.ai_model_tier = rec.model_tier
    patient.ai_model_confidence = rec.model_confidence
    patient.recheck_interval_minutes = rec.recheck_interval_minutes
    patient.last_rechecked_at = _now()

    flags = set(rec.flags)
    # Deterioration flag: only meaningful once a tier has been nurse-confirmed
    if (
        patient.current_esi_tier is not None
        and rec.suggested_tier < patient.current_esi_tier
    ):
        flags.add("deteriorating")
    patient.flags = sorted(flags)

    if rec.ack_required:
        patient.ack_required = True
        patient.acknowledged = False
    else:
        # Tier improved (or was never high-acuity) on this pass — don't leave
        # a stale ack requirement blocking the nurse for a suggestion that's
        # no longer current.
        patient.ack_required = False

    db.add(patient)

    event = models.TriageEvent(
        patient_id=patient.id,
        actor="AI",
        action="suggested" if prev_suggested is None else "rechecked",
        from_tier=prev_suggested,
        to_tier=rec.suggested_tier,
        reason=rec.reason,
        confidence=rec.confidence,
    )
    db.add(event)
    db.commit()
    db.refresh(patient)
    return patient, rec


@router.get("", response_model=List[schemas.PatientOut])
def list_patients(status: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(models.Patient)
    if status:
        q = q.filter(models.Patient.status == status)
    patients = q.all()

    def sort_key(p: models.Patient):
        deteriorating = 0 if "deteriorating" in (p.flags or []) else 1
        tier = p.current_esi_tier if p.current_esi_tier is not None else (p.ai_suggested_tier or 5)
        return (deteriorating, tier, p.arrival_time)

    return sorted(patients, key=sort_key)


@router.get("/{patient_id}", response_model=schemas.PatientDetailOut)
def get_patient(patient_id: str, db: Session = Depends(get_db)):
    patient = db.get(models.Patient, patient_id)
    if not patient:
        raise HTTPException(404, "Patient not found")
    return patient


@router.get("/ehr/lookup", response_model=schemas.EHRLookupOut, tags=["ehr"])
def ehr_lookup(name: str, dob: Optional[str] = None):
    rec = find_ehr_match(name, dob)
    if not rec:
        return schemas.EHRLookupOut(matched=False, record=None)
    return schemas.EHRLookupOut(matched=True, record=rec)


@router.post("", response_model=schemas.PatientDetailOut)
def create_patient(payload: schemas.PatientCreate, db: Session = Depends(get_db)):
    """Stage 1: Capture. Creates the patient, optionally pre-filling from the
    simulated EHR match, then immediately runs Analyze + Recommend (stage 2/3)."""
    ehr_fields = {}
    ehr_matched = False
    if payload.ehr_match_requested:
        rec = find_ehr_match(payload.name, payload.dob)
        if rec:
            ehr_matched = True
            ehr_fields = {
                "known_conditions": rec["known_conditions"],
                "medications": rec["medications"],
                "prior_ed_visits": rec["prior_ed_visits"],
                "last_vitals_trend": rec["last_vitals_trend"],
            }
            if payload.age is None:
                payload.age = rec["age"]
            if payload.sex is None:
                payload.sex = rec["sex"]

    patient = models.Patient(
        name=payload.name,
        age=payload.age,
        sex=payload.sex,
        chief_complaint=payload.chief_complaint,
        hr=payload.vitals.hr,
        bp_sys=payload.vitals.bp_sys,
        bp_dia=payload.vitals.bp_dia,
        rr=payload.vitals.rr,
        spo2=payload.vitals.spo2,
        temp=payload.vitals.temp,
        unconscious=payload.unconscious,
        non_verbal=payload.non_verbal,
        pediatric=payload.pediatric,
        ehr_matched=ehr_matched,
        status="waiting",
        **ehr_fields,
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)

    patient, _rec = _run_pipeline_and_store(db, patient)
    return patient


@router.post("/{patient_id}/acknowledge", response_model=schemas.PatientDetailOut)
def acknowledge(patient_id: str, db: Session = Depends(get_db)):
    """Nurse explicitly acknowledges a level 1-2 AI suggestion. Required before
    confirm/override will be accepted for those cases."""
    patient = db.get(models.Patient, patient_id)
    if not patient:
        raise HTTPException(404, "Patient not found")
    patient.acknowledged = True
    db.add(patient)
    event = models.TriageEvent(
        patient_id=patient.id, actor="nurse", action="acknowledged",
        from_tier=patient.current_esi_tier, to_tier=patient.ai_suggested_tier,
        reason="Nurse acknowledged high-acuity AI suggestion.",
    )
    db.add(event)
    db.commit()
    db.refresh(patient)
    return patient


def _require_ack_if_needed(patient: models.Patient, acknowledged_in_request: bool):
    if patient.ack_required and not patient.acknowledged and not acknowledged_in_request:
        raise HTTPException(
            400,
            "This is a Level 1-2 AI suggestion and requires explicit nurse "
            "acknowledgment before it can be confirmed or overridden.",
        )


@router.post("/{patient_id}/confirm", response_model=schemas.PatientDetailOut)
def confirm(patient_id: str, payload: schemas.ConfirmIn, db: Session = Depends(get_db)):
    """Stage 4: Nurse Decides — Confirm. Nurse accepts the AI-suggested tier."""
    patient = db.get(models.Patient, patient_id)
    if not patient:
        raise HTTPException(404, "Patient not found")
    _require_ack_if_needed(patient, payload.acknowledged)

    from_tier = patient.current_esi_tier
    patient.current_esi_tier = patient.ai_suggested_tier
    patient.acknowledged = True
    flags = [f for f in (patient.flags or []) if f != "deteriorating"]
    patient.flags = flags
    db.add(patient)

    event = models.TriageEvent(
        patient_id=patient.id, actor="nurse", action="confirmed",
        from_tier=from_tier, to_tier=patient.current_esi_tier,
        reason="Nurse confirmed AI-suggested tier.",
        confidence=patient.ai_confidence,
    )
    db.add(event)
    db.commit()
    db.refresh(patient)
    return patient


@router.post("/{patient_id}/override", response_model=schemas.PatientDetailOut)
def override(patient_id: str, payload: schemas.OverrideIn, db: Session = Depends(get_db)):
    """Stage 4: Nurse Decides — Override. Nurse picks a different tier and must
    give a one-line reason. Both AI and nurse tiers are stored in the audit log."""
    if payload.to_tier < 1 or payload.to_tier > 5:
        raise HTTPException(400, "Tier must be between 1 and 5")
    if not payload.reason or not payload.reason.strip():
        raise HTTPException(400, "Override requires a reason")

    patient = db.get(models.Patient, patient_id)
    if not patient:
        raise HTTPException(404, "Patient not found")
    _require_ack_if_needed(patient, payload.acknowledged)

    from_tier = patient.current_esi_tier
    patient.current_esi_tier = payload.to_tier
    patient.acknowledged = True
    flags = [f for f in (patient.flags or []) if f != "deteriorating"]
    patient.flags = flags
    db.add(patient)

    event = models.TriageEvent(
        patient_id=patient.id, actor="nurse", action="overridden",
        from_tier=patient.ai_suggested_tier, to_tier=payload.to_tier,
        reason=payload.reason,
        confidence=patient.ai_confidence,
    )
    db.add(event)
    db.commit()
    db.refresh(patient)
    return patient


@router.post("/{patient_id}/escalate", response_model=schemas.PatientDetailOut)
def escalate(patient_id: str, payload: schemas.EscalateIn, db: Session = Depends(get_db)):
    """Stage 4: Nurse Decides — Escalate. Flags the patient for immediate senior review."""
    if not payload.reason or not payload.reason.strip():
        raise HTTPException(400, "Escalation requires a reason")
    patient = db.get(models.Patient, patient_id)
    if not patient:
        raise HTTPException(404, "Patient not found")

    flags = set(patient.flags or [])
    flags.add("escalated")
    patient.flags = sorted(flags)
    patient.acknowledged = True
    db.add(patient)

    event = models.TriageEvent(
        patient_id=patient.id, actor="nurse", action="escalated",
        from_tier=patient.current_esi_tier, to_tier=patient.ai_suggested_tier,
        reason=payload.reason,
    )
    db.add(event)
    db.commit()
    db.refresh(patient)
    return patient


@router.post("/{patient_id}/seen", response_model=schemas.PatientDetailOut)
def mark_seen(patient_id: str, db: Session = Depends(get_db)):
    patient = db.get(models.Patient, patient_id)
    if not patient:
        raise HTTPException(404, "Patient not found")
    patient.status = "seen"
    db.add(patient)
    event = models.TriageEvent(
        patient_id=patient.id, actor="nurse", action="marked_seen",
        from_tier=patient.current_esi_tier, to_tier=patient.current_esi_tier,
        reason="Patient taken back to be seen.",
    )
    db.add(event)
    db.commit()
    db.refresh(patient)
    return patient


@router.post("/{patient_id}/recheck", response_model=schemas.PatientDetailOut)
def manual_recheck(patient_id: str, db: Session = Depends(get_db)):
    """Manually trigger stage 5 (Keep Watching) for one patient — useful for demoing."""
    patient = db.get(models.Patient, patient_id)
    if not patient:
        raise HTTPException(404, "Patient not found")
    patient, _rec = _run_pipeline_and_store(db, patient)
    return patient
