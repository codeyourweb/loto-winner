/** Types shared with the Flask API. */

export interface RankRule {
  rank: number;
  label: string;
  gain: number | null;
  is_jackpot: boolean;
}

export interface AppConfig {
  total_numbers: number;
  pick_count: number;
  chance_max: number;
  grid_price: number;
  max_rank: number;
  ranks: RankRule[];
  data_source: "fdj" | "simulated" | null;
  draws_available: number;
}

export interface SimulationSummary {
  numbers: number[];
  chance: number;
  stake_per_draw: number;
  total_draws: number;
  total_spent: number;
  total_won: number;
  net: number;
  roi: number;
  winning_draws: number;
  win_rate: number;
  biggest_win: number;
  best_rank: number | null;
  best_rank_label: string | null;
  best_rank_date: string | null;
  best_rank_numbers: number[] | null;
  first_draw: string;
  last_draw: string;
  simulation_start: string;
  data_source: "fdj" | "simulated";
}

export interface JackpotInfo {
  hits: number;
  dates: string[];
  amounts: number[];
  last_date: string | null;
  first_date: string | null;
  longest_drought_draws: number;
  current_drought_draws: number;
}

export interface JackpotDraw {
  date: string;
  numbers: number[];
  chance: number;
  jackpot: number;
  winners?: number;
}

export interface JackpotsResponse {
  total: number;
  jackpots: JackpotDraw[];
}

export interface RankBreakdown {
  rank: number;
  label: string;
  count: number;
  total_won: number;
}

export interface TimelineEntry {
  date: string;
  matches: number;
  chance: number;
  rank: number | null;
  gain: number;
  cumulative: number;
  isJackpot: boolean;
}

export interface SimulationResult {
  summary: SimulationSummary;
  jackpot: JackpotInfo;
  by_rank: RankBreakdown[];
  timeline: TimelineEntry[];
  generated_at: string;
  simulation_id?: number | null;
}

export interface Draw {
  date: string;
  numbers: number[];
  chance: number;
  jackpot: number;
  jackpotWinners: number;
  source: string;
}

export interface DrawsResponse {
  total: number;
  limit: number;
  offset: number;
  draws: Draw[];
}

export interface HotNumbers {
  total_draws: number;
  hot: { number: number; count: number }[];
  cold: { number: number; count: number }[];
  chance: { number: number; count: number }[];
}

export interface DataSourceInfo {
  is_real_data: boolean;
  counts: Record<string, number>;
  first_draw: string | null;
  last_draw: string | null;
  last_sync_at: string | null;
  official_source: string;
}

export interface DrawDetail {
  date: string;
  numbers: number[];
  chance: number;
  jackpot: number;
  jackpotWinners: number;
  source: string;
  reports: { rank: number; winners: number; report: number }[];
}
