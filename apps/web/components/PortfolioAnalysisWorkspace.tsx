"use client";

import { useEffect, useState } from "react";
import { useEffect, useState } from "react";
import { useState } from "react";
import { PortfolioEvidence } from "@/components/PortfolioEvidence";
import { PortfolioImportWizard } from "@/components/PortfolioImportWizard";
import { PortfolioScenarios } from "@/components/PortfolioScenarios";
import { PortfolioSynergies } from "@/components/PortfolioSynergies";
import { analyzePortfolio } from "@/lib/api";
import type { PortfolioSnapshot } from "@/lib/portfolio-import";

const STORAGE_KEY = "portfolio-analysis-snapshot";

function restoreSnapshot(): PortfolioSnapshot | null {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    return saved ? JSON.parse(saved) : null;
  } catch {
    return null;
  }
}

export function PortfolioAnalysisWorkspace() {
  const [snapshot, setSnapshot] = useState<PortfolioSnapshot | null>(null);
  const [analysis, setAnalysis] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => setSnapshot(restoreSnapshot()), []);
  useEffect(() => {
    if (!snapshot) {
      setAnalysis(null);
      return;
    }
    let active = true;
    setLoading(true);
    analyzePortfolio(snapshot.positions)
      .then((result) => active && setAnalysis(result))
      .catch((error) => active && setAnalysis({ available: false, reason: String(error) }))
      .finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [snapshot]);

  return <>
    <PortfolioImportWizard onSnapshot={setSnapshot} initialSnapshot={snapshot} />
    <PortfolioEvidence snapshot={snapshot} analysis={analysis} loading={loading} />
    <PortfolioScenarios snapshot={snapshot} analysis={analysis} />
    <PortfolioSynergies />
  </>;
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
