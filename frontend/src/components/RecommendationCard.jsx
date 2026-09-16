import { TierBadge, TierLabel, ConfidenceBadge, FlagChip } from "./Badges.jsx";

export default function RecommendationCard({ patient }) {
  if (!patient) return null;
  const isHighAcuity = patient.ai_suggested_tier <= 2;

  return (
    <div
      className={`rounded-xl border bg-paper p-5 shadow-card ${
        isHighAcuity ? "border-tier1/50" : "border-line"
      }`}
    >
      <div className="mb-3 flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-widest text-subink">AI Recommendation</span>
        {isHighAcuity && (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-tier1/10 px-2.5 py-1 text-[11px] font-semibold text-tier1">
            <span className="h-1.5 w-1.5 rounded-full bg-tier1 blip-dot" />
            Requires acknowledgment
          </span>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <TierBadge tier={patient.ai_suggested_tier} size="lg" />
        <TierLabel tier={patient.ai_suggested_tier} />
        <ConfidenceBadge confidence={patient.ai_confidence} label={confidenceLabel(patient.ai_confidence)} />
      </div>

      <p className="mt-3 text-sm leading-relaxed text-ink">{patient.ai_reason}</p>

      <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
        <div className="rounded-lg bg-bone p-3">
          <div className="text-[11px] uppercase tracking-wide text-subink">Suggested path</div>
          <div className="font-medium">{patient.ai_resource_path}</div>
        </div>
        <div className="rounded-lg bg-bone p-3">
          <div className="text-[11px] uppercase tracking-wide text-subink">Recheck interval</div>
          <div className="font-medium">every {patient.recheck_interval_minutes} min</div>
        </div>
      </div>

      {patient.ai_suggested_orders?.length > 0 && (
        <div className="mt-4 rounded-lg border border-teal-600/30 bg-teal-600/5 p-3">
          <div className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-teal-800">
            Staged order set &middot; nurse confirms to accept
          </div>
          <ul className="space-y-1 text-sm text-ink">
            {patient.ai_suggested_orders.map((o) => (
              <li key={o} className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-teal-600" />
                {o}
              </li>
            ))}
          </ul>
        </div>
      )}

      {patient.ai_model_tier != null && (
        <div className="mt-3 flex items-center gap-2 text-xs text-subink">
          <span className="rounded border border-line px-1.5 py-0.5 font-mono">
            ML second opinion: ESI {patient.ai_model_tier} ({Math.round((patient.ai_model_confidence || 0) * 100)}%)
          </span>
          {patient.ai_model_tier !== patient.ai_suggested_tier && (
            <span className="text-tier2">differs from final — see flags</span>
          )}
        </div>
      )}

      {patient.flags?.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {patient.flags.map((f) => (
            <FlagChip key={f} flag={f} />
          ))}
        </div>
      )}
    </div>
  );
}

export function confidenceLabel(confidence) {
  if (confidence >= 0.75) return "High";
  if (confidence >= 0.5) return "Medium";
  return "Low";
}
