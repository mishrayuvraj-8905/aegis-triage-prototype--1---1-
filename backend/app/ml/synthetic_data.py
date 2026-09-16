"""
Generates synthetic training examples for the ESI classifier.

There's no public ESI-labeled dataset we can pull in (real triage data is
protected health information), so this generates patients from clinically-
informed archetypes with randomized vitals/complaints/noise, labeled by an
independent severity heuristic — independent in the sense that it is NOT
the same code path as scoring.py's rules engine. If it were, the "model"
would just be memorizing the rules engine's own output, which would be
worthless as a second opinion. Small label noise is injected deliberately:
real triage outcomes are messier than any rule set, and a model trained on
a perfectly clean deterministic function has nothing to generalize from.

This is disclosed, not hidden: the model is a legitimate architectural
demonstration of "rules as safety floor, model as second opinion," not a
clinically validated tool. See README.
"""
import random
from typing import List, Tuple

import numpy as np

from ..signals import PatientSignals
from .features import featurize

ARCHETYPES = [
    # (name, weight, vitals sampler, complaint pool, base_tier)
    dict(
        name="critical",
        weight=0.08,
        vitals=lambda rng: dict(
            hr=rng.randint(125, 165), rr=rng.randint(28, 38),
            spo2=rng.randint(78, 89), bp_sys=rng.randint(65, 92), bp_dia=rng.randint(40, 60),
            temp=round(rng.uniform(96.5, 103.5), 1),
        ),
        complaints=["crushing chest pain radiating to the arm", "sudden difficulty breathing",
                    "unresponsive on arrival", "severe uncontrolled bleeding", "one-sided weakness and slurred speech"],
        base_tier=1,
    ),
    dict(
        name="emergent",
        weight=0.14,
        vitals=lambda rng: dict(
            hr=rng.randint(105, 130), rr=rng.randint(22, 29),
            spo2=rng.randint(89, 94), bp_sys=rng.randint(85, 105), bp_dia=rng.randint(55, 70),
            temp=round(rng.uniform(97.5, 102.5), 1),
        ),
        complaints=["shortness of breath getting worse", "severe abdominal pain with vomiting",
                    "allergic reaction with facial swelling", "high fever and confusion",
                    "seizure witnessed by family"],
        base_tier=2,
    ),
    dict(
        name="urgent",
        weight=0.28,
        vitals=lambda rng: dict(
            hr=rng.randint(85, 108), rr=rng.randint(16, 22),
            spo2=rng.randint(94, 98), bp_sys=rng.randint(105, 140), bp_dia=rng.randint(65, 88),
            temp=round(rng.uniform(97.0, 101.0), 1),
        ),
        complaints=["moderate abdominal pain", "possible fracture after a fall", "persistent migraine",
                    "laceration needing sutures", "dizziness on standing"],
        base_tier=3,
    ),
    dict(
        name="less_urgent",
        weight=0.30,
        vitals=lambda rng: dict(
            hr=rng.randint(65, 92), rr=rng.randint(12, 18),
            spo2=rng.randint(96, 100), bp_sys=rng.randint(108, 135), bp_dia=rng.randint(68, 85),
            temp=round(rng.uniform(97.2, 99.8), 1),
        ),
        complaints=["lower back pain after lifting", "mild sprain", "rash on arms", "persistent cough"],
        base_tier=4,
    ),
    dict(
        name="non_urgent",
        weight=0.20,
        vitals=lambda rng: dict(
            hr=rng.randint(60, 85), rr=rng.randint(12, 16),
            spo2=rng.randint(97, 100), bp_sys=rng.randint(110, 128), bp_dia=rng.randint(70, 82),
            temp=round(rng.uniform(97.5, 99.0), 1),
        ),
        complaints=["sore throat for two days", "medication refill", "minor cut on hand", "follow-up visit"],
        base_tier=5,
    ),
]


def _sample_one(rng: random.Random) -> Tuple[PatientSignals, int]:
    archetype = rng.choices(ARCHETYPES, weights=[a["weight"] for a in ARCHETYPES])[0]
    vitals = archetype["vitals"](rng)
    complaint = rng.choice(archetype["complaints"])
    age = rng.choice([rng.randint(1, 17), rng.randint(18, 64), rng.randint(65, 95)])
    pediatric = age < 18
    prior_visits = rng.choices([0, 1, 2, 3, 4, 5], weights=[35, 25, 15, 12, 8, 5])[0]
    trend = rng.choices([None, "stable", "worsening", "improving"], weights=[30, 40, 15, 15])[0]

    # Occasionally drop a vital to simulate incomplete capture.
    drop_prob = 0.06
    for k in ["hr", "rr", "spo2", "bp_sys"]:
        if rng.random() < drop_prob:
            vitals[k] = None

    label = archetype["base_tier"]
    # Elderly patients with any real severity trend slightly more urgent.
    if age >= 75 and label > 1 and rng.random() < 0.3:
        label -= 1
    # High prior-ED-visit count nudges slightly more urgent (chronic complexity).
    if prior_visits >= 4 and label > 1 and rng.random() < 0.2:
        label -= 1
    # Worsening trend nudges more urgent.
    if trend == "worsening" and label > 1 and rng.random() < 0.35:
        label -= 1
    # Small label noise: real outcomes are messier than any rule captures.
    if rng.random() < 0.08:
        label = min(5, max(1, label + rng.choice([-1, 1])))

    signals = PatientSignals(
        chief_complaint=complaint,
        hr=vitals["hr"], rr=vitals["rr"], spo2=vitals["spo2"],
        bp_sys=vitals["bp_sys"], bp_dia=vitals["bp_dia"], temp=vitals["temp"],
        age=age, pediatric=pediatric, prior_ed_visits=prior_visits,
        last_vitals_trend=trend,
    )
    return signals, label


def generate_dataset(n: int = 3000, seed: int = 42) -> Tuple[np.ndarray, np.ndarray]:
    rng = random.Random(seed)
    X: List[np.ndarray] = []
    y: List[int] = []
    for _ in range(n):
        signals, label = _sample_one(rng)
        X.append(featurize(signals))
        y.append(label)
    return np.vstack(X), np.array(y)
