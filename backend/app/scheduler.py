"""
Stage 5: Keep Watching.

A background job that periodically re-runs Analyze + Recommend against every
'waiting' patient whose last_rechecked_at exceeds their recheck_interval_minutes.
If the new suggestion is more urgent than the nurse-confirmed tier, the patient
is flagged 'deteriorating' and surfaced at the top of the board. This never
silently changes current_esi_tier — only a nurse action does that.

DEMO_SPEEDUP compresses wall-clock time so a hackathon demo doesn't require
waiting 10-45 real minutes to see a recheck fire. 1 simulated minute takes
(60 / DEMO_SPEEDUP) real seconds. Set AEGIS_DEMO_SPEEDUP=1 for real-time.
"""
import logging
import os
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from .database import SessionLocal
from . import models
from .routers.patients import _run_pipeline_and_store

logger = logging.getLogger("aegis.scheduler")

DEMO_SPEEDUP = float(os.environ.get("AEGIS_DEMO_SPEEDUP", "60"))
SCAN_INTERVAL_SECONDS = 3


def _tick():
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        waiting = db.query(models.Patient).filter(models.Patient.status == "waiting").all()
        for patient in waiting:
            last = patient.last_rechecked_at
            if last is not None and last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            elapsed_real_seconds = (now - last).total_seconds() if last else 1e9
            elapsed_sim_minutes = elapsed_real_seconds * DEMO_SPEEDUP / 60.0
            if elapsed_sim_minutes >= (patient.recheck_interval_minutes or 60):
                prev_tier = patient.current_esi_tier
                if patient.sim_decline:
                    _apply_decline_drift(patient)
                patient, rec = _run_pipeline_and_store(db, patient)
                if prev_tier is not None and rec.suggested_tier < prev_tier:
                    logger.info(
                        "Recheck: %s (%s) deteriorated: confirmed tier %s -> AI now suggests %s",
                        patient.name, patient.id, prev_tier, rec.suggested_tier,
                    )
    except Exception:
        logger.exception("Recheck tick failed")
    finally:
        db.close()


_scheduler = None


def _apply_decline_drift(patient: models.Patient):
    """Nudge a demo-flagged patient's vitals to worsen on each tick, until
    they cross into clearly dangerous territory. This simulates a patient
    quietly deteriorating in the waiting room."""
    changed = False
    if patient.spo2 is not None and patient.spo2 > 87:
        patient.spo2 -= 3
        changed = True
    if patient.hr is not None and patient.hr < 128:
        patient.hr += 8
        changed = True
    if patient.rr is not None and patient.rr < 28:
        patient.rr += 3
        changed = True
    if patient.bp_sys is not None and patient.bp_sys > 92:
        patient.bp_sys -= 4
        changed = True
    if changed:
        patient.last_vitals_trend = "worsening"


def start_scheduler():
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(_tick, "interval", seconds=SCAN_INTERVAL_SECONDS, id="keep_watching")
    _scheduler.start()
    logger.info("Keep Watching scheduler started (speedup=%sx, scan every %ss)", DEMO_SPEEDUP, SCAN_INTERVAL_SECONDS)
    return _scheduler


def stop_scheduler():
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
