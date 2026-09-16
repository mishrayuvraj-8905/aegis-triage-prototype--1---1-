import { useEffect, useState, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import { api } from "../api.js";
import { TierBadge, ConfidenceBadge, FlagChip } from "../components/Badges.jsx";
import { confidenceLabel } from "../components/RecommendationCard.jsx";
import RecommendationCard from "../components/RecommendationCard.jsx";
import NurseDecisionPanel from "../components/NurseDecisionPanel.jsx";

const ACTION_LABEL = {
  suggested: "AI suggested",
  rechecked: "AI rechecked",
  confirmed: "Nurse confirmed",
  overridden: "Nurse overrode",
  escalated: "Nurse escalated",
  acknowledged: "Nurse acknowledged",
  marked_seen: "Marked seen",
};

const ACTOR_DOT = {
  AI: "bg-teal-500",
  nurse: "bg-tier2",
};

export default function PatientDetail() {
  const { id } = useParams();
  const [patient, setPatient] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const p = await api.getPatient(id);
      setPatient(p);
      setError(null);
    } catch (e) {
      setError(e.message);
    }
  }, [id]);

  useEffect(() => {
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, [load]);

  async function markSeen() {
    setBusy(true);
    try {
      const p = await api.markSeen(id);
      setPatient(p);
    } finally {
      setBusy(false);
    }
  }

  async function recheckNow() {
    setBusy(true);
    try {
      const p = await api.recheck(id);
      setPatient(p);
    } finally {
      setBusy(false);
    }
  }

  if (error) return <div className="text-tier1">{error}</div>;
  if (!patient) return <div className="text-subink">Loading…</div>;

  const needsRetriage =
    patient.current_esi_tier == null ||
    patient.flags?.includes("deteriorating") ||
    patient.ai_suggested_tier !== patient.current_esi_tier;

  return (
    <div className="mx-auto max-w-4xl">
      <Link to="/" className="mb-4 inline-block text-sm text-teal-700 hover:underline">
        ← Back to waiting room
      </Link>

      <div className="mb-6 flex flex-wrap items-start justify-between gap-4 rounded-xl border border-line bg-paper p-6 shadow-card">
        <div>
          <h1 className="font-display text-2xl font-semibold text-teal-950">{patient.name}</h1>
          <p className="text-sm text-subink">
            {patient.age != null ? `${patient.age} y/o` : "Age unknown"} {patient.sex || ""} &middot; arrived{" "}
            {new Date(patient.arrival_time).toLocaleTimeString()} &middot; status: {patient.status}
          </p>
          <p className="mt-2 text-sm text-ink">{patient.chief_complaint}</p>
          {(patient.known_conditions?.length > 0 || patient.medications?.length > 0) && (
            <p className="mt-1 text-xs text-subink">
              {patient.known_conditions?.length > 0 && <>Conditions: {patient.known_conditions.join(", ")}. </>}
              {patient.medications?.length > 0 && <>Meds: {patient.medications.join(", ")}.</>}
            </p>
          )}
        </div>
        <div className="flex flex-col items-end gap-2">
          <TierBadge tier={patient.current_esi_tier} size="lg" />
          <span className="text-xs text-subink">
            {patient.current_esi_tier != null ? "Nurse-confirmed tier" : "Awaiting confirmation"}
          </span>
        </div>
      </div>

      <div className="mb-6 grid grid-cols-3 gap-3 sm:grid-cols-6">
        <Vital label="HR" value={patient.hr} unit="bpm" />
        <Vital label="BP" value={patient.bp_sys != null ? `${patient.bp_sys}/${patient.bp_dia ?? "\u2013"}` : null} />
        <Vital label="RR" value={patient.rr} unit="/min" />
        <Vital label="SpO₂" value={patient.spo2} unit="%" />
        <Vital label="Temp" value={patient.temp} unit="°F" />
        <Vital label="Prior ED" value={patient.prior_ed_visits} unit="visits" />
      </div>

      {patient.flags?.length > 0 && (
        <div className="mb-6 flex flex-wrap gap-1.5">
          {patient.flags.map((f) => (
            <FlagChip key={f} flag={f} />
          ))}
        </div>
      )}

      {needsRetriage ? (
        <div className="mb-8 space-y-4">
          {patient.flags?.includes("deteriorating") && (
            <div className="rounded-lg border border-tier1/50 bg-tier1/5 px-4 py-3 text-sm text-tier1">
              This patient's risk has crept up while waiting. The AI's new suggestion is below — the
              confirmed tier has not changed automatically.
            </div>
          )}
          <RecommendationCard patient={patient} />
          <NurseDecisionPanel patient={patient} onUpdated={setPatient} />
        </div>
      ) : (
        <div className="mb-8 flex flex-wrap items-center gap-3 rounded-xl border border-line bg-paper p-5 shadow-card">
          <ConfidenceBadge confidence={patient.ai_confidence} label={confidenceLabel(patient.ai_confidence)} />
          <p className="flex-1 text-sm text-ink">{patient.ai_reason}</p>
          <div className="flex gap-2">
            <button onClick={recheckNow} disabled={busy} className="rounded-md border border-line px-3 py-1.5 text-xs font-medium hover:bg-bone disabled:opacity-50">
              Recheck now
            </button>
            {patient.status !== "seen" && (
              <button onClick={markSeen} disabled={busy} className="rounded-md bg-teal-700 px-3 py-1.5 text-xs font-semibold text-white hover:bg-teal-800 disabled:opacity-50">
                Mark seen
              </button>
            )}
          </div>
        </div>
      )}

      <div>
        <h2 className="mb-3 font-display text-lg font-semibold text-teal-950">Audit trail</h2>
        <p className="mb-3 text-sm text-subink">A clear record behind every triage decision.</p>
        <ol className="space-y-0">
          {patient.events.map((e, i) => (
            <li key={e.id} className="relative flex gap-4 pb-6 last:pb-0">
              <div className="flex flex-col items-center">
                <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${ACTOR_DOT[e.actor] || "bg-subink"}`} />
                {i < patient.events.length - 1 && <span className="mt-1 w-px flex-1 bg-line" />}
              </div>
              <div className="flex-1 rounded-lg border border-line bg-paper p-4 shadow-card">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-sm font-semibold text-ink">
                    {ACTION_LABEL[e.action] || e.action}
                    <span className="ml-2 text-xs font-normal text-subink">by {e.actor}</span>
                  </span>
                  <span className="font-mono text-xs text-subink">{new Date(e.timestamp).toLocaleString()}</span>
                </div>
                <div className="mt-1 flex items-center gap-2 text-sm">
                  {e.from_tier != null && <TierBadge tier={e.from_tier} />}
                  {e.from_tier != null && e.to_tier != null && <span className="text-subink">→</span>}
                  {e.to_tier != null && <TierBadge tier={e.to_tier} />}
                  {e.confidence != null && <ConfidenceBadge confidence={e.confidence} label={confidenceLabel(e.confidence)} />}
                </div>
                {e.reason && <p className="mt-1.5 text-sm text-subink">{e.reason}</p>}
              </div>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}

function Vital({ label, value, unit }) {
  const missing = value === null || value === undefined;
  return (
    <div className={`rounded-lg border p-3 text-center ${missing ? "border-line bg-bone" : "border-line bg-paper"}`}>
      <div className="text-[10px] uppercase tracking-wide text-subink">{label}</div>
      <div className={`font-mono text-lg font-medium ${missing ? "text-subink/50" : "text-ink"}`}>
        {missing ? "\u2013" : value}
      </div>
      {!missing && unit && <div className="text-[10px] text-subink">{unit}</div>}
    </div>
  );
}
