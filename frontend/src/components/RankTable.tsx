import type { RankRule } from "../types";

interface RankTableProps {
  ranks: RankRule[];
}

const MEDALS: Record<number, string> = {
  1: "🏆",
  2: "🥈",
  3: "🥉",
};

/** Simplified official payout scale for the 10 LOTO ranks. */
export function RankTable({ ranks }: RankTableProps) {
  return (
    <table className="rank-table">
      <thead>
        <tr>
          <th>Rang</th>
          <th>Combinaison</th>
          <th className="align-right">Gain</th>
        </tr>
      </thead>
      <tbody>
        {ranks.map((rule) => (
          <tr key={rule.rank} className={rule.is_jackpot ? "row-jackpot" : undefined}>
            <td>
              <span className="rank-badge">{MEDALS[rule.rank] ?? rule.rank}</span>
            </td>
            <td>{rule.label}</td>
            <td className="align-right">
              {rule.is_jackpot ? (
                <span className="jackpot-label">Cagnotte variable</span>
              ) : (
                <span className="fallback-gain">
                  {rule.gain?.toFixed(2).replace(".", ",")} € <em>min.</em>
                </span>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
