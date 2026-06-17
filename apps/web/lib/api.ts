// Client API — le front consomme l'API, AUCUNE logique de trading ici.
import { useQuery } from "@tanstack/react-query";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`);
  if (!r.ok) throw new Error(`API ${path}: ${r.status}`);
  return r.json();
}

// Auto-rafraîchissement (mode "live" par polling) — TTL serveur 15 min, UI réactive.
const LIVE = 30000;
const q = (key: string, path: string, ms: number = LIVE) =>
  useQuery({ queryKey: [key], queryFn: () => get<any>(path), refetchInterval: ms, refetchOnWindowFocus: true });

export const useDashboard = () => q("dashboard", "/api/dashboard", 15000);
export const useScreener = () => q("screener", "/api/screener");
export const usePortfolio = () => q("portfolio", "/api/portfolio");
export const usePositions = () => q("positions", "/api/positions");
export const useTrades = () => q("trades", "/api/trades");
export const useUniverse = () => q("universe", "/api/universe", 120000);
export const useData = () => q("data", "/api/data");
export const useThemes = () => q("themes", "/api/themes");
export const useMl = () => q("ml", "/api/ml", 60000);
export const useSentiment = () => q("sentiment", "/api/sentiment", 60000);
export const useFundamentals = () => q("fundamentals", "/api/fundamentals", 60000);
