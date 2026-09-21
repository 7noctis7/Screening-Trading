"use client";
import s from "./intro.module.css";
import { BEATS, CHIFFRES_FIXES } from "./introConfig";
import { clamp01, easeOut } from "./introCourbeDraw";
import { IntroCourbes, Periode } from "./IntroCourbes";

/** POURQUOI la donnée manque, quand `/api/intro` n'a rien renvoyé DU TOUT.
 *
 *  « /api/intro n'a rien renvoyé » était exact et inutilisable : ça n'aide pas à savoir
 *  s'il faut attendre, relancer l'API, ou aller chercher un trou dans les données. Or la
 *  requête, elle, SAIT dans lequel des deux cas on est.
 *
 *  Le cas « attente » est de loin le plus fréquent et le moins inquiétant : `/api/intro`
 *  est servi par le snapshot complet, et après un `make up` l'API le reconstruit pendant
 *  une à trois minutes pendant que le rideau, lui, ne patiente que 2,5 s. */
const SANS_REPONSE: Record<string, string> = {
  attente: "/api/intro n'a pas encore répondu — le snapshot se reconstruit "
         + "(1 à 3 min après un « make up »). Rejouez l'intro dans une minute.",
  erreur: "/api/intro injoignable — l'API ne répond pas (curl .../health).",
};
const sansReponse = (etat?: string) =>
  SANS_REPONSE[etat ?? ""] ?? "/api/intro n'a rien renvoyé";

/** Libellés de repli : quand la période manque, on nomme quand même la fenêtre — sinon
 *  « donnée indisponible » ne dit pas DE QUOI. */
const LIBELLES: Record<string, string> = {
  ytd: "DEPUIS LE 1ᵉʳ JANVIER", "3a": "3 ANS", "5a": "5 ANS",
  "10a": "10 ANS", tout: "DEPUIS LE DÉBUT",
};

export type IntroData = {
  disponible?: boolean;
  reference_nom?: string;
  periodes?: Periode[];
  trades?: {
    disponible?: boolean; motif?: string; n?: number; profit_factor?: number | null;
    ratio_gain_perte?: number | null; esperance_par_trade?: number;
    esperance_pct?: number | null; taux_reussite?: number | null;
    /** Réalisé des aller-retours CLÔTURÉS, en dollars. Publié par l'API depuis le
     *  début (`intro_payload.trades`) et ignoré par ce composant jusqu'au 21/09 :
     *  l'intro montrait un profit factor sans jamais dire combien il avait rapporté. */
    pnl_total?: number | null;
  };
  avertissement?: string;
};

const pct = (v: number | null | undefined, d = 1) =>
  v == null ? "n/d" : `${v >= 0 ? "+" : ""}${(v * 100).toFixed(d)} %`;
const num = (v: number | null | undefined, d = 2) =>
  v == null ? "n/d" : v.toFixed(d);
/** Le réalisé en dollars, signé. « n/d » quand il manque — jamais zéro, qui se lirait
 *  « le robot n'a rien gagné » là où il faut lire « on ne sait pas ». */
