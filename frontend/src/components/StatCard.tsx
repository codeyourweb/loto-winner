import { formatEuros2, formatSigned } from "../format";

interface StatCardProps {
  label: string;
  value: string;
  variant?: "neutral" | "positive" | "negative";
  hint?: string;
}

/** Synthetic card displayed in the results dashboard. */
export function StatCard({ label, value, variant = "neutral", hint }: StatCardProps) {
  const className = ["stat-card", `stat-${variant}`].join(" ");

  return (
    <article className={className}>
      <p className="stat-label">{label}</p>
      <p className="stat-value">{value}</p>
      {hint ? <p className="stat-hint">{hint}</p> : null}
    </article>
  );
}

interface NetCardProps {
  net: number;
  roi: number;
  stakePerDraw: number;
}

/** Carte de bilan mise en avant (gains - mises). */
export function NetCard({ net, roi, stakePerDraw }: NetCardProps) {
  const positive = net >= 0;
  return (
    <article className={`net-card ${positive ? "net-positive" : "net-negative"}`}>
      <p className="stat-label">Bilan cumulé (gains − mises)</p>
      <p className="net-value">{formatSigned(net)}</p>
      <p className="stat-hint">
        Retour sur mise : {roi > 0 ? "+" : ""}
        {roi.toFixed(2).replace(".", ",")} % · {formatEuros2(stakePerDraw)} par tirage
      </p>
    </article>
  );
}
