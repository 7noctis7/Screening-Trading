"use client";

// Bandeaux compacts du dashboard, extraits de page.tsx (règle <400 l./fichier) :
//  - TradeStatsRow : qualité des trades du BACKTEST (win rate, profit factor, gains/pertes) ;
//  - HonestyStrip : PSR affiché, DSR multi-essais assumé (manifeste d'honnêteté).

const usd = (x: number) => `${x >= 0 ? "+" : ""}${Math.round(x).toLocaleString("fr-FR")} $`;

export function TradeStatsRow({ ts }: { ts: any }) {
  if (!ts || !(ts.count > 0)) return null;
  return (
    <section className="card p-4">
      <h2 className="text-sm uppercase tracking-wide text-muted mb-3">Qualité des trades (backtest)</h2>
      <div className="grid grid-cols-3 md:grid-cols-6 gap-3 text-sm">
        <div><div className="text-muted text-[11px]">Trades</div>
          <div className="mono text-lg">{ts.count}</div>
          <div className="text-muted2 text-[11px] mono">{ts.wins} gagnants / {ts.losses} perdants</div></div>
        <div><div className="text-muted text-[11px]">Win rate</div>
          <div className="mono text-lg">{Math.round((ts.win_rate ?? 0) * 100)}%</div></div>
        <div><div className="text-muted text-[11px]">Profit factor</div>
          <div className="mono text-lg">{ts.profit_factor ?? "∞"}</div></div>
        <div><div className="text-muted text-[11px]">Gain moyen</div>
          <div className="mono text-lg" style={{ color: "var(--pos)" }}>{usd(ts.avg_win ?? 0)}</div></div>
        <div><div className="text-muted text-[11px]">Perte moyenne</div>
          <div className="mono text-lg" style={{ color: "#f43f5e" }}>{usd(ts.avg_loss ?? 0)}</div></div>
        <div><div className="text-muted text-[11px]">Meilleur / pire</div>
          <div className="mono text-lg">{usd(ts.best ?? 0)} / {usd(ts.worst ?? 0)}</div></div>
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
