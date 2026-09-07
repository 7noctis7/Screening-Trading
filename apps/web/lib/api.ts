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

// Une requête qui n'ARRIVE PAS à l'API n'est pas une donnée manquante. Le navigateur rend
// « TypeError: Load failed » (Safari) ou « Failed to fetch » (Chrome) pour TOUTE panne de
// transport — API éteinte, mauvais port, origine refusée par le CORS — et ces chaînes ne
// disent rien de ce qu'il faut faire. Les relayer telles quelles sous « Analyse historique
// indisponible » accusait la donnée alors que le corps de la requête n'était jamais parti
// et qu'aucune base n'avait été ouverte (07/09).
// Origines que l'API autorise par défaut (apps/api/main.py). Un front servi ailleurs — le cas
// le plus courant : Next.js bascule tout seul sur 3001 quand 3000 est déjà pris — est refusé
// par le CORS AVANT d'atteindre l'API, ce que le navigateur rapporte comme une panne réseau
// indiscernable d'une API éteinte. Sans cette liste, le message renvoyait vers « make start »
// pour une cause qui n'avait rien à voir (07/09).
const ORIGINES_AUTORISEES = ["http://localhost:3000", "http://127.0.0.1:3000",
  "http://localhost:3001", "http://127.0.0.1:3001", "http://localhost:8080"];

function _raisonTransport(): string {
  const origine = typeof location === "undefined" ? "" : location.origin;
  const tete = `API injoignable à ${BASE} : la requête n'a pas abouti, aucun historique n'a été lu.`;
  if (ORIGINES_AUTORISEES.includes(origine))
    return `${tete} Vérifier que « make start » tourne — curl ${BASE}/health.`;
  const local = /^https?:\/\/(localhost|127\.0\.0\.1)(:|$)/.test(origine);
  if (local) return `${tete} La page est servie depuis ${origine}, qui n'est pas dans les origines `
    + `autorisées PAR DÉFAUT par l'API (${ORIGINES_AUTORISEES.join(", ")}) : le CORS refuse alors la requête avant `
    + `qu'elle parte. Libérez le port 3000 et relancez, ou ajoutez ${origine} à QUANT_CORS_ORIGINS.`;
  return `${tete} La page est servie depuis ${origine} : « localhost » y désigne CET appareil, `
    + `pas la machine qui héberge l'API. Définir NEXT_PUBLIC_API_URL sur son adresse et ajouter `
    + `cette origine à QUANT_CORS_ORIGINS.`;
}

const _indisponible = (reason: string) => ({ available: false, reason, missing: [], coverage: 0 });

export async function analyzePortfolio(positions: { ticker: string; weight: number | null }[]) {
  if (STATIC) return _indisponible("analyse dynamique disponible en local avec make start");
  const payload = { positions: positions.filter((row) => row.weight != null).map((row) => ({
    symbol: row.ticker, weight: Number(row.weight) / 100,
  })), years: 5 };
  let response: Response;
  try {
    response = await fetch(`${BASE}/api/portfolio/analyze`, { method: "POST",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
  } catch {
    return _indisponible(_raisonTransport());
  }
  if (!response.ok) {
    return _indisponible(`API ${BASE}/api/portfolio/analyze : HTTP ${response.status}. `
      + `L'API répond mais refuse la requête ; l'historique n'est pas en cause.`);
  }
  return response.json();
}

// Univers RECOMMANDÉ : ce que le robot proposerait de détenir, indépendamment de ce qui
// est détenu. Distinct de `optimal_allocation`, qui ne répartit le risque que sur les
// lignes déjà en portefeuille et ne peut donc rien proposer de nouveau.
// Le profil déclaré dans l'onglet « Mon profil » vit dans CE navigateur (clé `quant.profil`).
// On le transmet à chaque appel, exactement comme la page de profil interroge déjà `/api/profil` :
// l'API calcule et ne conserve rien. Sans profil enregistré, la recommandation reste ce qu'elle
// était — bornée par le seul plafond de ligne.
function _profilLocal(): unknown | null {
  try {
    const brut = localStorage.getItem("quant.profil");
    return brut ? JSON.parse(brut) : null;
  } catch {
    return null;
  }
}

export async function recommendUniverse(n: number, maxWeight: number,
  positions: { ticker: string; weight: number | null }[] = [], years = 5) {
  if (STATIC) return _indisponible("recommandation disponible en local avec make start");
  let response: Response;
  try {
    response = await fetch(`${BASE}/api/portfolio/recommend`, { method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ n, years, max_weight: maxWeight, profil: _profilLocal(),
        positions: positions.filter((r) => r.weight != null)
          .map((r) => ({ symbol: r.ticker, weight: Number(r.weight) / 100 })) }) });
  } catch {
    return _indisponible(_raisonTransport());
  }
  if (!response.ok) return _indisponible(`API ${BASE}/api/portfolio/recommend : HTTP ${response.status}.`);
  return response.json();
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
export const useCryptoCockpit = () => q("crypto_cockpit", "/api/crypto_cockpit", 600000);
export const useTicker = () => q("ticker", "/api/ticker", 600000);
export const useFailures = () => q("failures", "/api/failures", 600000);
export const usePortfolio = () => q("portfolio", "/api/portfolio");
export const usePositions = () => q("positions", "/api/positions");
export const useTrades = () => q("trades", "/api/trades");
export const useJournal = () => q("journal", "/api/journal", 60000);
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
