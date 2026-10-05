/** Client HTTP vers l'API Flask. */

import type {
  AppConfig,
  DataSourceInfo,
  DrawsResponse,
  HotNumbers,
  JackpotsResponse,
  SimulationResult,
} from "./types";

const BASE_URL = import.meta.env.VITE_API_URL ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });

  if (!response.ok) {
    let message = `Erreur ${response.status}`;
    try {
      const body = (await response.json()) as { error?: string };
      if (body.error) message = body.error;
    } catch {
      /* non-JSON response: keep the generic message */
    }
    throw new Error(message);
  }

  return (await response.json()) as T;
}

export const api = {
  config: () => request<AppConfig>("/api/config"),

  draws: (limit = 20, offset = 0) =>
    request<DrawsResponse>(`/api/draws?limit=${limit}&offset=${offset}`),

  hotNumbers: () => request<HotNumbers>("/api/stats/hot-numbers"),

  dataSource: () => request<DataSourceInfo>("/api/data-source"),

  jackpots: (limit = 25) => request<JackpotsResponse>(`/api/jackpots?limit=${limit}`),

  simulate: (numbers: number[], chance: number) =>
    request<SimulationResult>("/api/simulate", {
      method: "POST",
      body: JSON.stringify({ numbers, chance }),
    }),

  /** Requests the PDF report and triggers its download. */
  downloadPdf: async (numbers: number[], chance: number): Promise<void> => {
    const response = await fetch(`${BASE_URL}/api/simulate/pdf`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ numbers, chance }),
    });

    if (!response.ok) {
      let message = `Erreur ${response.status}`;
      try {
        const body = (await response.json()) as { error?: string };
        if (body.error) message = body.error;
      } catch {
        /* non-JSON response */
      }
      throw new Error(message);
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);

    const filename = extractFilename(response.headers.get("Content-Disposition"));
    const link = document.createElement("a");
    link.href = url;
    link.download = filename ?? "loto-winner-rapport.pdf";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  },
};

/** Extracts the filename from a Content-Disposition header. */
function extractFilename(header: string | null): string | null {
  if (!header) return null;
  const match = /filename="?([^";]+)"?/i.exec(header);
  return match ? match[1] : null;
}
