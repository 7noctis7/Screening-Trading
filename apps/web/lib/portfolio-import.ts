export type ResolutionStatus = "confirme" | "a_verifier" | "introuvable";

export type ImportedPosition = {
  id: string;
  original: string;
  ticker: string;
  name: string;
  venue: string;
  currency: string;
  instrumentType: string;
  exposureClass: string;
  weight: number | null;
  originalWeight: number | null;
  source: "manual" | "csv" | "demo";
  status: ResolutionStatus;
  excluded: boolean;
};

export type PortfolioSnapshot = {
  version: number;
  createdAt: string;
  baseCurrency: string;
  positions: ImportedPosition[];
};

const CASH = /^CASH(?::([A-Z]{3}))?$/i;
const CRYPTO = /^(BTC|ETH|SOL|XRP|ADA)(?:[-/](USD|EUR|USDT))?$/i;
const KNOWN: Record<string, [string, string, string]> = {
  AAPL: ["Apple", "NASDAQ", "USD"], MSFT: ["Microsoft", "NASDAQ", "USD"],
  SPY: ["SPDR S&P 500 ETF", "NYSE Arca", "USD"], GLD: ["SPDR Gold Shares", "NYSE Arca", "USD"],
};

function numberFrom(raw: string): number | null {
  const cleaned = raw.trim().replace(/%/g, "").replace(",", ".");
  if (!cleaned) return null;
  const value = Number(cleaned);
  return Number.isFinite(value) && value >= 0 ? value : null;
}

function classify(ticker: string) {
  const cash = ticker.match(CASH);
  if (cash) return { name: `Liquidités ${cash[1] ?? "USD"}`, venue: "—", currency: cash[1] ?? "USD", instrumentType: "Liquidités", exposureClass: "Liquidités", status: "confirme" as const };
  const crypto = ticker.match(CRYPTO);
  if (crypto) return { name: crypto[2] ? `${crypto[1]}/${crypto[2]}` : crypto[1], venue: crypto[2] ? "Plateforme à confirmer" : "—", currency: crypto[2] ?? "USD", instrumentType: crypto[2] ? "Paire crypto" : "Crypto-actif", exposureClass: "Cryptomonnaies", status: "a_verifier" as const };
  const known = KNOWN[ticker];
  if (known) return { name: known[0], venue: known[1], currency: known[2], instrumentType: ticker === "SPY" || ticker === "GLD" ? "ETF" : "Action", exposureClass: ticker === "GLD" ? "Matières premières" : ticker === "SPY" ? "Exposition indicielle" : "Actions", status: "confirme" as const };
  return { name: "Correspondance à confirmer", venue: "—", currency: "—", instrumentType: "Non résolu", exposureClass: "Autres", status: "a_verifier" as const };
}

function makePosition(original: string, tickerRaw: string, weight: number | null, source: ImportedPosition["source"], index: number): ImportedPosition {
  const ticker = tickerRaw.trim().toUpperCase();
  const metadata = classify(ticker);
  return { id: `${Date.now()}-${index}-${ticker}`, original, ticker, weight, originalWeight: weight, source, excluded: false, ...metadata };
}

export function parseManual(text: string, source: ImportedPosition["source"] = "manual"): ImportedPosition[] {
  return text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean).map((line, index) => {
    const parts = line.split(/[;\t, ]+/).filter(Boolean);
    return makePosition(line, parts[0] ?? "", numberFrom(parts[1] ?? ""), source, index);
  }).filter((position) => position.ticker.length > 0);
}

export function parseCsv(text: string): ImportedPosition[] {
  const lines = text.split(/\r?\n/).filter((line) => line.trim());
  if (!lines.length) return [];
  const separator = lines[0].includes(";") ? ";" : ",";
  const rows = lines.map((line) => line.split(separator).map((cell) => cell.trim()));
  const header = rows[0].map((cell) => cell.toLowerCase());
  const tickerIndex = header.findIndex((cell) => /ticker|symbol|symbole|instrument/.test(cell));
  const weightIndex = header.findIndex((cell) => /weight|poids|allocation|percent/.test(cell));
  const hasHeader = tickerIndex >= 0;
  return rows.slice(hasHeader ? 1 : 0).map((row, index) => makePosition(
    row.join(separator), row[hasHeader ? tickerIndex : 0] ?? "",
    numberFrom(row[hasHeader && weightIndex >= 0 ? weightIndex : 1] ?? ""), "csv", index,
  )).filter((position) => position.ticker.length > 0);
}

export function allocationState(positions: ImportedPosition[]) {
  const included = positions.filter((position) => !position.excluded);
  const total = included.reduce((sum, position) => sum + (position.weight ?? 0), 0);
  const missing = included.filter((position) => position.weight === null).length;
  const ambiguous = included.filter((position) => position.status !== "confirme").length;
  const duplicates = included.length - new Set(included.map((position) => `${position.ticker}:${position.venue}`)).size;
  return { total, missing, ambiguous, duplicates, coherent: missing === 0 && ambiguous === 0 && Math.abs(total - 100) < 0.01 };
}

export function normalize(positions: ImportedPosition[]): ImportedPosition[] {
  const total = allocationState(positions).total;
  if (total <= 0) return positions;
  return positions.map((position) => position.excluded || position.weight === null ? position : { ...position, weight: position.weight * 100 / total });
}
