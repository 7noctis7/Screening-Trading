"use client";
// DE QUAND DATENT CES CHIFFRES — la question que le site ne répondait nulle part.
//
// Trois dates d'arrêté coexistaient (18/06, 02/09, 04/09) selon l'onglet ouvert. L'inventaire
// du gate de publication les imprimait déjà dans les journaux de fabrication, où personne ne
// va les lire ; à l'écran, rien. Un visiteur qui comparait le tableau de bord et le calendrier
// des résultats croyait comparer deux photos du même instant.
//
// Certaines divergences sont LÉGITIMES : une fenêtre de backtest close en juin ne devient pas
// fausse en septembre, et la crypto cote le samedi quand les actions non. Les masquer serait
// donc faux. On les rend lisibles, avec leur écart au reste du site : la divergence attendue
// se lit d'un coup d'œil, celle qui ne l'est pas saute aux yeux.
import { useMeta } from "@/lib/api";

const JOUR = 86_400_000;

function jours(a: string, b: string): number | null {
  const x = Date.parse(a.slice(0, 10)), y = Date.parse(b.slice(0, 10));
  return Number.isFinite(x) && Number.isFinite(y) ? Math.round((y - x) / JOUR) : null;
}

const fr = (d: string) => {
  const t = Date.parse(d.slice(0, 10));
  return Number.isFinite(t) ? new Date(t).toLocaleDateString("fr-FR") : d.slice(0, 10);
};

/** Bandeau « données arrêtées au … », avec l'écart au bloc le plus frais du site.
 *  `date` absente → on n'affiche RIEN plutôt qu'une date inventée ou un « n/d » anxiogène. */
export function DateArrete({ date, quoi, seuilJours = 7 }:
  { date?: string | null; quoi?: string; seuilJours?: number }) {
  const { data: meta } = useMeta();
  if (!date) return null;
  const frais = (meta as any)?.arrete_le_plus_frais as string | undefined;
  const retard = frais ? jours(date, frais) : null;
  const enRetard = retard != null && retard >= seuilJours;
  return (
    <p className="text-muted2 text-xs" title={frais ? `Bloc le plus frais du site : ${fr(frais)}.` : undefined}>
      {quoi ?? "Données"} arrêtées au <b>{fr(date)}</b>
      {enRetard && (
        <span style={{ color: "var(--warn)" }}>
          {" "}— soit {retard} jours de retard sur le reste du site ({fr(frais!)}).
          {" "}Ce n'est pas forcément une anomalie : une période de mesure close ne bouge plus.
          {" "}Mais ne comparez pas ces chiffres à ceux d'un autre onglet sans y penser.
        </span>
      )}
    </p>
  );
}
