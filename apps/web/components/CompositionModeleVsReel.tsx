"use client";

export default function CompositionModeleVsReel({ modele, reel }: { modele: any[]; reel: any[] }) {
  const norm = (x: string) => (x || "").toUpperCase().replace(/[/\-]/g, "").replace(/(USDT|USDC|USD)$/, "");
  const totM = modele.reduce((t, p) => t + (Number(p?.value) || 0), 0);
  const totR = reel.reduce((t, p) => t + (Number(p?.market_value) || 0), 0);
  const map = new Map<string, any>();
  for (const p of modele) {
    map.set(norm(p.symbol), { symbol: p.symbol, wM: totM > 0 ? (Number(p.value) || 0) / totM : null,
      pnlM: p.pnl_pct ?? null, joursM: p.jours ?? null, depuisM: p.depuis ?? null,
      wR: null, pnlR: null });
  }
  for (const p of reel) {
    const k = norm(p.symbol);
    const w = totR > 0 ? (Number(p.market_value) || 0) / totR : null;
    const e = map.get(k);
    if (e) { e.wR = w; e.pnlR = p.pnl_pct ?? null; }
    else map.set(k, { symbol: p.symbol, wM: null, pnlM: null, wR: w, pnlR: p.pnl_pct ?? null });
  }
  const rows = [...map.values()].sort((a, b) => (b.wM ?? b.wR ?? 0) - (a.wM ?? a.wR ?? 0));
  if (!rows.length) return null;
  const pc = (x: number | null) => (x == null ? "—" : `${(x * 100).toFixed(1)}%`);
  const col = (x: number | null) => (x == null ? "#9aa1ad" : x >= 0 ? "#22c55e" : "#ef4444");
  return (
    <div className="mt-4 pt-3 border-t border-border">
      <h3 className="text-sm uppercase tracking-wide text-muted mb-1">Composition — modèle vs réel</h3>
      <p className="text-muted2 text-xs mb-3">
        Comparaison en <b>poids</b>, pas en montants : le backtest part de 10 000 $ et le compte réel
        en vaut dix fois plus. L'écart de poids est la seule quantité qui répond à
        « est-ce que je réplique le modèle ? ». Une ligne présente d'un seul côté est un écart de
        réplication, pas une erreur.
      </p>
      <p className="text-muted2 text-xs mb-3">
        <b>Les deux P&amp;L ne se comparent pas.</b> Celui du modèle cumule depuis l'ouverture de la
        ligne dans le backtest — la colonne « depuis » donne la durée ; celui du compte part de
        votre achat chez le courtier, souvent quelques semaines. Un « +158 % contre −1,1 % » sur la
        même ligne oppose dix ans à trois semaines, pas deux gestions.
      </p>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-muted text-xs"><tr>
            <th className="text-left font-normal">Actif</th>
            <th className="text-right font-normal">Poids modèle</th>
            <th className="text-right font-normal">Poids réel</th>
            <th className="text-right font-normal">Écart</th>
            <th className="text-right font-normal">P&amp;L modèle</th>
            <th className="text-right font-normal">depuis</th>
            <th className="text-right font-normal">P&amp;L réel</th>
          </tr></thead>
          <tbody className="mono">
            {rows.map((r) => {
              const ecart = r.wM != null && r.wR != null ? r.wR - r.wM : null;
              return (
                <tr key={r.symbol} className="border-t border-border">
                  <td className="py-1.5">{r.symbol}
                    {r.wM == null && <span className="ml-1.5 text-[10px] font-sans text-muted2">réel seul</span>}
                    {r.wR == null && <span className="ml-1.5 text-[10px] font-sans text-muted2">modèle seul</span>}
                  </td>
                  <td className="text-right">{pc(r.wM)}</td>
                  <td className="text-right">{pc(r.wR)}</td>
                  <td className="text-right" style={{ color: ecart == null ? "#9aa1ad" : Math.abs(ecart) > 0.03 ? "#f59e0b" : "var(--muted)" }}>
                    {ecart == null ? "—" : `${ecart >= 0 ? "+" : ""}${(ecart * 100).toFixed(1)} pt`}
                  </td>
                  <td className="text-right" style={{ color: col(r.pnlM) }}>{pc(r.pnlM)}</td>
                  <td className="text-right text-muted2" title={r.depuisM ?? ""}>
                    {r.joursM == null ? "—" : r.joursM >= 365
                      ? `${(r.joursM / 365).toFixed(1)} an${r.joursM >= 730 ? "s" : ""}`
                      : `${r.joursM} j`}
                  </td>
                  <td className="text-right" style={{ color: col(r.pnlR) }}>{pc(r.pnlR)}</td>
                </tr>);
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

