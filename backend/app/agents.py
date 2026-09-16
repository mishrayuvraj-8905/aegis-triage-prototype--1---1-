"""
The triage pipeline, decomposed into three agents instead of one
analyze() black box.

A note on what "agent" means here: these are not separate LLM calls behind
an orchestrator — a clinical tool that only works when a language-model API
is reachable is a worse tool, not a better one, and this needs to run
offline on a nurse's workstation. What they are is a genuine multi-agent
*decomposition*: three independently testable components with typed
inputs/outputs and a single responsibility each, run in sequence by an
orchestrator that stitches their traces into one explainable record. Any
one of them can be swapped for an LLM-backed implementation later without
touching the others, which is the actual point of decomposing it this way.

  1. SymptomExtractionAgent — free text -> structured complaint signals
     (fuzzy-matched red-flag/moderate phrases, vagueness, order-set triggers)
  2. RiskScoringAgent        — vitals + extracted symptoms -> a tier and
     confidence, blending the rules engine (safety floor) with the ML
     model (second opinion)
  3. ResourcePlanningAgent   — a risk result -> what the nurse actually
     sees: resource path, recheck interval, staged order set, ack gate
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict

from .signals import PatientSignals
from .clinical_scores import compute_news2, News2Result
from .nlp import ComplaintMatcher, PhraseMatch
from .scoring_phrases import RED_FLAG_TERMS, MODERATE_TERMS, VAGUE_COMPLAINT_MARKERS, ORDER_SET_TRIGGERS
from .ml.model import predict as ml_predict, ModelPrediction

_ALL_PHRASE_TIERS = {**RED_FLAG_TERMS, **MODERATE_TERMS}
_matcher = ComplaintMatcher(_ALL_PHRASE_TIERS)


# ---------------------------------------------------------------------------
# Shared result types
# ---------------------------------------------------------------------------

@dataclass
class AnalyzeResult:
    suggested_tier: int
    confidence: float
    reason: str
    flags: List[str]
    resource_score: int
    signal_trace: List[str]
    model_tier: Optional[int] = None
    model_confidence: Optional[float] = None
    model_distribution: Optional[Dict[int, float]] = None
    rule_tier: Optional[int] = None


@dataclass
class Recommendation:
    suggested_tier: int
    confidence: float
    confidence_label: str
    reason: str
    resource_path: str
    recheck_interval_minutes: int
    flags: List[str]
    ack_required: bool
    signal_trace: List[str]
    suggested_orders: List[str] = field(default_factory=list)
    model_tier: Optional[int] = None
    model_confidence: Optional[float] = None


@dataclass
class ExtractionResult:
    complaint_tier: Optional[int]
    matches: List[PhraseMatch]
    vague: bool
    order_categories: List[str]
    trace: List[str]


@dataclass
class RiskResult:
    suggested_tier: int
    confidence: float
    flags: List[str]
    trace: List[str]
    vitals_tier: Optional[int]
    news2: Optional[News2Result]
    vitals_present: bool
    model: Optional[ModelPrediction]
    forced: bool = False
    forced_reason: Optional[str] = None


# ---------------------------------------------------------------------------
# Agent 1: Symptom Extraction
# ---------------------------------------------------------------------------

class SymptomExtractionAgent:
    """Turns free-text chief complaint into structured signals: the best-
    matching acuity tier from the phrase bank (via fuzzy NLP matching, not
    literal substring search), vagueness, and which staged order-set
    categories (cardiac/respiratory/neuro/...) are implicated."""

    def __init__(self, matcher: ComplaintMatcher = _matcher):
        self.matcher = matcher

    def run(self, s: PatientSignals) -> ExtractionResult:
        tier, matches = self.matcher.best_tier(s.chief_complaint)
        trace = []
        for m in sorted(matches, key=lambda m: m.tier)[:5]:
            kind = "exact" if m.similarity >= 0.999 else f"fuzzy match ({m.similarity:.2f})"
            trace.append(f"Complaint term '{m.phrase}' matched ({kind}) -> tier {m.tier}")

        vague = self._is_vague(s.chief_complaint)
        if vague:
            trace.append("Chief complaint is vague or very short -> confidence penalized, cannot resolve to a lower tier")

        matched_phrases = {m.phrase for m in matches}
        order_categories = [
            cat for cat, spec in ORDER_SET_TRIGGERS.items()
            if matched_phrases & set(spec["phrases"])
        ]

        return ExtractionResult(
            complaint_tier=tier, matches=matches, vague=vague,
            order_categories=order_categories, trace=trace,
        )

    @staticmethod
    def _is_vague(complaint: str) -> bool:
        text = (complaint or "").lower().strip()
        if len(text) < 6:
            return True
        return any(text == m or (m and m in text and len(text) < 25) for m in VAGUE_COMPLAINT_MARKERS)


# ---------------------------------------------------------------------------
# Agent 2: Risk Scoring
# ---------------------------------------------------------------------------

class RiskScoringAgent:
    """Combines vitals (via NEWS2, trend-adjusted), the extracted complaint
    signal, and the ML model's second opinion into a final tier + confidence.

    The rules engine's hard-forced cases (unconscious, non-verbal,
    pediatric, critical vitals) are a safety floor: the ML model can only
    push the final tier *more* urgent than the floor, never less. This is
    enforced structurally (min() of the two), not by trusting the model to
    behave — see _blend()."""

    def run(self, s: PatientSignals, extraction: ExtractionResult) -> RiskResult:
        trace: List[str] = []
        flags: List[str] = []

        # --- Forced overrides: safety floor, nothing overrides these. ---
        if s.unconscious:
            trace.append("Unconscious flag set -> forced tier 1")
            return RiskResult(
                suggested_tier=1, confidence=0.95, flags=["forced-critical"], trace=trace,
                vitals_tier=None, news2=None, vitals_present=False, model=None,
                forced=True, forced_reason="Patient is unconscious \u2014 forced to the most urgent tier.",
            )

        if s.pediatric or (s.age is not None and s.age < 18):
            flags.append("pediatric")
            trace.append("Pediatric patient -> acuity floor raised, cannot resolve below tier 2 without clear reassurance")

        # --- Vitals: danger thresholds + NEWS2 (trend-adjusted) ---
        vitals_tier, vitals_trace = self._vitals_danger_tier(s)
        trace.extend(vitals_trace)
        vitals_present = all(v is not None for v in [s.hr, s.rr, s.spo2, s.bp_sys])
        if not vitals_present:
            flags.append("missing_data")
            missing = [n for n, v in [("HR", s.hr), ("RR", s.rr), ("SpO2", s.spo2), ("BP", s.bp_sys)] if v is None]
            trace.append(f"Missing vitals: {', '.join(missing)} -> cannot resolve to a lower tier")

        news2 = compute_news2(s.hr, s.rr, s.spo2, s.bp_sys, s.temp, s.last_vitals_trend)
        trace.extend(news2.trace)
        news2_tier = {"high": 1, "medium": 2}.get(news2.trend_adjusted_band)
        if news2_tier is not None:
            trace.append(f"NEWS2 trend-adjusted band '{news2.trend_adjusted_band}' implies tier <= {news2_tier}")

        complaint_tier = extraction.complaint_tier

        if s.non_verbal:
            candidates = [t for t in [vitals_tier, news2_tier, complaint_tier] if t is not None]
            forced = min([2] + candidates)
            flags.append("forced-non-verbal")
            trace.append("Non-verbal flag set -> forced tier <= 2")
            return RiskResult(
                suggested_tier=forced, confidence=0.7, flags=flags, trace=trace,
                vitals_tier=vitals_tier, news2=news2, vitals_present=vitals_present, model=None,
                forced=True, forced_reason="Patient is non-verbal \u2014 acuity cannot be safely assessed, forced to tier \u2264 2 pending nurse assessment.",
            )

        # --- Combine rule-derived signals ---
        candidate_tiers = [t for t in [vitals_tier, news2_tier, complaint_tier] if t is not None]

        conflict = False
        if vitals_tier is not None and vitals_tier <= 2 and (complaint_tier is None or complaint_tier >= 4):
            conflict = True
            flags.append("conflicting_signals")
            trace.append("Vitals indicate danger but complaint text reads mild -> confidence penalized, deferring to vitals")

        if candidate_tiers:
            rule_tier = min(candidate_tiers)
        elif not vitals_present or extraction.vague:
            rule_tier = 3
            trace.append("No clear signal and data is incomplete -> default to tier 3, not a lower/safer tier")
        else:
            rule_tier = 4
            trace.append("No red-flag or moderate signals, vitals unremarkable -> tier 4")

        if "pediatric" in flags:
            if rule_tier > 2:
                trace.append("Pediatric flag forces tier <= 2 regardless of other signals")
            rule_tier = min(rule_tier, 2)

        # --- Rule-side confidence ---
        rule_confidence = 0.9
        if extraction.vague:
            rule_confidence -= 0.3
        if not vitals_present:
            rule_confidence -= 0.25
        if conflict:
            rule_confidence -= 0.2
        if "pediatric" in flags:
            rule_confidence -= 0.05
        rule_confidence = max(0.15, min(0.95, rule_confidence))

        # --- ML second opinion ---
        model_pred = ml_predict(s)
        trace.append(
            f"ML model second opinion: tier {model_pred.tier} (confidence {model_pred.confidence:.2f}), "
            f"driven mainly by {', '.join(model_pred.top_features[:3])}"
        )

        final_tier, final_confidence, blend_flags, blend_trace = self._blend(
            rule_tier, rule_confidence, model_pred,
        )
        flags.extend(blend_flags)
        trace.extend(blend_trace)

        if final_confidence < 0.6:
            flags.append("low_confidence")

        if not trace:
            trace.append("No danger thresholds, NEWS2 concern, or red-flag terms matched; routine presentation")

        return RiskResult(
            suggested_tier=final_tier,
            confidence=round(final_confidence, 2),
            flags=sorted(set(flags)),
            trace=trace,
            vitals_tier=vitals_tier,
            news2=news2,
            vitals_present=vitals_present,
            model=model_pred,
        )

    @staticmethod
    def _vitals_danger_tier(s: PatientSignals):
        trace = []
        danger = False
        critical = False
        if s.spo2 is not None and s.spo2 < 90:
            critical = True
        if s.hr is not None and (s.hr > 130 or s.hr < 50):
            danger = True
        if s.rr is not None and (s.rr > 30 or s.rr < 8):
            critical = True
        if s.bp_sys is not None and s.bp_sys < 90:
            critical = True
        tier = 1 if critical else (2 if danger else None)
        if tier:
            trace.append(f"Vital sign danger threshold breached -> tier {tier}")
        return tier, trace

    @staticmethod
    def _blend(rule_tier: int, rule_confidence: float, model: ModelPrediction):
        """Rules are the safety floor: the blended tier can never be *less*
        urgent than the rules engine's own tier. The model can only push it
        *more* urgent, if its independent read disagrees in that direction."""
        flags: List[str] = []
        trace: List[str] = []

        final_tier = min(rule_tier, model.tier)

        if model.tier == rule_tier:
            # Independent agreement is a genuine confidence signal.
            confidence = min(0.97, (rule_confidence + model.confidence) / 2 + 0.05)
            trace.append(f"Rules ({rule_tier}) and ML model ({model.tier}) agree -> confidence boosted to {confidence:.2f}")
        elif model.tier < rule_tier:
            # Model caught something the rules missed. Use it, but flag the
            # disagreement plainly for the audit trail.
            confidence = round(min(rule_confidence, model.confidence) * 0.9, 2)
            flags.append("model_escalated")
            trace.append(
                f"ML model suggested a more urgent tier ({model.tier}) than the rules engine ({rule_tier}) "
                f"-> deferring to the more urgent read, confidence reduced to reflect the disagreement"
            )
        else:
            # Rules floor caught something the model didn't (expected —
            # that's what the floor is for). Model's more relaxed read
            # doesn't get to soften the outcome.
            confidence = round(rule_confidence, 2)
            flags.append("rules_floor_applied")
            trace.append(
                f"Rules safety floor ({rule_tier}) is more urgent than the ML model's read ({model.tier}) "
                f"-> rules floor applied, model's softer read did not lower the tier"
            )

        return final_tier, confidence, flags, trace


# ---------------------------------------------------------------------------
# Agent 3: Resource Planning
# ---------------------------------------------------------------------------

_RESOURCE_PATHS = {
    1: "Trauma bay",
    2: "Trauma bay",
    3: "Imaging / labs needed",
    4: "Standard bed",
    5: "Fast-track",
}


class ResourcePlanningAgent:
    """Turns a risk result into what the nurse actually sees: a resource
    path, a recheck interval, and — for tier <=2 cases — a staged order set
    the nurse can review and confirm in one action instead of building from
    scratch. The nurse still has to act; nothing here auto-orders anything."""

    def run(self, risk: RiskResult, extraction: ExtractionResult, resource_score: int, reason: str) -> Recommendation:
        label = self._confidence_label(risk.confidence)

        resource_path = _RESOURCE_PATHS.get(risk.suggested_tier, "Standard bed")
        if resource_score >= 4 and risk.suggested_tier <= 3:
            resource_path = "Trauma bay"
        elif resource_score >= 2 and risk.suggested_tier == 3:
            resource_path = "Imaging / labs needed"

        if risk.suggested_tier <= 2:
            interval = 10
        elif risk.suggested_tier == 3:
            interval = 20
        else:
            interval = 45
        if label == "Low":
            interval = max(5, interval // 2)

        ack_required = risk.suggested_tier <= 2

        suggested_orders: List[str] = []
        if risk.suggested_tier <= 2:
            for cat in extraction.order_categories:
                for order in ORDER_SET_TRIGGERS[cat]["orders"]:
                    if order not in suggested_orders:
                        suggested_orders.append(order)

        return Recommendation(
            suggested_tier=risk.suggested_tier,
            confidence=risk.confidence,
            confidence_label=label,
            reason=reason,
            resource_path=resource_path,
            recheck_interval_minutes=interval,
            flags=risk.flags,
            ack_required=ack_required,
            signal_trace=risk.trace,
            suggested_orders=suggested_orders,
            model_tier=risk.model.tier if risk.model else None,
            model_confidence=risk.model.confidence if risk.model else None,
        )

    @staticmethod
    def _confidence_label(confidence: float) -> str:
        if confidence >= 0.75:
            return "High"
        if confidence >= 0.5:
            return "Medium"
        return "Low"


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def _resource_score(s: PatientSignals, complaint_tier: Optional[int]) -> int:
    score = 0
    text = (s.chief_complaint or "").lower()
    if any(k in text for k in ["fracture", "fall", "head injury", "trauma"]):
        score += 2
    if any(k in text for k in ["chest pain", "abdominal pain", "vomiting", "bleeding"]):
        score += 2
    if any(k in text for k in ["difficulty breathing", "seizure", "overdose", "anaphylaxis", "allergic reaction"]):
        score += 2
    if s.prior_ed_visits and s.prior_ed_visits >= 3:
        score += 1
    if complaint_tier is not None and complaint_tier <= 3:
        score += 1
    return score


def _build_reason(risk: RiskResult, extraction: ExtractionResult) -> str:
    if risk.forced and risk.forced_reason:
        return risk.forced_reason
    parts = []
    if risk.vitals_tier:
        parts.append("vital signs are outside safe range")
    if risk.news2 and risk.news2.trend_adjusted_band == "high":
        parts.append("NEWS2 early warning score is in the high-risk band")
    if extraction.complaint_tier and extraction.complaint_tier <= 3:
        parts.append("chief complaint includes concerning terms")
    if "conflicting_signals" in risk.flags:
        parts.append("vitals and complaint disagree, so the more urgent reading was used")
    if "missing_data" in risk.flags:
        parts.append("some vitals are missing, which pushes acuity up rather than down")
    if extraction.vague:
        parts.append("the complaint text is too vague to rule out something serious")
    if "model_escalated" in risk.flags:
        parts.append("the ML model's independent read flagged more urgency than the rules alone")
    if not parts:
        parts.append("no danger signs were detected in vitals, NEWS2, or complaint text")
    return f"Suggested tier {risk.suggested_tier} because " + "; ".join(parts) + "."


class TriagePipeline:
    """Orchestrates the three agents in sequence and stitches their traces
    into one explainable record — this IS the 'clear record' the audit
    trail promises, one level up from individual nurse actions."""

    def __init__(self):
        self.extraction_agent = SymptomExtractionAgent()
        self.risk_agent = RiskScoringAgent()
        self.resource_agent = ResourcePlanningAgent()

    def run(self, s: PatientSignals):
        extraction = self.extraction_agent.run(s)
        risk = self.risk_agent.run(s, extraction)
        resource_score = _resource_score(s, extraction.complaint_tier)

        # Resource-implied tier cap (more resources implied -> at least tier 3)
        if resource_score >= 3 and risk.suggested_tier > 3:
            risk.trace.append(f"Resource inference score {resource_score} (labs/imaging/IV likely) -> tier capped at 3")
            risk.suggested_tier = 3

        reason = _build_reason(risk, extraction)

        analyze_result = AnalyzeResult(
            suggested_tier=risk.suggested_tier,
            confidence=risk.confidence,
            reason=reason,
            flags=risk.flags,
            resource_score=resource_score,
            signal_trace=extraction.trace + risk.trace,
            model_tier=risk.model.tier if risk.model else None,
            model_confidence=risk.model.confidence if risk.model else None,
            model_distribution=risk.model.distribution if risk.model else None,
        )

        recommendation = self.resource_agent.run(risk, extraction, resource_score, reason)
        recommendation.signal_trace = analyze_result.signal_trace

        return analyze_result, recommendation


_pipeline = TriagePipeline()


def analyze(s: PatientSignals) -> AnalyzeResult:
    """Stage 2: Analyze. Orchestrates the extraction + risk agents."""
    result, _ = _pipeline.run(s)
    return result


def recommend(result: AnalyzeResult) -> Recommendation:
    """Stage 3: Recommend. Kept as a compatible entry point — re-runs the
    resource planning agent's logic is already folded into analyze() above
    for real requests (see analyze_and_recommend), this function exists so
    any external caller that only wants a Recommendation from an
    already-computed AnalyzeResult-shaped object still works."""
    # This path is only hit if a caller has an AnalyzeResult without having
    # gone through the pipeline (e.g. tests). Reconstruct a minimal risk
    # result from the analyze output.
    from .clinical_scores import News2Result
    fake_model = ModelPrediction(
        tier=result.model_tier or result.suggested_tier,
        confidence=result.model_confidence or result.confidence,
        distribution=result.model_distribution or {},
        top_features=[],
    ) if result.model_tier is not None else None
    risk = RiskResult(
        suggested_tier=result.suggested_tier, confidence=result.confidence,
        flags=result.flags, trace=result.signal_trace, vitals_tier=None,
        news2=None, vitals_present=True, model=fake_model,
    )
    extraction = ExtractionResult(complaint_tier=None, matches=[], vague=False, order_categories=[], trace=[])
    agent = ResourcePlanningAgent()
    return agent.run(risk, extraction, result.resource_score, result.reason)


def analyze_and_recommend(s: PatientSignals):
    """Preferred entry point: runs the full pipeline once, returns both
    results consistently (avoids recomputing resource planning twice)."""
    return _pipeline.run(s)
