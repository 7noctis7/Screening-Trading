"use client";
// Trois repères de SANTÉ du marché, pas de direction : les munitions qui attendent
// (stablecoins et leur écart au peg), la part du top 50 qui bat BTC, et le cycle du
// halving. Aucun ne dit d'acheter — ils disent dans quel régime on se trouve.
import { InfoTip } from "@/components/InfoTip";
import { Card } from "./Card";
import { GLOSSARY } from "./glossaire";
import { usd, pct } from "./format";

// ---- Stablecoins : taille + écart au peg (santé de la liquidité) ----
export function Stablecoins({ ck }: { ck: any }) {
  const st = (ck.stablecoins ?? []) as any[];
  if (!st.length) return null;
  return (
    <Card title="Les cryptos calées sur le dollar" source="DefiLlama · stablecoins"
      hint="Ces cryptos valent en principe 1,00 $ en permanence : c'est l'argent qui attend sur le côté, prêt à être investi. Plus il y en a, plus il y a de munitions. Et si l'une d'elles s'écarte durablement de 1,00 $, c'est un signe de tension ou de perte de confiance.">
      <div className="overflow-x-auto">
        <table className="w-full text-sm mono">
          <thead className="text-muted2 text-[11px]">
            <tr>
              <th className="text-left font-normal">stablecoin</th>
              <th className="text-right font-normal">capitalisation</th>
              <th className="text-right font-normal">prix</th>
              <th className="text-right font-normal">
                <span className="inline-flex items-center gap-1">écart au <InfoTip label="peg">{GLOSSARY.peg}</InfoTip></span>
              </th>
            </tr>
          </thead>
          <tbody>
            {st.map((s) => {
              const isYield = s.kind === "yield";
              const off = !isYield && typeof s.peg_dev === "number" && Math.abs(s.peg_dev) > 0.005;
              return (
                <tr key={s.sym} className="border-t border-border">
                  <td className="py-1.5 font-sans">
                    {s.sym}
                    {isYield && (
                      <span className="ml-1.5 text-[10px] px-1.5 py-0.5 rounded align-middle"
                        style={{ background: "var(--surface2)", color: "var(--muted2)" }}
                        title="Cette crypto verse un rendement : sa valeur s'éloigne de 1 $ volontairement, en grandissant. Ce n'est pas un décrochage.">
                        rendement
                      </span>
                    )}
                  </td>
                  <td className="text-right">{usd(s.mcap)}</td>
                  <td className="text-right">{typeof s.price === "number" ? `$${s.price.toFixed(4)}` : "n/d"}</td>
                  <td className="text-right" style={{ color: off ? "#f43f5e" : "var(--muted2)" }}>
                    {isYield ? "—" : typeof s.peg_dev === "number" ? `${(s.peg_dev * 100).toFixed(2)}%` : "n/d"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

// ---- Jauge altseason (part du top 50 battant BTC sur 7 j) ----
export function Altseason({ ck }: { ck: any }) {
  const a = ck.altseason;
  if (!a?.available) return null;
  const col = a.label === "Altseason" ? "var(--pos)" : a.label === "Bitcoin" ? "#f59e0b" : "var(--muted)";
  return (
    <Card title="Bitcoin ou le reste du marché ?" source="calculé depuis CoinGecko · sur 7 jours"
      hint="Sur les 50 plus grosses cryptos, combien font mieux que le Bitcoin sur la semaine. Au-dessus de 75 %, l'argent part vers les autres cryptos ; en dessous de 25 %, le Bitcoin domine.">
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-sm font-semibold px-2.5 py-1 rounded-full"
          style={{ color: col, background: "color-mix(in srgb, " + col + " 15%, transparent)" }}>
          {a.label}
        </span>
        <span className="text-2xl mono font-semibold" style={{ color: col }}>
          {a.pct}%<span className="text-muted2 text-sm"> battent BTC</span>
        </span>
      </div>
      <div className="mt-3 h-2 rounded-full overflow-hidden" style={{ background: "var(--surface2)" }}>
        <div className="h-full rounded-full" style={{ width: `${a.pct}%`, background: col }} />
      </div>
      <div className="text-muted2 text-[11px] mt-1.5">
        sur {a.n} actifs · BTC {pct((a.btc_ret7d ?? 0) * 100)} sur 7 j
      </div>
    </Card>
  );
}

// ---- Compte à rebours du halving BTC ----
export function Halving({ ck }: { ck: any }) {
  const h = ck.halving;
  if (!h?.available) return null;
  const eta = new Date(Date.now() + h.days_left * 86400_000);
  return (
    <Card title={`Halving Bitcoin — le ${h.number}ᵉ`} source="blockchain.info · hauteur de bloc réelle"
      hint="Environ tous les quatre ans, la quantité de nouveaux bitcoins créés est divisée par deux : l'offre se raréfie d'un coup. La date est estimée à partir du rythme de création actuel.">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div><div className="text-muted text-xs">Dans</div><div className="text-lg mono">≈ {h.days_left} j</div></div>
        <div><div className="text-muted text-xs">Blocs restants</div><div className="text-lg mono">{h.blocks_left.toLocaleString("fr-FR")}</div></div>
        <div><div className="text-muted text-xs">Bloc du halving</div><div className="text-lg mono">{h.halving_block.toLocaleString("fr-FR")}</div></div>
        <div><div className="text-muted text-xs">Date estimée</div><div className="text-lg mono">{eta.toLocaleDateString("fr-FR", { month: "short", year: "numeric" })}</div></div>
      </div>
      <div className="mt-3 h-2 rounded-full overflow-hidden" style={{ background: "var(--surface2)" }}>
        <div className="h-full rounded-full" style={{ width: `${(h.progress * 100).toFixed(1)}%`, background: "var(--accent)" }} />
      </div>
      <div className="text-muted2 text-[11px] mt-1.5">{(h.progress * 100).toFixed(1)} % du cycle parcouru · hauteur {h.height.toLocaleString("fr-FR")}</div>
    </Card>
  );
}
