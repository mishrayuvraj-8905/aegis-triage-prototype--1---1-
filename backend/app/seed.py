"""Seeds a realistic-looking waiting room: a couple of obvious tier-1s, a
batch of tier-3/4 'normal ED day' cases, one deliberately ambiguous/missing
-data case, one pediatric case, plus several already confirmed-and-waiting
so the Keep Watching loop has something to act on live during a demo."""
from datetime import datetime, timedelta, timezone

from .database import SessionLocal, engine, Base
from . import models
from .routers.patients import _run_pipeline_and_store


SEED_PATIENTS = [
    # Obvious tier-1s
    dict(name="Wei Chen", age=50, sex="M", chief_complaint="Crushing chest pain radiating to left arm, sweating",
         hr=128, bp_sys=88, bp_dia=58, rr=26, spo2=91, temp=98.6),
    dict(name="Robert Klein", age=76, sex="M", chief_complaint="Sudden difficulty breathing, blue lips",
         hr=118, bp_sys=102, bp_dia=70, rr=32, spo2=85, temp=99.1),

    # Tier-3/4 'normal ED day' batch
    dict(name="Priya Nair", age=22, sex="F", chief_complaint="Severe migraine with light sensitivity, nausea",
         hr=88, bp_sys=118, bp_dia=76, rr=16, spo2=98, temp=98.4),
    dict(name="Daniel Osei", age=41, sex="M", chief_complaint="Abdominal pain and vomiting since this morning",
         hr=96, bp_sys=124, bp_dia=80, rr=18, spo2=97, temp=100.2),
    dict(name="Hannah Fischer", age=29, sex="F", chief_complaint="Twisted ankle playing soccer, possible fracture",
         hr=82, bp_sys=116, bp_dia=74, rr=14, spo2=99, temp=98.2),
    dict(name="Marcus Webb", age=55, sex="M", chief_complaint="Lower back pain after lifting furniture",
         hr=78, bp_sys=130, bp_dia=84, rr=16, spo2=98, temp=98.6),
    dict(name="Sofia Ricci", age=34, sex="F", chief_complaint="Sore throat and cough for three days",
         hr=80, bp_sys=112, bp_dia=72, rr=16, spo2=99, temp=100.8),
    dict(name="Ben Turner", age=19, sex="M", chief_complaint="Minor laceration on forearm from broken glass",
         hr=74, bp_sys=118, bp_dia=76, rr=14, spo2=99, temp=98.1),
    dict(name="Aisha Bello", age=27, sex="F", chief_complaint="Rash on both arms, mild itching, no other symptoms",
         hr=76, bp_sys=110, bp_dia=70, rr=14, spo2=99, temp=98.4),

    # Deliberately ambiguous / missing-data case
    dict(name="Unknown Male", age=None, sex=None, chief_complaint="Not feeling well",
         hr=None, bp_sys=None, bp_dia=None, rr=None, spo2=None, temp=None),

    # Pediatric case
    dict(name="Grace Kim", age=9, sex="F", chief_complaint="Facial swelling and hives after eating at school",
         hr=118, bp_sys=100, bp_dia=64, rr=24, spo2=95, temp=99.0, pediatric=True),

    # A couple more routine cases to round out the board
    dict(name="Linda Osei", age=64, sex="F", chief_complaint="Medication refill, out of blood pressure pills",
         hr=72, bp_sys=128, bp_dia=82, rr=14, spo2=98, temp=98.2),
    dict(name="Tomas Novak", age=60, sex="M", chief_complaint="Dizziness on standing for the past two days",
         hr=68, bp_sys=104, bp_dia=68, rr=16, spo2=97, temp=98.0),
]

# Names (from SEED_PATIENTS above) to auto-confirm so the recheck loop has
# live material during a demo. One of these ("Tomas Novak") will be seeded
# with a stale last_rechecked_at so a recheck fires almost immediately and
# visibly flags them as deteriorating.
AUTO_CONFIRM = {"Priya Nair", "Daniel Osei", "Marcus Webb", "Tomas Novak"}
STALE_RECHECK = {"Tomas Novak": 40}  # minutes ago -> will trigger a near-immediate recheck
SIM_DECLINE = {"Tomas Novak"}  # quietly deteriorates each recheck tick, unprompted


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(models.Patient).count() > 0:
            print("Database already has patients; skipping seed.")
            return

        for i, spec in enumerate(SEED_PATIENTS):
            patient = models.Patient(
                name=spec["name"],
                age=spec.get("age"),
                sex=spec.get("sex"),
                chief_complaint=spec.get("chief_complaint", ""),
                hr=spec.get("hr"), bp_sys=spec.get("bp_sys"), bp_dia=spec.get("bp_dia"),
                rr=spec.get("rr"), spo2=spec.get("spo2"), temp=spec.get("temp"),
                pediatric=spec.get("pediatric", False),
                status="waiting",
                sim_decline=spec["name"] in SIM_DECLINE,
                arrival_time=datetime.now(timezone.utc) - timedelta(minutes=(len(SEED_PATIENTS) - i) * 6),
            )
            db.add(patient)
            db.commit()
            db.refresh(patient)

            patient, rec = _run_pipeline_and_store(db, patient)

            if patient.name in AUTO_CONFIRM:
                from_tier = patient.current_esi_tier
                patient.current_esi_tier = patient.ai_suggested_tier
                patient.acknowledged = True
                db.add(patient)
                event = models.TriageEvent(
                    patient_id=patient.id, actor="nurse", action="confirmed",
                    from_tier=from_tier, to_tier=patient.current_esi_tier,
                    reason="Nurse confirmed AI-suggested tier.",
                    confidence=patient.ai_confidence,
                )
                db.add(event)
                if patient.name in STALE_RECHECK:
                    patient.last_rechecked_at = datetime.now(timezone.utc) - timedelta(
                        minutes=STALE_RECHECK[patient.name]
                    )
                    db.add(patient)
                db.commit()
                db.refresh(patient)

        print(f"Seeded {len(SEED_PATIENTS)} patients ({len(AUTO_CONFIRM)} confirmed and waiting).")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
