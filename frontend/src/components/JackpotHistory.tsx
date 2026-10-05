import type { JackpotDraw } from "../types";
import { formatDate, formatEuro } from "../format";
import { NumberBall } from "./NumberBall";

interface JackpotHistoryProps {
  jackpots: JackpotDraw[];
  total: number;
}

/** The latest draws where the jackpot (rank 1) was actually won. */
export function JackpotHistory({ jackpots, total }: JackpotHistoryProps) {
  return (
    <div className="jackpot-history">
      <p className="step-hint">
        {total} tirages réels ont vu la cagnotte tomber sur la période importée. Une grille fixe a
        statistiquement une chance sur 19 068 840 de décrocher le rang 1 à un tirage donné — mais
        jouée sur la durée, tout tirage finit par sortir.
      </p>
      <ul className="jackpot-list">
        {jackpots.map((draw) => (
          <li key={draw.date}>
            <div className="jackpot-head">
              <span className="draw-date">{formatDate(draw.date)}</span>
              <span className="jackpot-amount">{formatEuro(draw.jackpot)}</span>
            </div>
            <div className="jackpot-balls">
              {draw.numbers.map((number) => (
                <NumberBall key={number} value={number} size="sm" />
              ))}
              <span className="preview-plus">+</span>
              <NumberBall value={draw.chance} variant="chance" size="sm" />
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
