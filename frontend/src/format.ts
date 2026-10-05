/** Shared formatting functions. */

const euroFormatter = new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 0,
});

const euroPreciseFormatter = new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "EUR",
  minimumFractionDigits: 2,
});

const dateFormatter = new Intl.DateTimeFormat("fr-FR", {
  day: "2-digit",
  month: "long",
  year: "numeric",
});

/** 12345 -> "12 345 €" (rounded to the euro). */
export function formatEuro(value: number): string {
  return euroFormatter.format(value);
}

/** 2.2 -> "2,20 €" (two decimals). */
export function formatEuros2(value: number): string {
  return euroPreciseFormatter.format(value);
}

/** Formats a difference with an explicit sign. */
export function formatSigned(value: number): string {
  const formatted = euroPreciseFormatter.format(Math.abs(value));
  if (value > 0) return `+${formatted}`;
  if (value < 0) return `-${formatted}`;
  return formatted;
}

/** « 2026-10-03 » -> « 3 octobre 2026 ». */
export function formatDate(iso: string): string {
  return dateFormatter.format(new Date(`${iso}T00:00:00`));
}

/** Formats a signed percentage the French way (e.g. "+12,34 %"). */
export function formatPercent(value: number): string {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2).replace(".", ",")} %`;
}
