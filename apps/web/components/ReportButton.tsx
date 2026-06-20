"use client";
// Bouton « Note d'analyse » par société : ouvre le PDF/HTML institutionnel généré côté API
// (Vernimmen + Damodaran, intrants audités PwC, sources gratuites yfinance/FMP/SEC EDGAR).

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export function ReportButton({ ticker, assetClass }: { ticker: string; assetClass?: string }) {
  const ac = (assetClass || "").toLowerCase();
  if (ac && ac !== "equity" && ac !== "etf") return null;   // note fondamentale = actions/ETF
  const href = `${BASE}/api/company_report?ticker=${encodeURIComponent(ticker)}&format=html`;
  return (
    <a href={href} target="_blank" rel="noopener noreferrer"
      title={`Générer la note d'analyse fondamentale — ${ticker} (Vernimmen + Damodaran, audit PwC)`}
      onClick={(e) => e.stopPropagation()}
      className="inline-flex items-center justify-center w-5 h-5 rounded-md text-muted hover:text-accent hover:bg-surfaceAlt transition-colors align-middle"
      aria-label={`Note d'analyse ${ticker}`}>
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
        strokeLinecap="round" strokeLinejoin="round" aria-hidden>
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" /><line x1="9" y1="13" x2="15" y2="13" /><line x1="9" y1="17" x2="13" y2="17" />
      </svg>
    </a>
  );
}
