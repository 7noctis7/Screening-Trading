"use client";
import Link from "next/link";

// Bandeau compact d'humeur de marché (sentiment des positions). Cliquable → onglet dédié.
const SC: Record<string, [string, string]> = {
  bullish: ["#22c55e", "▲"], bearish: ["#f43f5e", "▼"], neutral: ["#9aa1ad", "–"],
};

export function SentimentBanner({ sentiment }: { sentiment: any }) {
  if (!sentiment?.available) return null;
  const mood: number = sentiment.market_mood ?? 0;
  const moodPct = Math.round(((mood + 1) / 2) * 100);
  const [c, i] = SC[sentiment.market_label] ?? SC.neutral;
  return (
    <Link href="/sentiment" className="card p-4 flex items-center gap-4 hover:bg-surfaceAlt transition-colors">
      <div className="text-muted text-xs uppercase tracking-wide whitespace-nowrap">Humeur de marché</div>
      <span className="font-medium" style={{ color: c }}>{i} {sentiment.market_label}</span>
      <div className="flex-1 h-2 rounded-md overflow-hidden" style={{ background: "#1d212a" }}>
        <div style={{ height: "100%", width: `${moodPct}%`, background: "linear-gradient(90deg,#f43f5e,#9aa1ad,#22c55e)" }} />
      </div>
      <span className="mono text-sm whitespace-nowrap">{mood.toFixed(2)}</span>
      <span className="text-muted text-xs whitespace-nowrap hidden md:inline">{sentiment.engine}</span>
    </Link>
  );
}
