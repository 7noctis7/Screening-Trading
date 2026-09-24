"use client";
// Deux cartes, deux questions DISTINCTES : ce que le public CHERCHE (attention) et
// ce qui s'ÉCHANGE (capital engagé). Les listes se recoupent parfois et divergent
// souvent — c'est leur divergence qui informe, les fondre la détruirait.
import { Card } from "./Card";
import { usd, pct, tone, cgCoin, EXT } from "./format";

// ---- Thèmes et NFT recherchés — le MÊME appel que « ce que tout le monde cherche ».
// Ces deux listes étaient téléchargées puis jetées par le parseur. Les catégories valent
// souvent mieux qu'un jeton isolé : elles disent quel THÈME le public cherche, ce qui
// bouge moins vite qu'un ticker de rang 900. ----
export function ThemesRecherches({ ck }: { ck: any }) {
  const a = (ck.trending_autres ?? {}) as any;
  const cats = (a.categories ?? []) as any[];
  const nfts = (a.nfts ?? []) as any[];
  if (!cats.length && !nfts.length) return null;
  return (
    <Card title="Les thèmes que le public cherche" source="CoinGecko · tendances de recherche"
      hint="Même source que la carte précédente, autre granularité. Un THÈME recherché bouge moins vite qu'un jeton isolé : c'est un thermomètre un peu moins bruyant, pas un signal pour autant.">
      {cats.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-3">
          {cats.map((c, i) => (
            <span key={(c.id ?? c.name) + i}
              className="text-xs px-2.5 py-1.5 rounded-lg border border-border"
              style={{ background: "var(--surface)" }}>
              <b>{c.name}</b>{" "}
              <span style={{ color: tone(c.chg24h) }}>{pct(c.chg24h)}</span>
            </span>
          ))}
        </div>
      )}
      {nfts.length > 0 && (
        <>
          <div className="text-[11px] text-muted2 mb-1.5">Collections NFT — prix plancher</div>
          <div className="flex flex-wrap gap-2">
            {nfts.map((n, i) => (
              <span key={(n.sym ?? n.name) + i}
                className="text-xs px-2.5 py-1.5 rounded-lg border border-border"
                style={{ background: "var(--surface)" }}>
                <b>{n.sym || n.name}</b>{" "}
                <span className="text-muted">
                  {typeof n.plancher === "number"
                    ? `${n.plancher} ${String(n.devise ?? "").toUpperCase()}`
                    : "n/d"}
                </span>{" "}
                <span style={{ color: tone(n.chg24h) }}>{pct(n.chg24h)}</span>
              </span>
            ))}
          </div>
        </>
      )}
    </Card>
  );
}

// ---- Ce qui S'ÉCHANGE le plus — une AUTRE question que « ce qui est recherché ».
// Le volume mesure du capital engagé, la recherche mesure de l'attention. Les deux
// listes se recoupent parfois et divergent souvent, et c'est leur divergence qui est
// informative : les fondre en une carte détruirait cette information. ----
export function VolumeTop({ ck }: { ck: any }) {
  const rows = (ck.volume_top ?? []) as any[];
  if (!rows.length) return null;
  return (
    <Card title="Ce qui s'échange le plus" source="CoinGecko · volume 24 h, top 20"
      hint="Classement par volume échangé sur 24 h — du capital qui bouge, pas de l'attention. La « rotation » est le volume rapporté à la capitalisation : au-delà de 1, l'actif change de mains plus vite que sa valeur totale en une journée. Aucun seuil n'a été calibré ici : le chiffre est rendu, pas interprété.">
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead className="text-muted2">
            <tr>
              <th className="text-left font-normal py-1">#</th>
              <th className="text-left font-normal">Actif</th>
              <th className="text-right font-normal">Prix</th>
              <th className="text-right font-normal">24 h</th>
              <th className="text-right font-normal">Volume 24 h</th>
              <th className="text-right font-normal">Rotation</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              const href = cgCoin(r.id);
              return (
                <tr key={(r.sym ?? "") + i} className="border-t border-border">
                  <td className="py-1.5 text-muted2">{i + 1}</td>
                  <td>
                    {href ? (
                      <a href={href} {...EXT} className="hover:text-accent transition-colors"
                        title={`${r.name} — ouvrir la fiche complète sur CoinGecko`}>
                        <b>{r.sym}</b> <span className="text-muted">{r.name}</span>
                      </a>
                    ) : (<><b>{r.sym}</b> <span className="text-muted">{r.name}</span></>)}
                  </td>
                  <td className="text-right tabular-nums">{usd(r.prix)}</td>
                  <td className="text-right tabular-nums" style={{ color: tone(r.chg24h) }}>
                    {pct(r.chg24h)}
                  </td>
                  <td className="text-right tabular-nums">{usd(r.volume)}</td>
                  <td className="text-right tabular-nums text-muted">
                    {typeof r.rotation === "number" ? r.rotation.toFixed(2) : "n/d"}
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
