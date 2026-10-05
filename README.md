# 🎯 Loto Winner

LOTO grid simulator (La Française des Jeux): pick your 5 numbers and your lucky
number, then find out **how much you would have won — or lost —** if you had
played that combination in every draw.

## ✨ Features

| Feature | Description |
| --- | --- |
| 🎛️ Interactive grid | Choose 5 numbers (1 → 49) + 1 lucky number (1 → 10), random flash, clear. |
| 💸 Cumulative balance | Total staked, total won, **net** (winnings − stakes), return rate (ROI). |
| 📈 Trend curve | Cumulative winnings/losses draw after draw, over the whole period. |
| 🏆 Jackpot search | Detects **the last time the series would have hit the jackpot (rank 1)** and its amount. |
| 🥇 Best result | Best rank reached, date, matching draw and win. |
| 📊 9 detailed ranks | Distribution of winnings by rank according to the official payout scale. |
| 🗂️ Real history | 1 500 official FDJ draws from the **current format** (since 2017), with the real payouts per rank. |
| 🔄 Automatic update | On every startup, the history is topped up with the draws missing up to today. |
| 📄 PDF export | The full simulation report (balance, ranks, curve, best wins) downloads as a PDF. |

## 🧮 The algorithm in brief

For each draw in the **real** history, the engine compares the grid played with
the draw:

1. **Matches** — number of shared numbers (0 → 5) and lucky-number match.
2. **Rank** — deduced from the matches, according to the **9 official ranks**:
   `5 numbers + lucky number → 1` … `1 number + lucky number → 9` (no win below that).
3. **Win** — comes from the **official payout of the draw** (the `rank_reports`
   table), not from an average: rank 1 uses the jackpot actually at stake.
4. **Cumulative balance** — for each draw, `cumulative = total_won − total_staked`.
5. **Jackpot search** — the list of draws where rank 1 is reached; the **last**
   one and its associated amount are exposed.

> **Scope: current 9-rank format only (since 6 March 2017).**
> Before that date, LOTO had only **6 ranks** and the FDJ publishes no payout for
> ranks 7 to 9. Replaying those draws would produce estimated winnings ("floor"
> values) instead of the real payouts: they are therefore excluded. The replayed
> period is exposed by `simulation_start` in `summary`.

### Verified example

The grid **5 - 17 - 27 - 32 - 44 + 4** came up on **Monday 29 September 2025**
(jackpot of **23 000 000 €**, 1 rank-1 winner):

```text
Draws played  : 1500            Total staked : 3 300 €
Total won     : 23 001 027 €
Net balance   : +22 997 727 €   (rank 1 won 1 time)
```

That is the use case that motivated the import of the official data.

### Probabilities

| Event | Probability | Order of magnitude |
| --- | --- | --- |
| Rank 1 (5 numbers + lucky number) | 1 / 19 068 840 | ~19 million |
| Rank 2 (5 numbers) | 1 / 2 118 760 | ~2,1 million |
| Any 3 numbers | ~1 / 224 | ~1 in 224 draws |

## 🗃️ Data source

The application **no longer invents the draws**: it imports the official history
published for free download by La Française des Jeux, from an anonymous endpoint
(no authentication).

| FDJ archive | Period | File |
| --- | --- | --- |
| `…afm6` | Oct. 2008 → March 2017 | `nouveau_loto.csv` |
| `…afn6` | March 2017 → Feb. 2019 | `loto2017.csv` |
| `…afo6` | Feb. 2019 → Nov. 2019 | `loto_201902.csv` |
| `…afp6` | Nov. 2019 → today | `loto_201911.csv` |

Each draw keeps, in addition to the numbers: the **number of rank-1 winners**,
the **real payout of each rank** and the **jackpot actually at stake**.

> The archives also cover 1976 → 2008, but those draws belong to the **old
> format** (7 numbers): they are deliberately excluded.

> The `…afm6` archive (2008 → March 2017) is kept for **consulting** the
> history, but it belongs to the **6-rank format**: the FDJ publishes no payout
> for ranks 7 to 9 there, so these draws are **excluded from the winnings
> calculation** (see "The algorithm in brief").

### Source priority order

1. **Official FDJ archives** online (by default);
2. **local file** (`LOTO_DRAW_FILE`) in the same format, for offline use;
3. deterministic **synthetic fallback**, marked `source = simulated`, only if
   no real data is available — the interface displays this clearly.

`GET /api/data-source` indicates the origin and freshness of the data.

## 🏗️ Architecture

