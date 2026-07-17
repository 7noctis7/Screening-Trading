"use client";

// Bandeaux compacts du dashboard, extraits de page.tsx (règle <400 l./fichier) :
//  - TradeStatsRow : qualité des trades du BACKTEST (win rate, profit factor, gains/pertes) ;
//  - HonestyStrip : PSR affiché, DSR multi-essais assumé (manifeste d'honnêteté).

const usd = (x: number) => `${x >= 0 ? "+" : ""}${Math.round(x).toLocaleString("fr-FR")} $`;

export function TradeStatsRow({ ts }: { ts: any }) {
  if (!ts || !(ts.count > 0)) return null;
  // Lecture institutionnelle : un win rate seul ne dit rien — il se lit AVEC le payoff
  // (gain moyen / |perte moyenne|) ; l'espérance/trade agrège les deux ; le turnover
  // dit si l'edge survit aux frictions.
  const payoff = ts.avg_loss ? Math.abs((ts.avg_win ?? 0) / ts.avg_loss) : null;
  const expectancy = ts.count ? (ts.pnl_total ?? 0) / ts.count : 0;
  return (
    <section className="card p-4">
      <div className="flex items-center justify-between flex-wrap gap-2 mb-3">
        <h2 className="text-sm uppercase tracking-wide text-muted">Qualité des trades (backtest)</h2>
        <span className="text-[11px] text-muted2 mono">{ts.count} trades clôturés · net de coûts</span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
        <div><div className="text-muted text-[11px]">Trades</div>
          <div className="mono text-lg">{ts.count}</div>
          <div className="text-muted2 text-[11px] mono">{ts.wins} gagnants / {ts.losses} perdants</div></div>
        <div><div className="text-muted text-[11px]">Win rate × payoff</div>
          <div className="mono text-lg">{Math.round((ts.win_rate ?? 0) * 100)}%
            <span className="text-muted2 text-xs"> × {payoff != null ? payoff.toFixed(2) : "∞"}</span></div>
          <div className="text-muted2 text-[11px]">à lire ensemble, jamais séparément</div></div>
        <div><div className="text-muted text-[11px]">Profit factor</div>
          <div className="mono text-lg">{ts.profit_factor ?? "∞"}</div></div>
        <div><div className="text-muted text-[11px]">Espérance / trade</div>
          <div className="mono text-lg" style={{ color: expectancy >= 0 ? "var(--pos)" : "#f43f5e" }}>{usd(expectancy)}</div></div>
        <div><div className="text-muted text-[11px]">Gain moyen</div>
          <div className="mono text-lg" style={{ color: "var(--pos)" }}>{usd(ts.avg_win ?? 0)}</div></div>
        <div><div className="text-muted text-[11px]">Perte moyenne</div>
          <div className="mono text-lg" style={{ color: "#f43f5e" }}>{usd(ts.avg_loss ?? 0)}</div></div>
        <div><div className="text-muted text-[11px]">Meilleur / pire</div>
          <div className="mono text-lg">{usd(ts.best ?? 0)} / {usd(ts.worst ?? 0)}</div></div>
        {ts.turnover != null && <div><div className="text-muted text-[11px]">Turnover annualisé</div>
          <div className="mono text-lg">{Number(ts.turnover).toFixed(2)}×</div>
          <div className="text-muted2 text-[11px]">friction & capacité</div></div>}
      </div>
    </section>
  );
}

export function HonestyStrip({ honesty }: { honesty: any }) {
  if (!honesty?.available) return null;
  return (
    <div className="card p-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs" title={honesty.note}>
      <span className="px-2 py-0.5 rounded-full text-[10px] uppercase tracking-[0.08em] font-semibold"
        style={{ background: "color-mix(in srgb, var(--accent) 18%, transparent)", color: "var(--accent2)" }}>
        Honnêteté
      </span>
      <span className="mono">PSR <b className="text-fg">{Math.round((honesty.psr ?? 0) * 100)}%</b>{" "}
        <span className="text-muted2">P(Sharpe&gt;0)</span></span>
      <span className="mono text-muted">Sharpe ann. {honesty.sharpe_annualized}</span>
      <span className="mono text-muted">n={honesty.n_obs}</span>
      <span className="text-muted2 basis-full md:basis-auto md:flex-1 md:min-w-0">{honesty.note}</span>
    </div>
  );
}
