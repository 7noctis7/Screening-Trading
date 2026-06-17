"use client";
import { useEffect, useState } from "react";
import { useDashboard } from "@/lib/api";

// Indicateur « live » : point pulsant + temps écoulé depuis la dernière mise à jour (auto-refresh).
export function LiveBadge() {
  const { dataUpdatedAt, isFetching } = useDashboard();
  const [, tick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => tick((x) => x + 1), 1000);
    return () => clearInterval(id);
  }, []);
  const secs = dataUpdatedAt ? Math.max(0, Math.round((Date.now() - dataUpdatedAt) / 1000)) : null;
  const label = isFetching ? "maj…" : secs == null ? "—" : secs < 60 ? `il y a ${secs}s` : `il y a ${Math.round(secs / 60)}min`;
  return (
    <span className="hidden sm:inline-flex items-center gap-1.5 text-[11px] text-muted px-2 py-1 rounded-md border border-border"
      title="Flux auto-rafraîchi">
      <span className="inline-block w-1.5 h-1.5 rounded-full"
        style={{ background: isFetching ? "#f59e0b" : "#22c55e", boxShadow: `0 0 8px ${isFetching ? "#f59e0b" : "#22c55e"}` }} />
      LIVE <span className="text-muted2">{label}</span>
    </span>
  );
}
