"use client";
import { useState } from "react";
import { EquityChart, type Win } from "@/components/EquityChart";
import { DrawdownChart } from "@/components/DrawdownChart";
import type { Point } from "@/lib/metrics";

// Panneau performance : equity (base 10k) AU-DESSUS du drawdown underwater. Zoom par glisser sur l'equity ;
// la fenêtre (`win`) pilote LES DEUX graphes → axes X synchronisés + downsampling recalculé de concert.
// `syncId` commun synchronise aussi le crosshair au survol.
export function PerformancePanel({ equity, benchmarks }:
  { equity: Point[]; benchmarks?: Record<string, Point[]> }) {
  const [win, setWin] = useState<Win>(null);
  if (!equity?.length) return null;
  return (
    <div className="space-y-3">
      <EquityChart series={equity} benchmarks={benchmarks} syncId="perf" win={win} onWin={setWin} />
      <DrawdownChart series={equity} syncId="perf" win={win} />
    </div>
  );
}
