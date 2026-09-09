// LA MÊME CONCLUSION, PARTOUT — la jointure que seule la fiche savait faire.
//
// `/fiche` assemblait déjà score, fondamentaux, actualité, conviction, position détenue et
// poids cible pour arriver à « et donc, j'achète ou pas ». Le screener, lui, s'arrêtait au
// classement : il fallait ouvrir quinze fiches, une par une, pour savoir ce que le site
// pensait de ses propres candidats.
//
// La jointure était donc écrite une fois et utilisable une fois. Elle est ici, partagée : le
// screener conclut désormais avec EXACTEMENT le même moteur que la fiche — ni un seuil
// différent, ni un raccourci « version liste ». Deux verdicts divergents sur le même titre
// selon la page qu'on ouvre, c'est précisément ce qu'il ne faut pas construire.
//
// Aucun chiffre nouveau n'est calculé ici : on rassemble ceux qui existent déjà.
import { useMemo } from "react";
import {
  useConviction, useFundamentals, usePositions, useSentiment,
} from "@/lib/api";
import { decide, type Decision } from "@/lib/decision";

/** Rapproche les symboles écrits différemment selon la source (BTC-USD, BTCUSDT, BTC). */
const norm = (s: string) =>
  (s || "").toUpperCase().replace(/[/\-]/g, "").replace(/(USDT|USDC|USD)$/, "");

/** Verdicts par symbole, prêts à afficher. Les sources absentes ne votent pas :
 *  `decide()` compte les étages réellement mesurés et devient prudent quand il en manque. */
export function useVerdicts(lignes: { symbol: string; ret_12m?: number | null }[] | undefined) {
  const { data: fund } = useFundamentals();
  const { data: sent } = useSentiment();
  const { data: conv } = useConviction();
  const { data: pos } = usePositions();

  return useMemo(() => {
    const out: Record<string, Decision> = {};
    if (!lignes?.length) return out;

    const index = (rows: any[] | undefined) => {
      const m: Record<string, any> = {};
      for (const r of rows ?? []) m[norm(r?.symbol ?? "")] = r;
      return m;
    };
    const F = index(fund?.rows), S = index(sent?.rows), C = index(conv?.rows);
    const P = index(pos?.real_positions), T = index(pos?.preset_allocation);
    // Valeur investie = somme des positions réelles. Absente, l'écart reste en points.
    const valeur = (pos?.real_positions ?? [])
      .reduce((t: number, p: any) => t + (Number(p?.market_value) || 0), 0) || null;

    for (const l of lignes) {
      const k = norm(l.symbol);
      const f = F[k], p = P[k], t = T[k], c = C[k];
      out[l.symbol] = decide({
        piotroski: f?.piotroski, altmanZ: f?.altman_z, margeSecurite: f?.margin_of_safety,
        ret12m: l.ret_12m, conviction: c?.conviction, sentiment: S[k]?.score,
        poidsCible: c?.target_weight ?? t?.weight ?? null,
        poidsActuel: p && valeur ? (Number(p.market_value) || 0) / valeur : (p ? null : 0),
        valeurPortefeuille: valeur,
      });
    }
    return out;
  }, [lignes, fund, sent, conv, pos]);
}
