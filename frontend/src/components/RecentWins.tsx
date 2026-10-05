import type { SimulationResult } from "../types";
import { formatDate, formatEuro, formatSigned } from "../format";

interface RecentWinsProps {
  timeline: SimulationResult["timeline"];
}

/** The 8 best results of the series over the whole history. */
export function RecentWins({ timeline }: RecentWinsProps) {
  const wins = timeline
    .filter((entry) => entry.gain > 0)
    .sort((a, b) => b.gain - a.gain)
    .slice(0, 8);

  if (wins.length === 0) {
    return (
      <p className="empty-state">
        Aucun gain sur toute la période. Cette grille n'a jamais rien rapporté 😢
      </p>
    );
  }

  return (
    <table className="wins-table">
      <thead>
        <tr>
          <th>Date du tirage</th>
          <th>Correspondances</th>
          <th className="align-right">Gain</th>
        </tr>
      </thead>
      <tbody>
        {wins.map((entry) => (
          <tr key={entry.date} className={entry.isJackpot ? "row-jackpot" : undefined}>
            <td>{formatDate(entry.date)}</td>
            <td>
              {entry.matches} n°{entry.isJackpot ? " + n° chance" : ""}
              {entry.rank ? <span className="rank-tag">rang {entry.rank}</span> : null}
            </td>
            <td className="align-right positive-text">{formatEuro(entry.gain)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Highlight: jackpot won and best approach of the grid. */
export function BestRankHighlight({ result }: { result: SimulationResult }) {
  const { summary, jackpot } = result;

  return (
    <div className="highlight">
      <div>
        <p className="highlight-title">Cagnotte (rang 1) décrochée</p>
        <p className="highlight-value">
          {jackpot.hits > 0 && jackpot.last_date
            ? formatDate(jackpot.last_date)
            : "Jamais avec cette grille"}
        </p>
        <p className="stat-hint">
          {jackpot.hits > 0
            ? `${jackpot.hits} fois sur ${summary.total_draws} tirages · jusqu'à ${formatSigned(
                Math.max(...jackpot.amounts)
              )}`
            : `1 chance sur 19 068 840 à chaque tirage.`}
        </p>
      </div>
      <div>
        <p className="highlight-title">Meilleure approche & meilleur gain</p>
        <p className="highlight-value">{formatSigned(summary.biggest_win)}</p>
        <p className="stat-hint">
          {summary.best_rank_label
            ? `${summary.best_rank_label} le ${
                summary.best_rank_date ? formatDate(summary.best_rank_date) : "—"
              }${
                summary.best_rank_numbers
                  ? ` · tirage ${summary.best_rank_numbers.join(" - ")}`
                  : ""
              }`
            : "Aucun rang atteint sur la période"}
        </p>
      </div>
    </div>
  );
}
