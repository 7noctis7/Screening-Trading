"use client";
import { useEffect, useState } from "react";

/** Préférences sectorielles — des CONTRAINTES, pas des vues de marché.
 *
 *  « Privilégier la santé » peut vouloir dire deux choses. Soit « je crois que la santé va
 *  surperformer » : c'est une prévision, et rien dans ce dépôt ne la valide — l'IC du score
 *  de sélection y vaut +0,0202 pour t = 0,76. Soit « je veux au moins x % de mon
 *  portefeuille en santé, pour des raisons qui m'appartiennent » : c'est une contrainte,
 *  légitime, qui n'exige aucune preuve. Cet écran n'implémente que la seconde.
 *
 *  Une exclusion ne demande aucune justification : refuser un secteur est une décision
 *  personnelle. Un plancher, lui, DÉTOURNE du poids d'une allocation qui minimisait le
 *  risque — la recommandation affiche donc ce que la contrainte coûte, en volatilité et en
 *  diversification. Une préférence qu'on croit gratuite est une préférence mal posée.
 *
 *  Comme le profil, tout reste dans ce navigateur (clé `quant.preferences`) et n'est
 *  transmis qu'au calcul local, qui n'en conserve rien. */
const STOCK = "quant.preferences";

type Prefs = { exclure: string[]; planchers: Record<string, number>; plafonds: Record<string, number> };
const VIDE: Prefs = { exclure: [], planchers: {}, plafonds: {} };

export function PreferencesSecteurs({ secteurs }: { secteurs: string[] }) {
  const [prefs, setPrefs] = useState<Prefs>(VIDE);
  const [lu, setLu] = useState(false);

  useEffect(() => {
    try { const b = localStorage.getItem(STOCK); if (b) setPrefs({ ...VIDE, ...JSON.parse(b) }); }
    catch { /* sans effet */ }
    setLu(true);
  }, []);
  useEffect(() => {
    if (!lu) return;                       // ne jamais écrire avant d'avoir lu
    try { localStorage.setItem(STOCK, JSON.stringify(prefs)); } catch { /* sans effet */ }
  }, [prefs, lu]);

  const bascule = (secteur: string) => setPrefs((p) => ({
    ...p,
    exclure: p.exclure.includes(secteur)
      ? p.exclure.filter((s) => s !== secteur)
      : [...p.exclure, secteur],
  }));
  const seuil = (cle: "planchers" | "plafonds", secteur: string, valeur: string) =>
    setPrefs((p) => {
      const suite = { ...p[cle] };
      const n = Number(valeur);
      if (!valeur || !Number.isFinite(n) || n <= 0) delete suite[secteur];
      else suite[secteur] = Math.min(100, n) / 100;
      return { ...p, [cle]: suite };
    });

  return <section className="card space-y-3">
    <div>
      <div className="eyebrow">Préférences sectorielles</div>
      <h2 className="text-lg font-semibold mt-1">Ce que vous voulez, ou ne voulez pas, détenir</h2>
      <p className="text-xs text-muted mt-1">
        Des <b>contraintes</b>, pas des prévisions. Exclure un secteur ne demande aucune
        justification. Imposer un plancher détourne du poids d'une allocation qui minimisait le
        risque : la recommandation vous montrera ce que cela coûte, en volatilité et en
        diversification. Rien n'est envoyé ni conservé.
      </p>
    </div>
    <div className="overflow-x-auto"><table><thead><tr>
      <th>Secteur</th><th>Exclure</th><th>Au moins (%)</th><th>Au plus (%)</th>
    </tr></thead><tbody>
      {secteurs.map((secteur) => {
        const exclu = prefs.exclure.includes(secteur);
        return <tr key={secteur}>
          <td className={exclu ? "line-through text-muted" : ""}>{secteur}</td>
          <td className="text-center">
            <input type="checkbox" checked={exclu} onChange={() => bascule(secteur)}
              aria-label={`Exclure ${secteur}`} />
          </td>
          {(["planchers", "plafonds"] as const).map((cle) => <td key={cle} className="text-right">
            <input type="number" min="0" max="100" disabled={exclu}
              value={prefs[cle][secteur] != null ? Math.round(prefs[cle][secteur] * 100) : ""}
              onChange={(e) => seuil(cle, secteur, e.target.value)}
              className="w-20 rounded-lg border border-border bg-surface p-1 mono text-fg text-right disabled:opacity-40" />
          </td>)}
        </tr>;
      })}
    </tbody></table></div>
    <p className="text-[11px] text-muted2">
      Un plancher ne peut pas créer une position que le modèle de risque n'a pas retenue : si
      aucune ligne du secteur n'est dans la sélection, la contrainte est déclarée non satisfaite
      plutôt qu'appliquée en inventant des lignes. Une exclusion prime toujours sur un plancher.
    </p>
  </section>;
}
