"use client";
import s from "./intro.module.css";
import { ML_LABELS, PHASES, RISK_LABELS } from "./introConfig";

/**
 * Le HUD : ce qu'un terminal affiche pendant qu'il calcule.
 *
 * Les valeurs sont DÉRIVÉES de l'avancement, jamais aléatoires — une intro qui rejoue
 * doit rejouer à l'identique. Et elles convergent vers des ordres de grandeur que ce
 * projet assume vraiment : AUC ~0,52, pas 0,94. Afficher un edge qu'on n'a pas serait
 * exactement le genre de vitrine que ce dépôt passe son temps à démonter.
 */
export function IntroHud({ t, sortie }: { t: number; sortie: boolean }) {
  const on = t > 0.04 && t < PHASES.risk + 0.06;
  const p = (a: number, b: number) => Math.max(0, Math.min(1, (t - a) / (b - a)));

  const ml = p(PHASES.flow, PHASES.neural);
  const risk = p(PHASES.neural, PHASES.risk);
  const flux = p(PHASES.init, PHASES.flow);

  // Convergence : chaque métrique part d'une valeur instable et se fige.
  const auc = 0.500 + 0.024 * ml;
  const brier = 0.250 - 0.008 * ml;
  const ic = 0.004 + 0.011 * ml;
  const gross = 138 - 38 * risk;          // % — part de trop, puis ramenée sous 100
  const vol = 31 - 11 * risk;             // % annualisée, vers la cible
  const dd = 27 - 18 * risk;              // % — l'enveloppe se referme

  const val = [auc.toFixed(3), brier.toFixed(3), ic.toFixed(3)];
  const rsk = [`${gross.toFixed(0)} %`, `${vol.toFixed(1)} %`, `−${dd.toFixed(0)} %`];

  return (
    <div className={s.hud} data-on={on ? "1" : "0"} data-fade={sortie ? "1" : "0"}
         aria-hidden="true">
      <div className={s.hudTL}>
        <div className={s.metric}>
          <span className={s.metricK}>INSTRUMENTS</span>
          <span className={s.metricV}>{Math.round(flux * 821)}</span>
        </div>
        <div className={s.metric}>
          <span className={s.metricK}>BARRES</span>
          <span className={s.metricV}>{(flux * 2.03).toFixed(2)} M</span>
        </div>
      </div>

      <div className={s.hudTR}>
        {ML_LABELS.map((k, i) => (
          <div key={k} className={s.metric} style={{ justifyContent: "flex-end" }}>
            <span className={s.metricK} style={{ minWidth: "4em", textAlign: "right" }}>{k}</span>
            <span className={s.metricV} data-ok={ml > 0.9 ? "1" : "0"}>
              {ml > 0.03 ? val[i] : "—"}
            </span>
          </div>
        ))}
      </div>

      <div className={s.hudBL}>
        {RISK_LABELS.map((k, i) => (
          <div key={k} className={s.metric}>
            <span className={s.metricK}>{k}</span>
            <span className={s.metricV} data-risk={risk < 0.7 && risk > 0 ? "1" : "0"}
                  data-ok={risk >= 0.7 ? "1" : "0"}>
              {risk > 0.03 ? rsk[i] : "—"}
            </span>
          </div>
        ))}
      </div>

      <div className={s.progress}>
        <div className={s.progressFill} style={{ width: `${Math.min(100, t * 100)}%` }} />
      </div>
    </div>
  );
}

export default IntroHud;
