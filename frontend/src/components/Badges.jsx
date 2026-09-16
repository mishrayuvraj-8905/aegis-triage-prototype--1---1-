const TIER_COLORS = {
  1: "bg-tier1 text-white",
  2: "bg-tier2 text-white",
  3: "bg-tier3 text-ink",
  4: "bg-tier4 text-white",
  5: "bg-tier5 text-white",
};

const TIER_LABELS = {
  1: "Resuscitation",
  2: "Emergent",
  3: "Urgent",
  4: "Less urgent",
  5: "Non-urgent",
};

export function TierBadge({ tier, size = "md" }) {
  if (!tier) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-line bg-paper px-2.5 py-1 text-xs font-medium text-subink">
        Unscored
      </span>
    );
  }
  const sizeCls = size === "lg" ? "px-4 py-2 text-lg" : "px-2.5 py-1 text-sm";
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full font-display font-semibold ${sizeCls} ${TIER_COLORS[tier]}`}
      title={TIER_LABELS[tier]}
    >
      ESI {tier}
    </span>
  );
}

export function TierLabel({ tier }) {
  return <span className="text-subink text-sm">{TIER_LABELS[tier] || ""}</span>;
}

export function ConfidenceBadge({ confidence, label }) {
  const pct = Math.round((confidence || 0) * 100);
  const colorClass =
    label === "High" ? "text-teal-700 border-teal-700" :
    label === "Medium" ? "text-tier3 border-tier3" :
    "text-tier1 border-tier1";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-xs font-mono font-medium ${colorClass}`}>
      {label} · {pct}%
    </span>
  );
}

export function FlagChip({ flag }) {
  const styles = {
    deteriorating: "bg-tier1/10 text-tier1 border-tier1/40",
    low_confidence: "bg-tier3/10 text-tier3 border-tier3/40",
    missing_data: "bg-subink/10 text-subink border-subink/30",
    vague_complaint: "bg-subink/10 text-subink border-subink/30",
    conflicting_signals: "bg-tier2/10 text-tier2 border-tier2/40",
    pediatric: "bg-teal-600/10 text-teal-700 border-teal-600/40",
    escalated: "bg-tier1/10 text-tier1 border-tier1/40",
    "forced-critical": "bg-tier1/10 text-tier1 border-tier1/40",
    "forced-non-verbal": "bg-tier1/10 text-tier1 border-tier1/40",
    model_escalated: "bg-tier2/10 text-tier2 border-tier2/40",
    rules_floor_applied: "bg-teal-600/10 text-teal-700 border-teal-600/40",
  };
  const labels = {
    deteriorating: "Deteriorating",
    low_confidence: "Low confidence",
    missing_data: "Missing data",
    vague_complaint: "Vague complaint",
    conflicting_signals: "Conflicting signals",
    pediatric: "Pediatric",
    escalated: "Escalated",
    "forced-critical": "Forced critical",
    "forced-non-verbal": "Non-verbal",
    model_escalated: "ML flagged more urgent",
    rules_floor_applied: "Rules safety floor applied",
  };
  return (
    <span className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[11px] font-medium ${styles[flag] || "bg-line text-subink border-line"}`}>
      {labels[flag] || flag}
    </span>
  );
}
