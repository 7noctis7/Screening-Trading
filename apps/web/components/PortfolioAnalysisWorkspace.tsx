"use client";
import { useEffect, useState } from "react";
import { useState } from "react";
import { PortfolioEvidence } from "@/components/PortfolioEvidence";
import { PortfolioImportWizard } from "@/components/PortfolioImportWizard";
import { PortfolioScenarios } from "@/components/PortfolioScenarios";
import { PortfolioSynergies } from "@/components/PortfolioSynergies";
import { PortfolioSnapshot } from "@/lib/portfolio-import";
import { analyzePortfolio } from "@/lib/api";

export function PortfolioAnalysisWorkspace() {
  const [snapshot, setSnapshot] = useState<PortfolioSnapshot | null>(null);
  const [analysis, setAnalysis] = useState<any>(null); const [loading, setLoading] = useState(false);
  useEffect(() => {
    try {
      const saved = localStorage.getItem("portfolio-analysis-snapshot");
      if (saved) setSnapshot(JSON.parse(saved));
    } catch { /* stockage navigateur indisponible : l'import manuel reste utilisable */ }
  }, []);
  useEffect(() => {
    if (!snapshot) { setAnalysis(null); return; }
    setLoading(true); analyzePortfolio(snapshot.positions).then(setAnalysis)
      .catch((error) => setAnalysis({ available: false, reason: String(error) })).finally(() => setLoading(false));
  }, [snapshot]);
  return <><PortfolioImportWizard onSnapshot={setSnapshot} initialSnapshot={snapshot} /><PortfolioEvidence snapshot={snapshot} analysis={analysis} loading={loading} /><PortfolioScenarios snapshot={snapshot} analysis={analysis} /><PortfolioSynergies /></>;

export function PortfolioAnalysisWorkspace() {
  const [snapshot, setSnapshot] = useState<PortfolioSnapshot | null>(null);
  return <><PortfolioImportWizard onSnapshot={setSnapshot} /><PortfolioEvidence snapshot={snapshot} /><PortfolioScenarios snapshot={snapshot} /><PortfolioSynergies /></>;
}
