"use client";
import { useState } from "react";
import { PortfolioEvidence } from "@/components/PortfolioEvidence";
import { PortfolioImportWizard } from "@/components/PortfolioImportWizard";
import { PortfolioScenarios } from "@/components/PortfolioScenarios";
import { PortfolioSynergies } from "@/components/PortfolioSynergies";
import { PortfolioSnapshot } from "@/lib/portfolio-import";

export function PortfolioAnalysisWorkspace() {
  const [snapshot, setSnapshot] = useState<PortfolioSnapshot | null>(null);
  return <><PortfolioImportWizard onSnapshot={setSnapshot} /><PortfolioEvidence snapshot={snapshot} /><PortfolioScenarios snapshot={snapshot} /><PortfolioSynergies /></>;
}