```
loto-winner/
├── backend/                      # Python / Flask API
│   ├── app/
│   │   ├── __init__.py           # Application factory, CORS, headers, errors
│   │   ├── config.py             # Dev / production / test config
│   │   ├── fdj_importer.py      # Import of the official FDJ archives
│   │   ├── simulated_data.py     # Fallback history (offline)
│   │   ├── db.py                 # SQLite schema + synchronisation
│   │   ├── extensions.py         # Rate limiter (Flask-Limiter)
│   │   ├── loto_logic.py         # 9 ranks, validation, real winnings
│   │   ├── pdf_report.py         # PDF report generation (ReportLab)
│   │   ├── routes.py             # REST endpoints (+ rate limiting)
│   │   ├── security.py           # Security headers + safe parsing
│   │   └── simulation_service.py # Simulation engine (full replay)
│   ├── tests/
│   │   ├── conftest.py           # Shared fixtures
│   │   ├── fixtures/             # Real excerpt of the official FDJ format
│   │   ├── functional/           # User journey
│   │   ├── technical/            # FDJ import, robustness & API contract
│   │   └── security/             # OWASP Top 10 / API Top 10
│   ├── pytest.ini
│   ├── requirements.txt
│   ├── run.py                    # Development server
│   └── wsgi.py                   # WSGI entry point (waitress/gunicorn)
├── frontend/                     # React + TypeScript interface (Vite)
│   ├── src/
│   │   ├── api.ts                # HTTP client
│   │   ├── format.ts             # FR formatting (€, dates, %)
│   │   ├── types.ts              # Shared data contracts
│   │   ├── App.tsx               # Page composition
│   │   └── components/           # Grid, results, chart, history…
│   └── vite.config.ts            # Proxy /api → Flask (port 5000)
├── scripts/                      # Cross-platform launchers
│   ├── start.ps1 / start.bat     # Development (Windows)
│   ├── start.sh                  # Development (Linux / macOS)
│   ├── start-prod.ps1            # Production (Windows / waitress)
│   └── start-prod.sh             # Production (Linux / gunicorn)
├── .env.example
└── README.md
```

## 🚀 Installation

### Quick start (provided scripts)

Windows — PowerShell:

```powershell
.\scripts\start.ps1
# or, if script execution is restricted:
.\scripts\start.bat
```

Linux / macOS — Bash:

```bash
chmod +x scripts/start.sh
./scripts/start.sh
```

The scripts check the prerequisites, create the virtualenv, install the
dependencies and then start **both servers** in parallel, wait until they are
ready and open the browser. `Ctrl+C` stops everything cleanly.

