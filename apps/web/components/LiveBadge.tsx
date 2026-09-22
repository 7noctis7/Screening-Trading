"use client";
import { useEffect, useState } from "react";
import { useDashboard } from "@/lib/api";

// FRAÎCHEUR DE LA DONNÉE, PAS DE LA REQUÊTE.
//
// Ce bandeau lisait `dataUpdatedAt` — l'instant où le NAVIGATEUR a interrogé l'API. Or
// l'API répond instantanément depuis un cache serveur (`_TTL_S`, 15 min), rafraîchi en
// arrière-plan. Le badge affichait donc « LIVE · il y a 1s » sur un snapshot vieux d'un
// quart d'heure, point vert pulsant à l'appui — constaté sur la page Positions, qui
// listait dix-huit lignes vendues treize minutes plus tôt.
//
// Il mesurait l'aller-retour réseau et le présentait comme l'âge de la donnée. Le serveur
// envoie désormais `snapshot_age_s` ; on y ajoute le temps écoulé depuis la réponse.
const AMBRE = "#f59e0b";
const VERT = "#22c55e";
const ROUGE = "#ef4444";

function libelle(secs: number): string {
  if (secs < 60) return `il y a ${secs}s`;
  if (secs < 3600) return `il y a ${Math.round(secs / 60)}min`;
  const h = Math.floor(secs / 3600);
  return `il y a ${h}h${String(Math.round((secs % 3600) / 60)).padStart(2, "0")}`;
}

export function LiveBadge() {
  const { data, dataUpdatedAt, isFetching } = useDashboard();
  const [, tick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => tick((x) => x + 1), 1000);
    return () => clearInterval(id);
  }, []);

  const ageServeur: number | undefined = data?.snapshot_age_s;
  const ttl: number = data?.snapshot_ttl_s ?? 900;
  // LE SERVEUR EST-IL EN TRAIN DE REFAIRE LE SNAPSHOT ? « Périmé » et « en cours de
  // reconstruction » ne sont pas la même chose, et le badge disait DIFFÉRÉ pour les deux.
  // Mesuré le 22/09 : trois quarts d'heure de DIFFÉRÉ, zéro échec au journal — le serveur
  // reconstruisait, simplement. Une alarme qui se déclenche sur le cas normal cesse d'être
  // lue le jour où elle a raison.
  const refait: boolean = data?.snapshot_etat === "pret_rafraichissement";
  // Âge au moment de la réponse + temps écoulé depuis. Aucune horloge partagée requise.
  const secs =
    ageServeur == null || !dataUpdatedAt
      ? null
      : Math.max(0, Math.round(ageServeur + (Date.now() - dataUpdatedAt) / 1000));

  // Au-delà du TTL, la donnée servie n'est plus « live » — mais ça ne dit pas encore si
  // quelque chose ne va pas : le serveur est peut-être en train de la refaire.
  const perime = secs != null && secs > ttl;
  // DIFFÉRÉ NE PARLE PLUS QUE DE CE QU'IL DÉCRIT. La reconstruction n'étant déclenchée
  // QUE par une requête du front, « périmé ET aucune reconstruction en cours » est un
  // état qui ne devrait pas exister : c'est devenu un vrai signal, celui d'un rebuild
  // qui échoue (`snapshot rebuild failed` au journal du serveur).
  const bloque = perime && !refait;
  const tresPerime = secs != null && secs > ttl * 2 && !refait;
  const couleur = refait ? AMBRE : tresPerime ? ROUGE : bloque ? AMBRE : VERT;
  const mot = refait ? "MAJ EN COURS" : bloque ? "DIFFÉRÉ" : "LIVE";
  // `isFetching` est le va-et-vient du NAVIGATEUR, pas le travail du serveur : il ne
  // change que le texte, jamais le mot — les confondre remplacerait un diagnostic par
  // un clignotement toutes les quinze secondes.
  const texte = isFetching ? "maj…" : secs == null ? "—" : libelle(secs);
  const heure =
    secs == null ? null : new Date(Date.now() - secs * 1000).toLocaleTimeString("fr-FR",
      { hour: "2-digit", minute: "2-digit" });

  return (
    <span
      className="hidden sm:inline-flex items-center gap-1.5 text-[11px] text-muted px-2 py-1 rounded-md border border-border"
      title={
        secs == null
          ? "Âge du snapshot inconnu"
          : refait
            ? `Données calculées à ${heure}. Le serveur en construit une nouvelle version EN CE MOMENT (1 à 3 min) ; en attendant il sert celle-ci, sans attente.`
            : bloque
              ? `Données calculées à ${heure}, soit au-delà des ${Math.round(ttl / 60)} min prévues, et AUCUNE reconstruction n'est en cours. Vérifier le journal du serveur : grep 'snapshot rebuil' logs/app.log`
              : `Données calculées à ${heure}. Le serveur les recalcule toutes les ${Math.round(ttl / 60)} min ; entre deux, il sert la dernière version connue.`
      }
    >
      <span
        className="inline-block w-1.5 h-1.5 rounded-full"
        style={{ background: couleur, boxShadow: `0 0 8px ${couleur}` }}
      />
      {mot} <span className="text-muted2">{texte}</span>
    </span>
  );
}
