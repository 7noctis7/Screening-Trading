"use client";
import Link from "next/link";

// Bandeau d'humeur. Si le chiffre vient du cours et non d'un fil, il ne s'appelle
// pas « humeur de marché » : c'est le déguisement que la page a déjà trop longtemps tenu.
const SC: Record<string, [string, string]> = {
  bullish: ["#22c55e", "▲"], bearish: ["#f43f5e", "▼"], neutral: ["#9aa1ad", "–"],
};

export function SentimentBanner({ sentiment }: { sentiment: any }) {
  if (!sentiment?.available) return null;
  const fil = sentiment.humeur_est_fil === true;
  const mood = sentiment.market_mood;
  if (mood == null) {
    return (
      <Link href="/sentiment" className="card p-4 text-sm text-muted hover:bg-surfaceAlt">
        Pas de fil d'actualité sur les positions — humeur non mesurée, pas neutre.
      </Link>
    );
  }
  const moodPct = Math.round(((Number(mood) + 1) / 2) * 100);
  const [c, i] = SC[sentiment.market_label] ?? SC.neutral;
  return (
    <Link href="/sentiment" className="card p-4 flex items-center gap-4 hover:bg-surfaceAlt transition-colors">
      <div className="text-muted text-xs uppercase tracking-wide whitespace-nowrap">
        {fil ? "Humeur des news" : "Tendance 3 mois"}
      </div>
      <span className="font-medium" style={{ color: fil ? c : "var(--muted)" }}>
        {fil ? `${i} ${sentiment.market_label}` : "pas un fil"}
      </span>
      <div className="flex-1 h-2 rounded-md overflow-hidden" style={{ background: "#1d212a" }}>
        <div style={{ height: "100%", width: `${moodPct}%`, background: fil
          ? "linear-gradient(90deg,#f43f5e,#9aa1ad,#22c55e)" : "var(--muted2)" }} />
      </div>
      <span className="mono text-sm whitespace-nowrap">{Number(mood).toFixed(2)}</span>
      <span className="text-muted text-xs whitespace-nowrap hidden md:inline">
        {fil ? sentiment.engine : `${sentiment.n_lignes_tendance ?? "—"} lignes en repli`}
      </span>
    </Link>
  );
}
