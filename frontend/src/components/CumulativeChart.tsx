import type { TimelineEntry } from "../types";
import { formatDate, formatEuro, formatSigned } from "../format";

interface CumulativeChartProps {
  timeline: TimelineEntry[];
}

const WIDTH = 900;
const HEIGHT = 280;
const PADDING = 32;

/** Cumulative curve (winnings − stakes) over the whole played period. */
export function CumulativeChart({ timeline }: CumulativeChartProps) {
  if (timeline.length < 2) {
    return null;
  }

  const values = timeline.map((entry) => entry.cumulative);
  const min = Math.min(...values, 0);
  const max = Math.max(...values, 0);
  const span = max - min || 1;

  const innerWidth = WIDTH - PADDING * 2;
  const innerHeight = HEIGHT - PADDING * 2;

  const xFor = (index: number) => PADDING + (index / (timeline.length - 1)) * innerWidth;
  const yFor = (value: number) => PADDING + innerHeight - ((value - min) / span) * innerHeight;

  const linePath = values
    .map((value, index) => `${index === 0 ? "M" : "L"} ${xFor(index).toFixed(2)} ${yFor(value).toFixed(2)}`)
    .join(" ");

  const zeroY = yFor(0);
  const areaPath = `${linePath} L ${xFor(timeline.length - 1).toFixed(2)} ${zeroY.toFixed(
    2
  )} L ${xFor(0).toFixed(2)} ${zeroY.toFixed(2)} Z`;

  const lastValue = values[values.length - 1];
  const positive = lastValue >= 0;

  return (
    <figure className="chart">
      <figcaption className="chart-caption">
        Évolution du cumul, de {formatDate(timeline[0].date)} à{" "}
        {formatDate(timeline[timeline.length - 1].date)}
      </figcaption>
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label="Évolution du bilan cumulé">
        <defs>
          <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={positive ? "#22c55e" : "#ef4444"} stopOpacity="0.35" />
            <stop offset="100%" stopColor={positive ? "#22c55e" : "#ef4444"} stopOpacity="0" />
          </linearGradient>
        </defs>

        <line x1={PADDING} y1={zeroY} x2={WIDTH - PADDING} y2={zeroY} className="chart-zero" />

        <path d={areaPath} fill="url(#areaGradient)" stroke="none" />
        <path d={linePath} className={positive ? "chart-line positive" : "chart-line negative"} />

        <circle cx={xFor(timeline.length - 1)} cy={yFor(lastValue)} r={5}
          className={positive ? "chart-dot positive" : "chart-dot negative"} />

        <text x={PADDING} y={PADDING - 8} className="chart-axis-label">
          {formatEuro(max)}
        </text>
        <text x={PADDING} y={HEIGHT - 8} className="chart-axis-label">
          {formatEuro(min)}
        </text>
      </svg>
      <p className="chart-footnote">
        Dernier cumul : <strong>{formatSigned(lastValue)}</strong>
      </p>
    </figure>
  );
}
