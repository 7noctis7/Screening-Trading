import { PortfolioAnalysisWorkspace } from "@/components/PortfolioAnalysisWorkspace";

export default function AnalysePortefeuille() {
  return <main className="max-w-6xl mx-auto p-4 md:p-6 space-y-5">
    <header><div className="eyebrow">Analyse multi-actifs · MVP</div><h1 className="display text-2xl md:text-3xl mt-2">Comprendre votre portefeuille</h1><p className="text-sm text-muted mt-2 max-w-3xl">Import manuel ou CSV, résolution prudente, confirmation explicite et snapshot local versionné. Le moteur quantitatif calcule ; l'IA n'invente ni score ni allocation.</p></header>
    <PortfolioAnalysisWorkspace />
  </main>;
}