const usd = (v: number | null | undefined) =>
  v == null ? "n/d" : `${v >= 0 ? "+" : "−"}$${Math.abs(v).toLocaleString("fr-FR",
    { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

/** Le chiffre monte de zéro à sa valeur sur le premier tiers du battement.
 *
 *  Un nombre POSÉ se lit ; un nombre qui MONTE se regarde monter — c'est la seule seconde
 *  où l'œil reste sur lui. Le compteur s'arrête net à la valeur réelle : il n'a pas le
 *  droit de dépasser puis revenir, ce serait afficher un chiffre qui n'existe pas. */
const DEBUT_COMPTE = 0.03;
// 0,25 d'un battement de 3,4 s ≈ 0,85 s de montée, puis 2,5 s de chiffre POSÉ. Allonger le
// battement sans resserrer le compteur aurait seulement fait monter le nombre plus
// longtemps — pas donné plus de temps pour le lire.
const FIN_COMPTE = 0.25;
const compte = (p: number) => easeOut(clamp01((p - DEBUT_COMPTE) / (FIN_COMPTE - DEBUT_COMPTE)));

/**
 * Les mots de l'intro, rendus par le DOM — pas par le canvas.
 *
 * À cette taille, du texte canvas est rastérisé au DPR sans hinting : plus flou, hors de
 * la police du site, non sélectionnable. Le canvas fait le MOUVEMENT, le DOM fait les MOTS.
 *
 * Aucun chiffre de performance n'est écrit ici : ils viennent de `/api/intro`, régénéré à
 * chaque construction du snapshot. Absent → « n/d », jamais une valeur de remplacement.
 */
export function IntroBeats({ i, p, sortie, data, etat }: {
  i: number; p: number; sortie: boolean; data?: IntroData;
  /** État de la requête quand `data` est absente : « attente » ou « erreur ». */
  etat?: "attente" | "erreur";
}) {
  const b = BEATS[i];
  if (!b || b.genre === "reveal") return null;
  const on = p > 0.05 && p < 0.9 && !sortie;
  const k = compte(p);

  if (b.genre === "chiffre") {
    const c = CHIFFRES_FIXES[b.cle];
    if (!c) return null;
    const chiffre = c.valeur != null
      ? Math.round(c.valeur * k).toLocaleString("fr-FR")
      : c.chiffre;
    return <Bloc on={on} sur={b.sur} chiffre={chiffre} unite={c.unite} sous={c.sous} />;
  }

  if (b.genre === "trades") {
    const t = data?.trades;
    if (!t?.disponible) {
      return <Absent on={on} sur={b.sur}
                     motif={t?.motif || (data ? "aucun trade clôturé"
                                              : sansReponse(etat))} />;
    }
    // LE RÉALISÉ EN TÊTE DE LA SOUS-LIGNE. « Profit factor 1,34 » ne dit pas si le
    // robot a gagné dix dollars ou dix mille ; c'est pourtant la première chose qu'on
    // veut savoir. Il est marqué BRUT parce qu'il l'est : chez ce courtier les frais
    // sont des activités séparées, absentes du flux d'ordres.
    return (
      <Bloc on={on} sur={b.sur}
            chiffre={t.profit_factor == null ? "n/d" : num(t.profit_factor * k)}
            unite="PROFIT FACTOR"
            sous={`${usd(t.pnl_total)} réalisé BRUT · R:R ${num(t.ratio_gain_perte)} · `
                  + `espérance ${pct(t.esperance_pct, 2)} par trade · `
                  + `${t.n} trades clôturés`} />
    );
  }

  // Battement de période : la fenêtre, les trois chiffres, puis les deux courbes.
  const d = (data?.periodes || []).find((x) => x.cle === b.fenetre);
  // UNE ABSENCE SE DIT. Rendre `null` faisait disparaître le battement sans un mot : cinq
  // secondes de noir au milieu de l'intro, impossibles à distinguer d'une panne. On ne sait
  // alors ni que la donnée manque, ni pourquoi — et on cherche le défaut dans le composant
  // qui, lui, fonctionne. C'est ce qui a coûté deux allers-retours de diagnostic le 16/09.
  if (!d?.disponible) {
    return <Absent on={on} sur={LIBELLES[b.fenetre ?? ""] ?? "FENÊTRE"}
                   motif={d?.motif || (data ? "période absente du payload"
                                             : sansReponse(etat))} />;
  }
  return (
    <div className={s.beatWrap} data-courbes={on ? "1" : "0"}>
      <div className={s.beat} data-on={on ? "1" : "0"}>
        <div className={s.beatSur}>{d.libelle}</div>
        <div className={s.beatNum}>
          {d.croissance == null ? "n/d" : pct(d.croissance * k, 0)}
        </div>
        <div className={s.beatUnite}>
          {d.cagr != null ? `${pct(d.cagr)} PAR AN` : "CROISSANCE TOTALE"}
          {d.max_drawdown != null && ` · PIRE RECUL ${pct(d.max_drawdown, 0)}`}
        </div>
      </div>
      <IntroCourbes p={p} periode={d} nomRef={data?.reference_nom || "S&P 500"} />
      {data?.avertissement && <div className={s.avert}>{data.avertissement}</div>}
    </div>
  );
}

/** Ce qui s'affiche quand la donnée manque : la fenêtre, et POURQUOI elle est vide. */
function Absent({ on, sur, motif }: { on: boolean; sur: string; motif: string }) {
  return (
    <div className={s.beat} data-on={on ? "1" : "0"} aria-hidden="true">
      <div className={s.beatSur}>{sur}</div>
      <div className={s.absent}>DONNÉE INDISPONIBLE</div>
      <div className={s.absentMotif}>{motif}</div>
    </div>
  );
}

function Bloc({ on, sur, chiffre, unite, sous }: {
  on: boolean; sur: string; chiffre: string; unite: string; sous: string;
}) {
  return (
    <div className={s.beat} data-on={on ? "1" : "0"} aria-hidden="true">
      <div className={s.beatSur}>{sur}</div>
      <div className={s.beatNum}>{chiffre}</div>
      <div className={s.beatUnite}>{unite}</div>
      <div className={s.beatSous}>{sous}</div>
    </div>
  );
}

export default IntroBeats;
