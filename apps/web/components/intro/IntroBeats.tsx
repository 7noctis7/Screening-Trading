"use client";
import s from "./intro.module.css";
import { BEATS, CHIFFRES_FIXES } from "./introConfig";
import { IntroCourbes, Periode } from "./IntroCourbes";

export type IntroData = {
  disponible?: boolean;
  reference_nom?: string;
  periodes?: Periode[];
  trades?: {
    disponible?: boolean; n?: number; profit_factor?: number | null;
    ratio_gain_perte?: number | null; esperance_par_trade?: number;
    esperance_pct?: number | null; taux_reussite?: number | null;
  };
  avertissement?: string;
};

const pct = (v: number | null | undefined, d = 1) =>
  v == null ? "n/d" : `${v >= 0 ? "+" : ""}${(v * 100).toFixed(d)} %`;
const num = (v: number | null | undefined, d = 2) =>
  v == null ? "n/d" : v.toFixed(d);

/**
 * Les mots de l'intro, rendus par le DOM — pas par le canvas.
 *
 * À cette taille, du texte canvas est rastérisé au DPR sans hinting : plus flou, hors de
 * la police du site, non sélectionnable. Le canvas fait le MOUVEMENT, le DOM fait les MOTS.
 *
 * Aucun chiffre de performance n'est écrit ici : ils viennent de `/api/intro`, régénéré à
 * chaque construction du snapshot. Absent → « n/d », jamais une valeur de remplacement.
 */
export function IntroBeats({ i, p, sortie, data }: {
  i: number; p: number; sortie: boolean; data?: IntroData;
}) {
  const b = BEATS[i];
  if (!b || b.genre === "reveal") return null;
  const on = p > 0.05 && p < 0.9 && !sortie;

  if (b.genre === "chiffre") {
    const c = CHIFFRES_FIXES[b.cle];
    if (!c) return null;
    return (
      <Bloc on={on} sur={b.sur} chiffre={c.chiffre} unite={c.unite} sous={c.sous} />
    );
  }

  if (b.genre === "trades") {
    const t = data?.trades;
    if (!t?.disponible) return null;
    return (
      <Bloc on={on} sur={b.sur} chiffre={num(t.profit_factor)} unite="PROFIT FACTOR"
            sous={`R:R ${num(t.ratio_gain_perte)} · espérance ${pct(t.esperance_pct, 2)} `
                  + `par trade · ${t.n} trades clôturés`} />
    );
  }

  // Battement de période : la fenêtre, les trois chiffres, puis les deux courbes.
  const d = (data?.periodes || []).find((x) => x.cle === b.fenetre);
  if (!d?.disponible) return null;
  return (
    <div className={s.beatWrap} data-courbes={on ? "1" : "0"}>
      <div className={s.beat} data-on={on ? "1" : "0"}>
        <div className={s.beatSur}>{d.libelle}</div>
        <div className={s.beatNum}>{pct(d.croissance, 0)}</div>
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