| Script | Platform | Role |
| --- | --- | --- |
| `scripts/start.ps1` | Windows (PS 5.1 / 7+) | Development: Flask + Vite |
| `scripts/start.bat` | Windows (cmd) | Shortcut to `start.ps1` |
| `scripts/start.sh` | Linux / macOS | Development: Flask + Vite |
| `scripts/start-prod.ps1` | Windows | Production: API via **waitress** |
| `scripts/start-prod.sh` | Linux / macOS | Production: API via **gunicorn**/**waitress** |

Common options:

```powershell
.\scripts\start.ps1 -BackendPort 5001 -FrontendPort 5174 -NoBrowser
.\scripts\start.ps1 -SkipInstall        # do not reinstall the dependencies
```

```bash
BACKEND_PORT=5001 FRONTEND_PORT=5174 ./scripts/start.sh --no-browser
./scripts/start.sh --skip-install
```

### Manual start

Backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

The API starts on <http://127.0.0.1:5000> and automatically generates the SQLite
`loto.db` database with ~1 370 draws (2018 → today).

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

The interface is available at <http://127.0.0.1:5173>. Vite forwards `/api/*`
calls to Flask: no CORS configuration is needed in development.

### Going to production

```bash
cp .env.example .env    # then set LOTO_SECRET_KEY and LOTO_CORS_ORIGINS
export LOTO_SECRET_KEY="$(python -c 'import secrets;print(secrets.token_hex(32))')"
export LOTO_CORS_ORIGINS="https://loto.example"
./scripts/start-prod.sh
```

The script refuses to start if the production configuration is incomplete.
Always place a **TLS reverse proxy** (nginx, Caddy, IIS) in front of the API.

## 🔌 API

| Method | Route | Description |
| --- | --- | --- |
| `GET` | `/api/health` | Service status, freshness and origin of the data |
| `GET` | `/api/data-source` | Source of the draws (real or simulated FDJ) and period covered |
| `GET` | `/api/config` | Rules, price and indicative payout scale of the 9 ranks |
| `GET` | `/api/draws?limit=&offset=` | Paginated real draws (most recent first) |
| `GET` | `/api/draws/<date>` | Details of a draw and real payouts per rank |
| `GET` | `/api/jackpots?limit=` | Draws where the jackpot was won |
| `GET` | `/api/stats/hot-numbers` | Most / least frequent numbers |
| `POST` | `/api/simulate` | Replays a grid over the whole real history |
| `POST` | `/api/simulate/pdf` | Generates the simulation report as a PDF |
| `POST` | `/api/admin/sync` | Forces a resynchronisation with the FDJ |
| `GET` | `/api/simulations?limit=` | Latest archived simulations |

Example:

```jsonc
// POST /api/simulate
{
  "numbers": [7, 13, 24, 31, 42],
  "chance": 3,
  "secondDraw": false,
  "jackpotOption": true
}
```

```jsonc
// Response (excerpt)
{
  "summary": { "net": -2189.8, "roi": -66.13, "total_draws": 1371, "…": "…" },
  "jackpot": { "hits": 0, "last_date": null, "amounts": [] },
  "by_rank": [ { "rank": 8, "count": 78, "total_won": 390.0 }, "…" ],
  "timeline": [ { "date": "2018-01-01", "cumulative": -2.2 }, "…" ]
}
```

## 🧪 Tests

The suite has **112 tests** split into three families:

```
backend/tests/
├── conftest.py                     # Fixtures (isolated app, client, prod, payload)
├── fixtures/fdj_sample.csv         # Real excerpt of the official FDJ format
├── functional/test_user_journey.py # End-to-end user journey
├── technical/test_robustness.py    # FDJ import, robustness, API contract
└── security/test_owasp.py          # Security aligned with OWASP Top 10 / API Top 10
```

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q                    # all
.\.venv\Scripts\python.exe -m pytest tests/functional -q   # functional
.\.venv\Scripts\python.exe -m pytest tests/technical -q    # technical
.\.venv\Scripts\python.exe -m pytest tests/security -q     # security
```

| Family | What is verified |
| --- | --- |
| **Functional** | Balance `net = won − staked`, curve consistency, sum of ranks, **detection of the 29/09/2025 jackpot**, draw lookup, PDF export. |
| **Technical** | Parsing of the FDJ archives, French dates, amounts `1 234,50`, priority import (FDJ → local → fallback), idempotence, JSON contract, performance. |
| **Security** | Headers, cookies, injections, input limits, CORS, error leakage, rate limiting, PDF export. |

## 🛡️ Security

The hardening of the application follows the **OWASP Top 10 (2021)** and the
**OWASP API Top 10 (2023)**: security headers, strict input validation,
allow-listed CORS, rate limiting, secrets via environment variables and error
handling that leaks no information.

**📄 The detailed inventory of the security measures and tests is in
[`SECURITY.md`](SECURITY.md)** (threat model, OWASP coverage, 34 test cases,
reporting procedure, known limitations).

```powershell
# Run only the security tests
cd backend
.\.venv\Scripts\python.exe -m pytest tests/security -v
```

## 🔄 Updating the history

**The history is topped up automatically on every launch:**

1. the application downloads the official archives (at most once a day);
2. draws already present are **updated**
   (`ON CONFLICT(draw_date) DO UPDATE`), new ones are inserted;
3. no existing draw is deleted;
4. the result is logged and exposed via `/api/health`.

```jsonc
// GET /api/health
{
  "status": "ok",
  "draws": 2817,
  "latest_draw": "2026-10-05",
  "data_source": "fdj",
  "draws_added_at_startup": 0
}
```

> `draws` counts **all** the imported history (consultation), whereas the
> simulation only replays the **1 500 draws of the current format** (≥ 2017-03-06).

The `loto.db` file is kept between two launches: only the draws that are
genuinely missing are added (no duplication). To force a resynchronisation,
`POST /api/admin/sync` (rate-limited).

## 📄 PDF export

After a simulation, the **"Export to PDF"** button downloads a full report
generated server-side (ReportLab), containing:

- the grid played and the options enabled;
- the financial balance (staked, won, net, return on stake);
- the jackpot history (rank 1) and the best result;
- the distribution of winnings by rank;
- the trend curve of the cumulative balance;
- the 10 biggest wins of the series.

The export **does not archive** any simulation: it is a view, not a write.
The endpoint has its own rate limit (20/min).

## ⚠️ Disclaimer

**Educational and independent** project, not affiliated with La Française des
Jeux.

The draws come from the **official archives published for free download by the
FDJ**. The simulator faithfully reproduces the rules of LOTO (5 numbers out of
49, 1 lucky number out of 10, 9 winning ranks) and uses the **real payouts** of
each draw to calculate the winnings.

Gambling can be dangerous: loss of money, debt, isolation, addiction.
**Playing involves risks.**
