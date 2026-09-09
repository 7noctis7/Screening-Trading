"use client";
/** Primitives visuelles du panneau « Pouls du portefeuille ».
 *
 *  Séparées du panneau pour tenir la limite de 400 lignes/fichier de CLAUDE.md, et parce
 *  qu'elles n'ont AUCUNE connaissance des données : elles reçoivent des nombres bornés
 *  et rendent des pixels. Toutes les couleurs passent par les jetons de thème
 *  (`--pos`, `--neg`, `--muted`, `--accent`) : un littéral hexadécimal serait juste dans
 *  un thème et faux dans l'autre — c'est exactement le défaut corrigé sur les couleurs
 *  de benchmark le 09/09.
 */

export const TEINTE = (score: number | null | undefined) =>
  score == null ? "var(--muted)" : score > 0.05 ? "var(--pos)" : score < -0.05 ? "var(--neg)" : "var(--muted)";

export const FLECHE = (score: number | null | undefined) =>
  score == null ? "·" : score > 0.05 ? "▲" : score < -0.05 ? "▼" : "–";

export const LIBELLE: Record<string, string> = {
  bullish: "Haussier", bearish: "Baissier", neutral: "Neutre", inconnu: "Non mesuré",
};

/** Arc semi-circulaire gradué −1 → +1, avec aiguille. Le dégradé n'est PAS décoratif :
 *  il donne l'échelle sans axe écrit, sur une plage que le lecteur ne connaît pas
 *  d'avance. L'aiguille se lit à l'angle, pas à la couleur — un daltonien lit la même
 *  chose. */
export function Jauge({ score, taille = 168 }: { score: number | null; taille?: number }) {
  const R = taille / 2 - 14, cx = taille / 2, cy = R + 12;
  const borne = Math.max(-1, Math.min(1, score ?? 0));
  const angle = Math.PI * (1 - (borne + 1) / 2);
  const ax = cx + (R - 6) * Math.cos(angle), ay = cy - (R - 6) * Math.sin(angle);
  const id = `jauge-${taille}`;
  return <svg width={taille} height={cy + 18} viewBox={`0 0 ${taille} ${cy + 18}`} role="img"
    aria-label={`humeur ${score == null ? "non mesurée" : borne.toFixed(2)} sur une échelle de -1 à +1`}>
    <defs>
      <linearGradient id={id} x1="0" y1="0" x2="1" y2="0">
        <stop offset="0%" style={{ stopColor: "var(--neg)" }} />
        <stop offset="50%" style={{ stopColor: "var(--muted)" }} />
        <stop offset="100%" style={{ stopColor: "var(--pos)" }} />
      </linearGradient>
    </defs>
    <path d={`M ${cx - R} ${cy} A ${R} ${R} 0 0 1 ${cx + R} ${cy}`} fill="none"
      stroke={`url(#${id})`} strokeWidth={10} strokeLinecap="round" opacity={score == null ? 0.28 : 1} />
    {score != null && <>
      <line x1={cx} y1={cy} x2={ax} y2={ay} stroke={TEINTE(score)} strokeWidth={2.5} strokeLinecap="round"
        style={{ filter: `drop-shadow(0 0 6px ${TEINTE(score)})` }} />
      <circle cx={cx} cy={cy} r={4} fill={TEINTE(score)} />
    </>}
    <text x={cx} y={cy - 8} textAnchor="middle" className="display mono" fontSize={26}
      fill={TEINTE(score)}>{score == null ? "—" : (score > 0 ? "+" : "") + score.toFixed(2)}</text>
    <text x={cx - R} y={cy + 15} textAnchor="middle" fontSize={9} fill="var(--muted2)">−1</text>
    <text x={cx + R} y={cy + 15} textAnchor="middle" fontSize={9} fill="var(--muted2)">+1</text>
  </svg>;
}

/** Barre signée centrée sur zéro : la longueur dit l'intensité, le côté dit le sens.
 *  Un simple pourcentage de remplissage ferait passer −0,8 pour « presque vide » et
 *  +0,1 pour « un peu rempli » — deux lectures fausses du même axe. */
export function BarreSignee({ score, hauteur = 6 }: { score: number | null; hauteur?: number }) {
  const v = Math.max(-1, Math.min(1, score ?? 0));
  const largeur = Math.abs(v) * 50;
  return <div className="relative w-full rounded-full overflow-hidden" style={{ height: hauteur, background: "color-mix(in srgb, var(--fg) 8%, transparent)" }}>
    <div className="absolute top-0 bottom-0" style={{ left: "50%", width: 1, background: "var(--border)" }} />
    {score != null && <div className="absolute top-0 bottom-0 rounded-full" style={{
      [v >= 0 ? "left" : "right"]: "50%", width: `${largeur}%`, background: TEINTE(score),
      boxShadow: `0 0 8px ${TEINTE(score)}`,
    } as React.CSSProperties} />}
  </div>;
}

/** Filtre segmenté. Un compteur par segment : un filtre qui ne dit pas combien il
 *  cache se lit comme une liste vide quand il ne reste rien. */
export function Segments({ options, actif, onChange }: {
  options: [string, string, number][]; actif: string; onChange: (v: string) => void;
}) {
  return <div className="flex flex-wrap gap-1">
    {options.map(([cle, texte, n]) => {
      const on = cle === actif;
      return <button key={cle} type="button" onClick={() => onChange(cle)} disabled={n === 0 && !on}
        className="text-[11px] px-2.5 py-1 rounded-full border transition disabled:opacity-35"
        style={{
          borderColor: on ? "var(--accent)" : "var(--border)",
          background: on ? "color-mix(in srgb, var(--accent) 16%, transparent)" : "transparent",
          color: on ? "var(--accent)" : "var(--muted)",
        }}>{texte} <span className="mono">{n}</span></button>;
    })}
  </div>;
}

/** Liste de titres d'actualité, compacte. Le lien s'ouvre chez la SOURCE : on ne
 *  reproduit jamais l'article, on renvoie à lui. */
export function Titres({ items, max = 5 }: { items: any[]; max?: number }) {
  if (!items?.length) return <p className="text-xs text-muted">Aucun titre récent.</p>;
  return <ul className="space-y-1.5">
    {items.slice(0, max).map((h, i) => <li key={i} className="flex gap-2 text-xs leading-snug">
      <span style={{ color: TEINTE(h.score) }}>{FLECHE(h.score)}</span>
      {h.date && <span className="text-muted2 text-[10px] mono shrink-0 pt-px">{String(h.date).slice(5, 10)}</span>}
      {h.link
        ? <a href={h.link} target="_blank" rel="noopener noreferrer" className="hover:underline"
          style={{ color: "var(--accent)" }}>{h.title}</a>
        : <span>{h.title}</span>}
    </li>)}
  </ul>;
}
