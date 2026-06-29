// Client API — le front consomme l'API, AUCUNE logique de trading ici.
import { keepPreviousData, useQuery } from "@tanstack/react-query";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
// Mode STATIQUE (GitHub Pages) : on lit des instantanés JSON figés au lieu d'interroger l'API.
const STATIC = process.env.NEXT_PUBLIC_STATIC === "1";
const BP = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

function _staticUrl(path: string): string {
  // "/api/portfolio" → "<base>/data/portfolio.json" ; les query (overlays, …) sont neutralisés.
  const name = path.split("?")[0].replace(/^\/api\//, "").replace(/\//g, "_");
  return `${BP}/data/${name}.json`;
}

async function get<T>(path: string): Promise<T> {
  const url = STATIC ? _staticUrl(path) : `${BASE}${path}`;
  const r = await fetch(url);
  if (!r.ok) throw new Error(`API ${path}: ${r.status}`);
  return r.json();
}

// Navigation instantanée : données fraîches gardées en cache (staleTime), pas de "vide" au
// changement d'onglet (placeholderData), refetch en arrière-plan. TTL serveur 15 min.
const LIVE = 30000;
const q = (key: string, path: string, ms: number = LIVE) =>
  useQuery({
    queryKey: [key], queryFn: () => get<any>(path),
    refetchInterval: ms, refetchOnWindowFocus: false,
    staleTime: Math.min(ms, 30000), gcTime: 600000,
    placeholderData: keepPreviousData,
  });

export const useMeta = () => q("meta", "/api/meta", 60000);
export const useDashboard = () => q("dashboard", "/api/dashboard", 15000);
export const useScreener = () => q("screener", "/api/screener");
export const useScreen = () => q("screen", "/api/screen", 60000);
export const usePredictionMarkets = () => q("prediction_markets", "/api/prediction_markets", 600000);
export const useCryptoOnchain = () => q("crypto_onchain", "/api/crypto_onchain", 600000);
export const usePortfolio = () => q("portfolio", "/api/portfolio");
export const usePositions = () => q("positions", "/api/positions");
export const useTrades = () => q("trades", "/api/trades");
export const usePresetLedger = () => q("preset_ledger", "/api/preset_ledger", 60000);
export const useUniverse = () => q("universe", "/api/universe", 120000);
export const useData = () => q("data", "/api/data");
export const useThemes = () => q("themes", "/api/themes");
export const useMl = () => q("ml", "/api/ml", 60000);
export const useSentiment = () => q("sentiment", "/api/sentiment", 60000);
export const useFundamentals = () => q("fundamentals", "/api/fundamentals", 60000);
export const useLive = () => q("live", "/api/live", 30000);
export const useConviction = () => q("conviction", "/api/conviction", 60000);
export const useInvestors = () => q("investors", "/api/investors", 60000);
export const useMacro = () => q("macro", "/api/macro", 600000);
export const useEvents = () => q("events", "/api/events", 600000);
export const useAnalytics = () => q("analytics", "/api/analytics", 60000);
export const useNotes = () => q("notes", "/api/notes", 300000);
// Overlays MCP TradingView (cônes de risque + blackouts) pour un ticker — null si aucun.
export const useOverlays = (ticker: string | null) =>
  useQuery({
    queryKey: ["overlays", ticker], enabled: !!ticker,
    queryFn: () => get<any>(`/api/overlays?ticker=${encodeURIComponent(ticker ?? "")}`),
    refetchInterval: 20000, refetchOnWindowFocus: false, staleTime: 10000, gcTime: 600000,
    placeholderData: keepPreviousData,
  });
