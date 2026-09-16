import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api.js";
import RecommendationCard from "../components/RecommendationCard.jsx";
import NurseDecisionPanel from "../components/NurseDecisionPanel.jsx";

const EMPTY_FORM = {
  name: "",
  dob: "",
  age: "",
  sex: "",
  chief_complaint: "",
  hr: "",
  bp_sys: "",
  bp_dia: "",
  rr: "",
  spo2: "",
  temp: "",
  unconscious: false,
  non_verbal: false,
  pediatric: false,
};

function numOrNull(v) {
  if (v === "" || v === null || v === undefined) return null;
  const n = Number(v);
  return Number.isNaN(n) ? null : n;
}

export default function Intake() {
  const [form, setForm] = useState(EMPTY_FORM);
  const [ehrToggle, setEhrToggle] = useState(false);
  const [ehrPreview, setEhrPreview] = useState(null);
  const [ehrChecked, setEhrChecked] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [patient, setPatient] = useState(null);
  const navigate = useNavigate();

  function set(field, value) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  async function checkEhr() {
    if (!form.name.trim()) return;
    setEhrChecked(true);
    try {
      const res = await api.ehrLookup(form.name.trim(), form.dob || undefined);
      setEhrPreview(res.matched ? res.record : null);
    } catch {
      setEhrPreview(null);
    }
  }

  async function submit(e) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const payload = {
        name: form.name.trim(),
        age: numOrNull(form.age),
        sex: form.sex || null,
        chief_complaint: form.chief_complaint.trim(),
        vitals: {
          hr: numOrNull(form.hr),
          bp_sys: numOrNull(form.bp_sys),
          bp_dia: numOrNull(form.bp_dia),
          rr: numOrNull(form.rr),
          spo2: numOrNull(form.spo2),
          temp: numOrNull(form.temp),
        },
        unconscious: form.unconscious,
        non_verbal: form.non_verbal,
        pediatric: form.pediatric,
        ehr_match_requested: ehrToggle,
        dob: form.dob || null,
      };
      const created = await api.createPatient(payload);
      setPatient(created);
    } catch (e) {
      setError(e.message);
    } finally {
      setSubmitting(false);
    }
  }

  function reset() {
    setForm(EMPTY_FORM);
    setEhrToggle(false);
    setEhrPreview(null);
    setEhrChecked(false);
    setPatient(null);
    setError(null);
  }

  if (patient) {
    const isDecided = patient.current_esi_tier != null;
    return (
      <div className="mx-auto max-w-2xl space-y-5">
        <div className="rounded-xl border border-line bg-paper p-5 shadow-card">
          <div className="text-xs font-semibold uppercase tracking-widest text-subink">Patient captured</div>
          <div className="mt-1 font-display text-xl font-semibold text-teal-950">{patient.name}</div>
          <p className="text-sm text-subink">{patient.chief_complaint}</p>
        </div>

        <RecommendationCard patient={patient} />

        {isDecided ? (
          <div className="rounded-xl border border-teal-600/40 bg-teal-600/5 p-5 text-center">
            <p className="font-medium text-teal-800">
              Triaged at ESI {patient.current_esi_tier}. Recorded in the audit trail.
            </p>
            <div className="mt-3 flex justify-center gap-2">
              <button
                onClick={() => navigate(`/patients/${patient.id}`)}
                className="rounded-md border border-line px-4 py-2 text-sm font-medium hover:bg-bone"
              >
                View patient
              </button>
              <button
                onClick={reset}
                className="rounded-md bg-teal-700 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-800"
              >
                Add another patient
              </button>
            </div>
          </div>
        ) : (
          <NurseDecisionPanel patient={patient} onUpdated={setPatient} />
        )}
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl">
      <h1 className="mb-1 font-display text-2xl font-semibold text-teal-950">Intake</h1>
      <p className="mb-6 text-sm text-subink">Capture a new patient. The AI will suggest a tier the moment you submit.</p>

      <form onSubmit={submit} className="space-y-5 rounded-xl border border-line bg-paper p-6 shadow-card">
        <div className="grid grid-cols-2 gap-4">
          <Field label="Name" required>
            <input
              value={form.name}
              onChange={(e) => set("name", e.target.value)}
              onBlur={checkEhr}
              required
              className="input"
              placeholder="Patient name"
            />
          </Field>
          <Field label="Date of birth (optional, for EHR match)">
            <input
              value={form.dob}
              onChange={(e) => set("dob", e.target.value)}
              onBlur={checkEhr}
              placeholder="YYYY-MM-DD"
              className="input"
            />
          </Field>
          <Field label="Age">
            <input
              value={form.age}
              onChange={(e) => set("age", e.target.value)}
              type="number"
              min="0"
              className="input"
            />
          </Field>
          <Field label="Sex">
            <select value={form.sex} onChange={(e) => set("sex", e.target.value)} className="input">
              <option value="">—</option>
              <option value="F">F</option>
              <option value="M">M</option>
              <option value="Other">Other</option>
            </select>
          </Field>
        </div>

        {ehrChecked && (
          <div
            className={`rounded-lg border p-3 text-sm ${
              ehrPreview ? "border-teal-600/40 bg-teal-600/5" : "border-line bg-bone text-subink"
            }`}
          >
            {ehrPreview ? (
              <label className="flex cursor-pointer items-start gap-2">
                <input
                  type="checkbox"
                  checked={ehrToggle}
                  onChange={(e) => setEhrToggle(e.target.checked)}
                  className="mt-1"
                />
                <span>
                  <span className="font-medium text-teal-800">EHR match found</span> &mdash; {ehrPreview.known_conditions?.join(", ") || "no known conditions"};{" "}
                  {ehrPreview.prior_ed_visits} prior ED visit{ehrPreview.prior_ed_visits === 1 ? "" : "s"}, trend:{" "}
                  {ehrPreview.last_vitals_trend}. Check to pre-fill.
                </span>
              </label>
            ) : (
              "No EHR match found for this name/DOB."
            )}
          </div>
        )}

        <div>
          <Field label="Chief complaint" required>
            <textarea
              value={form.chief_complaint}
              onChange={(e) => set("chief_complaint", e.target.value)}
              required
              rows={2}
              className="input"
              placeholder="e.g. chest pain radiating to left arm, sweating"
            />
          </Field>
        </div>

        <div>
          <div className="mb-2 text-xs font-semibold uppercase tracking-widest text-subink">Vitals</div>
          <div className="grid grid-cols-3 gap-3">
            <Field label="HR (bpm)"><input value={form.hr} onChange={(e) => set("hr", e.target.value)} type="number" className="input" /></Field>
            <Field label="BP systolic"><input value={form.bp_sys} onChange={(e) => set("bp_sys", e.target.value)} type="number" className="input" /></Field>
            <Field label="BP diastolic"><input value={form.bp_dia} onChange={(e) => set("bp_dia", e.target.value)} type="number" className="input" /></Field>
            <Field label="RR (/min)"><input value={form.rr} onChange={(e) => set("rr", e.target.value)} type="number" className="input" /></Field>
            <Field label="SpO2 (%)"><input value={form.spo2} onChange={(e) => set("spo2", e.target.value)} type="number" className="input" /></Field>
            <Field label="Temp (°F)"><input value={form.temp} onChange={(e) => set("temp", e.target.value)} type="number" step="0.1" className="input" /></Field>
          </div>
        </div>

        <div className="flex flex-wrap gap-4">
          <Toggle label="Unconscious" checked={form.unconscious} onChange={(v) => set("unconscious", v)} />
          <Toggle label="Non-verbal" checked={form.non_verbal} onChange={(v) => set("non_verbal", v)} />
          <Toggle label="Pediatric" checked={form.pediatric} onChange={(v) => set("pediatric", v)} />
        </div>

        {error && <div className="rounded-md bg-tier1/10 px-3 py-2 text-sm text-tier1">{error}</div>}

        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-md bg-teal-700 py-3 text-sm font-semibold text-white shadow-card transition hover:bg-teal-800 disabled:opacity-50"
        >
          {submitting ? "Analyzing…" : "Capture patient & get AI suggestion"}
        </button>
      </form>
    </div>
  );
}

function Field({ label, required, children }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-subink">
        {label} {required && <span className="text-tier1">*</span>}
      </span>
      {children}
    </label>
  );
}

function Toggle({ label, checked, onChange }) {
  return (
    <label className="flex cursor-pointer items-center gap-2 text-sm">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      {label}
    </label>
  );
}
