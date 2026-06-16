// Client API — le front consomme l'API, AUCUNE logique de trading ici.
import { useQuery } from "@tanstack/react-query";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function get<T>(path: string): Promise<T> {
  const r = await fetch(`${BASE}${path}`);
  if (!r.ok) throw new Error(`API ${path}: ${r.status}`);
  return r.json();
}

export const useDashboard = () => useQuery({ queryKey: ["dashboard"], queryFn: () => get<any>("/api/dashboard"), refetchInterval: 15000 });
export const useScreener = () => useQuery({ queryKey: ["screener"], queryFn: () => get<any>("/api/screener") });
export const usePortfolio = () => useQuery({ queryKey: ["portfolio"], queryFn: () => get<any>("/api/portfolio") });
export const usePositions = () => useQuery({ queryKey: ["positions"], queryFn: () => get<any>("/api/positions") });
export const useTrades = () => useQuery({ queryKey: ["trades"], queryFn: () => get<any>("/api/trades") });
export const useUniverse = () => useQuery({ queryKey: ["universe"], queryFn: () => get<any>("/api/universe") });
export const useData = () => useQuery({ queryKey: ["data"], queryFn: () => get<any>("/api/data") });
export const useThemes = () => useQuery({ queryKey: ["themes"], queryFn: () => get<any>("/api/themes") });
