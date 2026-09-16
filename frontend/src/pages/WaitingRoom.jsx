import { useEffect, useState, useCallback, useRef } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { TierBadge, FlagChip } from "../components/Badges.jsx";

const POLL_MS = 15000;

function useNow(tickMs = 1000) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), tickMs);
    return () => clearInterval(id);
  }, [tickMs]);
  return now;
}

function formatWait(arrivalIso, now) {
  const arrival = new Date(arrivalIso).getTime();
  const mins = Math.max(0, Math.floor((now - arrival) / 60000));
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
}

function formatRecheckCountdown(patient, now, speedup) {
  const last = new Date(patient.last_rechecked_at).getTime();
  const elapsedRealSeconds = (now - last) / 1000;
  const elapsedSimMinutes = (elapsedRealSeconds * speedup) / 60;
  const remaining = Math.ceil(patient.recheck_interval_minutes - elapsedSimMinutes);
  if (remaining <= 0) return "due now";
  return `${remaining}m`;
}

export default function WaitingRoom() {
  const [patients, setPatients] = useState([]);
  const [speedup, setSpeedup] = useState(60);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const now = useNow(1000);
  const pollRef = useRef(null);

  const load = useCallback(async () => {
    try {
      const [list, cfg] = await Promise.all([
        api.listPatients("waiting"),
        api.config().catch(() => ({ demo_speedup: 60 })),
      ]);
      setPatients(list);
      setSpeedup(cfg.demo_speedup || 60);
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    pollRef.current = setInterval(load, POLL_MS);
    return () => clearInterval(pollRef.current);
  }, [load]);

  const deteriorating = patients.filter((p) => p.flags?.includes("deteriorating"));
  const rest = patients.filter((p) => !p.flags?.includes("deteriorating"));

  return (
    <div>
      <div className="mb-6 flex items-end justify-between">
        <div>
          <h1 className="font-display text-2xl font-semibold text-teal-950">Waiting Room</h1>
          <p className="text-sm text-subink">
            {patients.length} patient{patients.length !== 1 ? "s" : ""} waiting &middot; refreshes every {POLL_MS / 1000}s
          </p>
        </div>
        <Link
          to="/intake"
          className="rounded-md bg-teal-700 px-4 py-2 text-sm font-semibold text-white shadow-card hover:bg-teal-800"
        >
          + New patient
        </Link>
      </div>

      {error && <div className="mb-4 rounded-md bg-tier1/10 px-4 py-3 text-sm text-tier1">Couldn't reach the API: {error}</div>}

      {loading ? (
        <div className="text-sm text-subink">Loading board…</div>
      ) : patients.length === 0 ? (
        <div className="rounded-xl border border-line bg-paper p-8 text-center text-subink">
          No one's waiting right now.
        </div>
      ) : (
        <div className="space-y-6">
          {deteriorating.length > 0 && (
            <section>
              <h2 className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-widest text-tier1">
                <span className="h-2 w-2 rounded-full bg-tier1 blip-dot" />
                Needs re-triage &middot; risk has crept up
              </h2>
              <div className="space-y-2">
                {deteriorating.map((p) => (
                  <PatientRow key={p.id} patient={p} now={now} speedup={speedup} alert />
                ))}
              </div>
            </section>
          )}

          <section>
            {deteriorating.length > 0 && (
              <h2 className="mb-2 text-xs font-semibold uppercase tracking-widest text-subink">
                Rest of the queue
              </h2>
            )}
            <div className="space-y-2">
              {rest.map((p) => (
                <PatientRow key={p.id} patient={p} now={now} speedup={speedup} />
              ))}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}

function PatientRow({ patient, now, speedup, alert }) {
  const countdown = formatRecheckCountdown(patient, now, speedup);
  const isTriaged = patient.current_esi_tier != null;

  return (
    <Link
      to={`/patients/${patient.id}`}
      className={`flex items-center gap-4 rounded-xl border bg-paper p-4 shadow-card transition hover:border-teal-500 ${
        alert ? "border-tier1/60 animate-alert" : "border-line"
      }`}
    >
      <div className="flex w-24 flex-col items-start gap-1">
        <TierBadge tier={patient.current_esi_tier ?? patient.ai_suggested_tier} />
        {!isTriaged && <span className="text-[10px] uppercase tracking-wide text-subink">AI suggested</span>}
      </div>

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="font-display font-semibold text-ink">{patient.name}</span>
          {patient.age != null && <span className="text-xs text-subink">{patient.age}{patient.sex ? `${patient.sex}` : ""}</span>}
        </div>
        <p className="truncate text-sm text-subink">{patient.chief_complaint || "\u2014"}</p>
      </div>

      <div className="hidden shrink-0 items-center gap-1.5 sm:flex">
        {patient.flags?.slice(0, 3).map((f) => (
          <FlagChip key={f} flag={f} />
        ))}
      </div>

      <div className="w-24 shrink-0 text-right font-mono text-sm text-ink">
        {formatWait(patient.arrival_time, now)}
      </div>

      <div className="w-24 shrink-0 text-right">
        <div className="text-[10px] uppercase tracking-wide text-subink">Recheck</div>
        <div className={`font-mono text-sm ${countdown === "due now" ? "text-tier2 font-semibold" : "text-ink"}`}>
          {countdown}
        </div>
      </div>
    </Link>
  );
}
