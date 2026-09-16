# Aegis Triage — Prototype

A working, hackathon-grade prototype of an AI co-pilot for ED triage nurses.
Real data flowing through a real pipeline — no mocked screens.

**Core principle: the AI recommends, the nurse decides.** Nothing ever
auto-finalizes a triage tier.

## Stack

- **Backend**: FastAPI + SQLAlchemy + SQLite (`backend/`)
- **Frontend**: React + Vite + Tailwind (`frontend/`)
- **Scoring layer**: a multi-agent pipeline (`backend/app/agents.py`) blending
  a rules engine, a NEWS2-style vitals score, fuzzy NLP complaint matching,
  and a trained ML model — see "The scoring layer" below.

## Running it

### Backend

```bash
cd backend
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
./venv/bin/uvicorn app.main:app --reload --port 8000
```

On first startup it trains the ML model (~2-3s), creates `aegis.db`, seeds
~13 patients across the acuity spectrum, and starts the "Keep Watching"
background recheck job.

By default the recheck job runs on an accelerated clock so you can see it
work in a demo (`AEGIS_DEMO_SPEEDUP=60` — 1 simulated minute = 1 real second).
Set `AEGIS_DEMO_SPEEDUP=1` for a real-time pace.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Opens on `http://localhost:5173`, talking to the API at `http://localhost:8000`
(configurable in `frontend/.env`).

## The five pipeline stages

1. **Capture** — `POST /api/patients` (intake form + optional simulated EHR match)
2. **Analyze** — the multi-agent pipeline in `backend/app/agents.py`
3. **Recommend** — resource path, recheck interval, and staged order set
4. **Nurse Decides** — `/confirm`, `/override`, `/escalate` — every action writes a `TriageEvent`
5. **Keep Watching** — `backend/app/scheduler.py` — background job re-scores waiting
   patients on an interval and flags anyone whose risk has crept up, without
   ever silently changing their confirmed tier

## The scoring layer

`analyze()` was always structured to have a real model dropped in behind it.
It's decomposed into three agents, orchestrated by `TriagePipeline`
(`backend/app/agents.py`):

- **`SymptomExtractionAgent`** — turns free text into structured signals
  using `backend/app/nlp.py`: a local, fully-offline fuzzy matcher (word-level
  sequence similarity, not literal substring search) against a canonical
  red-flag/moderate-complaint phrase bank. Catches typos ("chest pian"),
  reordering ("pain in my chest"), and shorthand ("SOB", "CP") that exact
  substring matching would silently miss. A phrase only matches if *every*
  one of its words has a fuzzy match in the complaint — this was tightened
  after testing surfaced a real false positive (see below).

- **`RiskScoringAgent`** — combines:
  - **Vitals danger thresholds** (hard-coded safety limits: SpO2<90, HR>130
    or <50, RR>30 or <8, systolic BP<90)
  - **NEWS2** (`backend/app/clinical_scores.py`) — a simplified version of
    the standard clinical early-warning score, computed from the vitals
    snapshot and trend-adjusted using `last_vitals_trend` (a field that
    existed from the start but was never actually read by the scoring logic
    until this pass)
  - **A trained ML model** (`backend/app/ml/`) — a small `RandomForestClassifier`
    trained at process startup on synthetic data (`ml/synthetic_data.py`,
    generated from clinically-informed archetypes with randomized vitals and
    deliberate label noise — not a clinically validated dataset, disclosed as
    such). It runs as a genuine second opinion alongside the rules engine,
    not a replacement for it.

  **Blending policy**: the rules engine (including the hard-forced
  unconscious/non-verbal/pediatric/critical-vitals cases) is an absolute
  safety floor. The final tier is `min(rule_tier, model_tier)` — the model
  can only push a case *more* urgent than the rules alone would, never less.
  Agreement between the two boosts confidence; disagreement is flagged
  (`model_escalated` / `rules_floor_applied`) and explained in the audit
  trail, never silently resolved.

- **`ResourcePlanningAgent`** — turns the risk result into what the nurse
  sees: resource path, recheck interval, and — for tier ≤2 cases — a staged
  order set (e.g. chest pain → ECG, troponin, IV access, cardiac monitoring)
  the nurse can review and confirm in one action instead of building from
  scratch. This does not auto-order anything; it's still gated behind the
  same tier-1/2 acknowledgment requirement as the tier itself.

**A bug worth knowing about**: an earlier version of the fuzzy matcher used
whole-string character n-gram similarity, which produced real false
positives — "sore throat" (routine) matched "throat swelling" (critical) at
0.70 similarity purely because both strings contain the word "throat", and
"not feeling well" matched "swelling" via coincidental character overlap.
The fix was to require every word in a canonical phrase to have its own
fuzzy match among the complaint's tokens, rather than scoring string
similarity as a whole. Caught by testing every seeded patient's output
against expectation before considering this done, not by design review
alone — worth doing the same before trusting any change to this file.

## Try the demo

1. Open the **Waiting Room** — seeded queue, sorted by tier then wait time.
2. Watch **Tomas Novak** — seeded to quietly deteriorate. Within ~20–40 seconds
   the recheck loop flags him and pins him to the top with a red pulse.
3. Click **+ New patient**, try a typo: "crushing chest pian and sweating" —
   the fuzzy matcher still catches it, tier 1, with a staged cardiac order
   set attached. Because it's Level 1–2 you'll have to explicitly acknowledge
   it before confirming or overriding.
4. Try an **override**: pick a different tier, give a one-line reason, then
   open the patient's detail page to see it recorded in the audit trail
   alongside the original AI suggestion, the ML model's second opinion, and
   the NEWS2/complaint-matching trace that produced it.
5. Try "Not feeling well" with no vitals — resolves to a moderate tier
   (never a falsely reassuring low-acuity one), per the hard rule: missing
   or ambiguous data escalates, it never quietly downgrades.

## Notes

- This is a prototype, not a certified clinical system. The ML model is
  trained on synthetic data to demonstrate the architecture (rules as
  safety floor, model as second opinion), not as a validated clinical tool.
- The EHR match is a small hardcoded fake dataset (`backend/app/ehr_data.py`), not a real integration.
- SQLite is used for simplicity; the models are ORM-based so swapping to Postgres is a one-line `DATABASE_URL` change.
- No external API calls anywhere in the scoring path — it has to run on a
  nurse's workstation without depending on network availability.
