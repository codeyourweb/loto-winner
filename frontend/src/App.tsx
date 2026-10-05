import { useCallback, useEffect, useMemo, useState } from "react";

import { api } from "./api";
import { JackpotHistory } from "./components/JackpotHistory";
import { ChancePicker, LotoGrid, SelectionPreview } from "./components/LotoGrid";
import { RankTable } from "./components/RankTable";
import { ResultsPanel } from "./components/ResultsPanel";
import { formatDate, formatEuro } from "./format";
import type {
  AppConfig,
  DataSourceInfo,
  Draw,
  JackpotDraw,
  SimulationResult,
} from "./types";

const DRAW_HISTORY_PAGE = 10;
const JACKPOT_HISTORY_PAGE = 6;

function randomSelection(total: number, pickCount: number, chanceMax: number) {
  const pool = Array.from({ length: total }, (_, index) => index + 1);
  const picked: number[] = [];
  while (picked.length < pickCount) {
    const index = Math.floor(Math.random() * pool.length);
    picked.push(pool.splice(index, 1)[0]);
  }
  return {
    numbers: picked.sort((a, b) => a - b),
    chance: Math.floor(Math.random() * chanceMax) + 1,
  };
}

export default function App() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [numbers, setNumbers] = useState<number[]>([]);
  const [chance, setChance] = useState<number | null>(null);

  const [result, setResult] = useState<SimulationResult | null>(null);
  const [draws, setDraws] = useState<Draw[]>([]);
  const [jackpots, setJackpots] = useState<JackpotDraw[]>([]);
  const [jackpotTotal, setJackpotTotal] = useState(0);
  const [dataSource, setDataSource] = useState<DataSourceInfo | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  // Initial load: game rules, latest draws and won jackpots.
  useEffect(() => {
    let cancelled = false;

    Promise.all([
      api.config(),
      api.draws(DRAW_HISTORY_PAGE),
      api.jackpots(JACKPOT_HISTORY_PAGE),
      api.dataSource(),
    ])
      .then(([cfg, history, jackpotHistory, source]) => {
        if (cancelled) return;
        setConfig(cfg);
        setDraws(history.draws);
        setJackpots(jackpotHistory.jackpots);
        setJackpotTotal(jackpotHistory.total);
        setDataSource(source);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const pickCount = config?.pick_count ?? 5;
  const chanceMax = config?.chance_max ?? 10;
  const totalNumbers = config?.total_numbers ?? 49;

  const canRun = numbers.length === pickCount && chance !== null;

  const handleToggle = useCallback(
    (value: number) => {
      setNumbers((current) => {
        if (current.includes(value)) {
          return current.filter((item) => item !== value);
        }
        if (current.length >= pickCount) {
          return current;
        }
        return [...current, value].sort((a, b) => a - b);
      });
    },
    [pickCount]
  );

  const handleRandom = useCallback(() => {
    const pick = randomSelection(totalNumbers, pickCount, chanceMax);
    setNumbers(pick.numbers);
    setChance(pick.chance);
  }, [totalNumbers, pickCount, chanceMax]);

  const handleClear = useCallback(() => {
    setNumbers([]);
    setChance(null);
  }, []);

  const handleSimulate = useCallback(async () => {
    if (!canRun || chance === null) return;

    setLoading(true);
    setError(null);
    try {
      const simulation = await api.simulate(numbers, chance);
      setResult(simulation);
      setExportError(null);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }, [canRun, chance, numbers]);

  const handleExportPdf = useCallback(async () => {
    if (!result) return;

    setExporting(true);
    setExportError(null);
    try {
      await api.downloadPdf(result.summary.numbers, result.summary.chance);
    } catch (err) {
      setExportError((err as Error).message);
    } finally {
      setExporting(false);
    }
  }, [result]);

  const jackpotPreview = useMemo(() => {
    if (draws.length === 0) return null;
    return formatEuro(draws[0].jackpot);
  }, [draws]);

  return (
    <div className="app">
      <header className="hero">
        <div className="hero-text">
          <p className="eyebrow">Simulateur LOTO · La Française des Jeux</p>
          <h1>
            <span className="hero-logo">🎯</span> Loto Winner
          </h1>
          <p className="hero-subtitle">
            Composez votre grille, puis laissez l'algorithme rejouer ces 5 numéros et ce numéro
            chance sur tout l'historique du LOTO. Vous saurez enfin combien vous auriez gagné —
            ou perdu — et quand la cagnotte aurait basculé.
          </p>
          {jackpotPreview ? (
            <p className="hero-jackpot">
              Cagnotte estimée au prochain tirage : <strong>{jackpotPreview}</strong>
            </p>
          ) : null}
        </div>
      </header>

      <main className="layout">
        <section className="panel panel-play">
          <h2>1. Votre grille</h2>
          <p className="step-hint">
            Cochez {pickCount} numéros parmi {totalNumbers}, puis choisissez votre numéro chance
            (1 à {chanceMax}).
          </p>

          <SelectionPreview
            numbers={numbers}
            chance={chance}
            onClear={handleClear}
            onRandom={handleRandom}
            disabled={loading}
          />

          <LotoGrid
            selected={numbers}
            onToggle={handleToggle}
            disabled={loading}
            pickCount={pickCount}
          />

          <ChancePicker
            value={chance}
            onChange={setChance}
            disabled={loading}
            chanceMax={chanceMax}
          />

          <div className="options">
            <p className="data-source-note">
              {dataSource?.is_real_data
                ? `Données officielles FDJ — ${dataSource.counts.fdj} tirages réels importés (${dataSource.first_draw} → ${dataSource.last_draw}).`
                : "Données simulées de secours (hors ligne) — activez la connexion réseau pour importer l'historique officiel FDJ."}
            </p>
          </div>

          <button
            type="button"
            className="btn btn-primary"
            onClick={handleSimulate}
            disabled={!canRun || loading}
          >
            {loading ? "Simulation en cours…" : "🚀 Lancer la simulation"}
          </button>

          {error ? <p className="error-banner">⚠️ {error}</p> : null}
        </section>

        <aside className="panel panel-rules">
          <h2>2. Barème des gains</h2>
          <p className="step-hint">
            Le LOTO comporte <strong>9 rangs</strong>. Le rang 1 désigne la cagnotte. Les montants
            affichés sont des ordres de grandeur : chaque gain réel provient du rapport officiel du
            tirage concerné.
          </p>
          {config ? <RankTable ranks={config.ranks} /> : <p className="empty-state">Chargement…</p>}

          <h2 className="panel-subtitle">Derniers tirages</h2>
          <ul className="draws-list">
            {draws.map((draw) => (
              <li key={draw.date}>
                <span className="draw-date">{formatDate(draw.date)}</span>
                <span className="draw-balls">
                  {draw.numbers.join(" · ")} <em>+ chance {draw.chance}</em>
                </span>
              </li>
            ))}
          </ul>

          <h2 className="panel-subtitle">Cagnottes remportées</h2>
          <JackpotHistory jackpots={jackpots} total={jackpotTotal} />
        </aside>

        {result ? (
          <div className="panel panel-results">
            <ResultsPanel
              result={result}
              onExportPdf={handleExportPdf}
              exporting={exporting}
              exportError={exportError}
            />
          </div>
        ) : (
          <div className="panel panel-placeholder">
            <h2>3. Vos gains et pertes</h2>
            <p className="empty-state">
              Lancez une simulation pour découvrir votre bilan cumulé, la dernière fois où la
              série aurait décroché la cagnotte, et l'évolution de vos gains dans le temps.
            </p>
          </div>
        )}
      </main>

      <footer className="footer">
        <p>
          Projet pédagogique indépendant — non affilié à La Française des Jeux. Les tirages sont
          simulés à des fins de démonstration.
        </p>
        <p>Jouer comporte des risques : endettement, isolement, dépendance.</p>
      </footer>
    </div>
  );
}
