import { CumulativeChart } from "./CumulativeChart";
import { BestRankHighlight, RecentWins } from "./RecentWins";
import { NetCard, StatCard } from "./StatCard";
import { formatDate, formatEuro, formatEuros2, formatPercent } from "../format";
import type { SimulationResult } from "../types";

interface ResultsPanelProps {
  result: SimulationResult;
  onExportPdf: () => void;
  exporting: boolean;
  exportError: string | null;
}

const MAX_TIMELINE_POINTS = 400;

/** Full dashboard displayed after a simulation. */
export function ResultsPanel({ result, onExportPdf, exporting, exportError }: ResultsPanelProps) {
  const { summary, jackpot, by_rank, timeline } = result;

  // The curve is sampled to keep rendering smooth over ~1350 points.
  const step = Math.max(1, Math.ceil(timeline.length / MAX_TIMELINE_POINTS));
  const sampledTimeline = timeline.filter(
    (_, index) => index % step === 0 || index === timeline.length - 1
  );

  const winningRanks = by_rank.filter((rank) => rank.count > 0);

  return (
    <section className="results" aria-live="polite">
      <header className="results-header">
        <div>
          <h2>Résultats de la simulation</h2>
          <p className="results-subtitle">
            Grille {summary.numbers.join(" - ")} + chance {summary.chance} · rejouée sur{" "}
            {summary.total_draws} tirages, du {formatDate(summary.first_draw)} au{" "}
            {formatDate(summary.last_draw)}
          </p>
          <p className="results-subtitle">
            {summary.data_source === "fdj"
              ? "Gains calculés à partir des rapports officiels FDJ de chaque tirage."
              : "⚠️ Données simulées (repli hors ligne) : les montants ne sont pas officiels."}
          </p>
          <p className="results-subtitle">
            Formule actuelle (9 rangs de gains) uniquement : les tirages antérieurs au{" "}
            {formatDate(summary.simulation_start)} sont exclus.
          </p>
        </div>
        <div className="results-actions">
          {result.simulation_id ? (
            <span className="sim-id">Simulation #{result.simulation_id}</span>
          ) : null}
          <button
            type="button"
            className="btn btn-export"
            onClick={onExportPdf}
            disabled={exporting}
          >
            {exporting ? "Génération du PDF…" : "📄 Exporter en PDF"}
          </button>
        </div>
      </header>

      {exportError ? <p className="error-banner">⚠️ {exportError}</p> : null}

      <div className="stats-grid">
        <NetCard net={summary.net} roi={summary.roi} stakePerDraw={summary.stake_per_draw} />
        <StatCard
          label="Total misé"
          value={formatEuro(summary.total_spent)}
          hint={`${summary.total_draws} tirages × ${formatEuros2(summary.stake_per_draw)}`}
        />
        <StatCard
          label="Total gagné"
          value={formatEuro(summary.total_won)}
          variant="positive"
          hint={`${summary.winning_draws} tirages gagnants (${summary.win_rate
            .toFixed(2)
            .replace(".", ",")} %)`}
        />
        <StatCard
          label="Taux de retour"
          value={formatPercent(summary.roi)}
          variant={summary.roi >= 0 ? "positive" : "negative"}
          hint="Part de la mise récupérée sur la période"
        />
      </div>

      <BestRankHighlight result={result} />

      <div className="results-grid">
        <div className="panel">
          <h3>Évolution du bilan</h3>
          <CumulativeChart timeline={sampledTimeline} />
        </div>

        <div className="panel">
          <h3>Rangs atteints</h3>
          {winningRanks.length === 0 ? (
            <p className="empty-state">Aucun rang gagnant atteint.</p>
          ) : (
            <ul className="rank-list">
              {winningRanks.map((rank) => (
                <li key={rank.rank}>
                  <span className={`rank-chip rank-${rank.rank}`}>Rang {rank.rank}</span>
                  <span className="rank-desc">{rank.label}</span>
                  <span className="rank-count">
                    ×{rank.count} · {formatEuro(rank.total_won)}
                  </span>
                </li>
              ))}
            </ul>
          )}

          <h3 className="panel-subtitle">Cagnotte</h3>
          <ul className="kv-list">
            <li>
              <span>Rang 1 remporté</span>
              <strong>{jackpot.hits} fois</strong>
            </li>
            <li>
              <span>Dernière cagnotte</span>
              <strong>{jackpot.last_date ? formatDate(jackpot.last_date) : "Jamais"}</strong>
            </li>
            <li>
              <span>Plus longue série sans rang 1</span>
              <strong>{jackpot.longest_drought_draws} tirages</strong>
            </li>
            <li>
              <span>Série actuelle sans rang 1</span>
              <strong>{jackpot.current_drought_draws} tirages</strong>
            </li>
          </ul>
        </div>
      </div>

      <div className="panel">
        <h3>Meilleurs gains de la série</h3>
        <RecentWins timeline={timeline} />
      </div>
    </section>
  );
}
