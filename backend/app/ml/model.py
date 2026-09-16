"""
The learned side of the scoring layer.

analyze() in scoring.py was always written to have a real model swappable
in behind it. This is that model: a small RandomForestClassifier trained on
synthetic data (see synthetic_data.py) at process startup and cached for
the life of the process. It runs *alongside* the rules engine, not instead
of it — see scoring.py's blending logic, where the rules engine's hard
safety floor (unconscious, pediatric, critical vitals) always wins, and the
model contributes a second opinion + blended confidence for everything else.

This is honestly a synthetic-data model, not a clinically validated one —
the point is demonstrating the architecture (a real model behind the same
analyze() interface, with rules as the safety floor), which is exactly what
the codebase's docstrings always said would happen here.
"""
import logging
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
from sklearn.ensemble import RandomForestClassifier

from ..signals import PatientSignals
from .features import featurize, FEATURE_NAMES
from .synthetic_data import generate_dataset

logger = logging.getLogger("aegis.ml")

_model: Optional[RandomForestClassifier] = None
_top_features: Optional[List[str]] = None


def _train() -> RandomForestClassifier:
    t0 = time.time()
    X, y = generate_dataset(n=3000, seed=42)
    clf = RandomForestClassifier(
        n_estimators=150, max_depth=8, min_samples_leaf=4,
        random_state=42, n_jobs=-1,
    )
    clf.fit(X, y)
    logger.info("ML triage model trained on %d synthetic examples in %.2fs", len(y), time.time() - t0)
    return clf


def get_model() -> RandomForestClassifier:
    global _model, _top_features
    if _model is None:
        _model = _train()
        importances = sorted(zip(FEATURE_NAMES, _model.feature_importances_), key=lambda t: -t[1])
        _top_features = [name for name, _ in importances[:4]]
        logger.info("Top model features: %s", _top_features)
    return _model


def warm_up():
    """Call at app startup so the first real request isn't the one paying
    the training cost."""
    get_model()


@dataclass
class ModelPrediction:
    tier: int
    confidence: float
    distribution: Dict[int, float]
    top_features: List[str]


def predict(signals: PatientSignals) -> ModelPrediction:
    model = get_model()
    x = featurize(signals).reshape(1, -1)
    proba = model.predict_proba(x)[0]
    classes = model.classes_
    order = np.argsort(-proba)
    top_class = int(classes[order[0]])
    top_conf = float(proba[order[0]])
    distribution = {int(classes[i]): float(proba[i]) for i in range(len(classes))}
    return ModelPrediction(
        tier=top_class,
        confidence=round(top_conf, 3),
        distribution=distribution,
        top_features=_top_features or [],
    )
