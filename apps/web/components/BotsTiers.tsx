"use client";
import { usePortefeuille } from "@/lib/api";
import { couleurLigne } from "@/lib/couleurs";

// LES AUTRES ROBOTS (« XIII indic »), à côté du nôtre — et JAMAIS dedans.
//
// Lus par `/api/portefeuille` sous la clé `bots`, chez le courtier, avec la même fraîcheur
// que le bandeau du compte. Ce sont des BENCHMARKS : leur equity et leurs lignes ne sont
// pas ajoutées au total du robot (cf. `packages/execution/bots_tiers`), sinon le tableau
// de bord mesurerait deux stratégies à la fois.
//
// Un bot sans clés n'apparaît pas ; un bot configuré mais muet est NOMMÉ avec son motif.

const VERT = "#22c55e";
const ROUGE = "#ef4444";
const usd = (x?: number | null) =>
  x == null ? "—" : `${x.toLocaleString("fr-FR", { maximumFractionDigits: 2 })} $`;
const pct = (x?: number | null) =>
  x == null ? "—" : `${x >= 0 ? "+" : ""}${(x * 100).toFixed(2)} %`;
const signe = (x?: number | null) => (x == null ? undefined : x >= 0 ? VERT : ROUGE);

type Ligne = { symbole: string; qty: number | null; prix: number | null;
               valeur: number | null; pnl: number | null; pnl_pct: number | null };
type Bot = { cle: string; nom: string; ok: boolean; equity: number | null;
             latent: number | null; n_positions: number | null; positions: Ligne[];
             motif: string | null };

function CarteBot({ b }: { b: Bot }) {
  const col = couleurLigne(b.nom);
  return (
    <section className="card p-4 overflow-x-auto">
      <div className="flex flex-wrap items-baseline gap-x-5 gap-y-1 mb-2">
        <h2 className="text-sm uppercase tracking-wide" style={{ color: col }}>
          <span className="inline-block w-2 h-2 rounded-full mr-2 align-middle"
                style={{ background: col }} />
          {b.nom} <span className="text-muted2 normal-case text-[11px]">· autre robot, compte séparé</span>
        </h2>
        {b.ok && (
          <>
            <span className="text-sm"><span className="text-muted text-xs">valeur du compte </span>
              <span className="font-semibold tabular-nums">{usd(b.equity)}</span></span>
            <span className="text-sm"><span className="text-muted text-xs">latent </span>
              <span className="font-semibold tabular-nums" style={{ color: signe(b.latent) }}>
                {usd(b.latent)}</span></span>
            <span className="text-sm"><span className="text-muted text-xs">lignes </span>
              <span className="font-semibold tabular-nums">{b.n_positions}</span></span>
          </>
        )}
      </div>
      {!b.ok ? (
        <p className="text-xs text-muted">Compte illisible — {b.motif ?? "sans réponse"}.</p>
      ) : b.positions.length === 0 ? (
        <p className="text-xs text-muted">Aucune position ouverte.</p>
      ) : (
        <table className="w-full text-sm" style={{ minWidth: 520 }}>
          <thead><tr className="text-muted text-[11px] uppercase tracking-wide">
            <th className="text-left font-medium pb-2">Actif</th>
            <th className="text-right font-medium pb-2">Quantité</th>
            <th className="text-right font-medium pb-2">Prix</th>
            <th className="text-right font-medium pb-2">Valeur</th>
            <th className="text-right font-medium pb-2">Latent</th>
          </tr></thead>
          <tbody className="tabular-nums">
            {b.positions.map((p) => (
              <tr key={p.symbole} className="border-t border-border">
                <td className="py-1.5">{p.symbole}</td>
                <td className="text-right">{p.qty ?? "—"}</td>
                <td className="text-right">{usd(p.prix)}</td>
                <td className="text-right">{usd(p.valeur)}</td>
                <td className="text-right" style={{ color: signe(p.pnl) }}>
                  {usd(p.pnl)} <span className="text-muted">({pct(p.pnl_pct)})</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="text-[11px] text-muted2 mt-2">
        Affiché comme référence : ni son equity ni ses lignes n'entrent dans le total de votre
        robot. Lecture seule — rien n'est envoyé à ce compte depuis ce terminal.
      </p>
    </section>
  );
}

export function BotsTiers() {
  const { data } = usePortefeuille();
  const bots: Bot[] = data?.bots ?? [];
  if (!bots.length) return null;
  return <>{bots.map((b) => <CarteBot key={b.cle} b={b} />)}</>;
}
