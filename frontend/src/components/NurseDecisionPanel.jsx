import { useState } from "react";
import { api } from "../api.js";
import { confidenceLabel } from "./RecommendationCard.jsx";

export default function NurseDecisionPanel({ patient, onUpdated }) {
  const [mode, setMode] = useState(null); // null | "override" | "escalate"
  const [tier, setTier] = useState(patient.ai_suggested_tier);
  const [reason, setReason] = useState("");
  const [acking, setAcking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const needsAck = patient.ack_required && !patient.acknowledged;

  async function acknowledge() {
    setAcking(true);
    setError(null);
    try {
      const updated = await api.acknowledge(patient.id);
      onUpdated(updated);
    } catch (e) {
      setError(e.message);
    } finally {
      setAcking(false);
    }
  }

  async function doConfirm() {
    setBusy(true);
    setError(null);
    try {
      const updated = await api.confirm(patient.id, true);
      onUpdated(updated);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function doOverride() {
    if (!reason.trim()) {
      setError("Please enter a one-line reason for the override.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const updated = await api.override(patient.id, Number(tier), reason.trim(), true);
      onUpdated(updated);
      setMode(null);
      setReason("");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function doEscalate() {
    if (!reason.trim()) {
      setError("Please enter a reason for the escalation.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const updated = await api.escalate(patient.id, reason.trim());
      onUpdated(updated);
      setMode(null);
      setReason("");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (needsAck) {
    return (
      <div className="rounded-xl border border-tier1/50 bg-tier1/5 p-5">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 h-2.5 w-2.5 shrink-0 rounded-full bg-tier1 blip-dot" />
          <div>
            <div className="font-display font-semibold text-tier1">
              Level {patient.ai_suggested_tier} suggestion needs explicit acknowledgment
            </div>
            <p className="mt-1 text-sm text-ink/80">
              This is a high-acuity AI suggestion (
              {confidenceLabel(patient.ai_confidence)} confidence). Read the reasoning above, then
              acknowledge before you can confirm or override.
            </p>
            {error && <p className="mt-2 text-sm text-tier1">{error}</p>}
            <button
              onClick={acknowledge}
              disabled={acking}
              className="mt-3 rounded-md bg-tier1 px-4 py-2 text-sm font-semibold text-white transition hover:bg-tier1/90 disabled:opacity-50"
            >
              {acking ? "Acknowledging…" : "I've reviewed this — acknowledge"}
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-line bg-paper p-5 shadow-card">
      <div className="mb-3 text-xs font-semibold uppercase tracking-widest text-subink">Nurse Decision</div>

      {error && <div className="mb-3 rounded-md bg-tier1/10 px-3 py-2 text-sm text-tier1">{error}</div>}

      {mode === null && (
        <div className="flex flex-wrap gap-2">
          <button
            onClick={doConfirm}
            disabled={busy}
            className="rounded-md bg-teal-700 px-4 py-2 text-sm font-semibold text-white transition hover:bg-teal-800 disabled:opacity-50"
          >
            Confirm tier {patient.ai_suggested_tier}
          </button>
          <button
            onClick={() => { setMode("override"); setTier(patient.ai_suggested_tier); }}
            className="rounded-md border border-line px-4 py-2 text-sm font-medium text-ink transition hover:bg-bone"
          >
            Override
          </button>
          <button
            onClick={() => setMode("escalate")}
            className="rounded-md border border-tier1/40 px-4 py-2 text-sm font-medium text-tier1 transition hover:bg-tier1/5"
          >
            Escalate for senior review
          </button>
        </div>
      )}

      {mode === "override" && (
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-subink">New ESI tier</label>
            <select
              value={tier}
              onChange={(e) => setTier(e.target.value)}
              className="w-full rounded-md border border-line bg-paper px-3 py-2 text-sm"
            >
              {[1, 2, 3, 4, 5].map((t) => (
                <option key={t} value={t}>
                  ESI {t}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-subink">Reason (required)</label>
            <input
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="One line explaining the override…"
              className="w-full rounded-md border border-line bg-paper px-3 py-2 text-sm"
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={doOverride}
              disabled={busy}
              className="rounded-md bg-teal-700 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-800 disabled:opacity-50"
            >
              Save override
            </button>
            <button
              onClick={() => { setMode(null); setError(null); }}
              className="rounded-md border border-line px-4 py-2 text-sm font-medium text-ink hover:bg-bone"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {mode === "escalate" && (
        <div className="space-y-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-subink">Reason for escalation (required)</label>
            <input
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="What should the senior reviewer know?"
              className="w-full rounded-md border border-line bg-paper px-3 py-2 text-sm"
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={doEscalate}
              disabled={busy}
              className="rounded-md bg-tier1 px-4 py-2 text-sm font-semibold text-white hover:bg-tier1/90 disabled:opacity-50"
            >
              Escalate
            </button>
            <button
              onClick={() => { setMode(null); setError(null); }}
              className="rounded-md border border-line px-4 py-2 text-sm font-medium text-ink hover:bg-bone"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
