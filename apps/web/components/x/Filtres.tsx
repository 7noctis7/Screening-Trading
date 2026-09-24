"use client";
// La barre de filtres. Un principe la gouverne : L'ÉTAT DOIT SE VOIR.
//
// Un filtre actif qu'on a oublié d'avoir posé est la première cause de « le site
// n'affiche plus rien ». Les critères posés sont donc TOUJOURS visibles (le compte
// sélectionné reste allumé, le compteur dit « 12 sur 340 »), et un seul bouton les
// efface tous. Sans cela, l'écran vide et l'écran filtré se ressemblent trait pour trait.
import { basculer, type Criteres } from "./filtrage";

const CHIP = "text-xs px-2.5 py-1.5 rounded-lg border transition-colors";
const ON = "bg-surfaceAlt text-fg border-border2";
const OFF = "text-muted hover:text-fg border-border";

function Chips({ valeurs, choisies, onToggle, libelleTous, onTous }: {
  valeurs: string[]; choisies: string[]; onToggle: (v: string) => void;
  libelleTous: string; onTous: () => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      <button onClick={onTous} className={`${CHIP} ${choisies.length === 0 ? ON : OFF}`}>
        {libelleTous}
      </button>
      {valeurs.map((v) => (
        <button key={v} onClick={() => onToggle(v)}
          className={`${CHIP} ${choisies.includes(v) ? ON : OFF}`}>
          {v}
        </button>
      ))}
    </div>
  );
}

function Select({ label, valeur, options, onChange }: {
  label: string; valeur: string; options: string[]; onChange: (v: string) => void;
}) {
  return (
    <label className="text-xs text-muted2 flex items-center gap-2">
      {label}
      <select value={valeur} onChange={(e) => onChange(e.target.value)}
        className="text-xs px-2 py-1.5 rounded-lg border border-border bg-transparent"
        style={{ background: "var(--surface)" }}>
        <option value="">Tous</option>
        {options.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    </label>
  );
}

export function Filtres({ c, setC, comptes, symboles, classifications, directions,
                          n, total }: {
  c: Criteres; setC: (c: Criteres) => void;
  comptes: string[]; symboles: string[];
  classifications: string[]; directions: string[];
  n: number; total: number;
}) {
  const un = (v: string[]) => (v.length === 1 ? v[0] : "");
  return (
    <section className="card p-4 space-y-3">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-sm uppercase tracking-wide text-muted">Filtrer</h2>
        {/* LE COMPTEUR EST LA RÉPONSE À « pourquoi je ne vois rien ». */}
        <span className="text-[11px] text-muted2 tabular-nums">
          {n} sur {total} publication{total > 1 ? "s" : ""}
        </span>
      </div>

      <input
        value={c.requete}
        onChange={(e) => setC({ ...c, requete: e.target.value })}
        placeholder="Rechercher — BTC, breakout, support, 65000, TP1…"
        aria-label="Rechercher dans les publications"
        className="w-full text-sm px-3 py-2 rounded-lg border border-border"
        style={{ background: "var(--surface)" }} />

      <Chips valeurs={comptes} choisies={c.comptes} libelleTous="Tous les comptes"
        onTous={() => setC({ ...c, comptes: [] })}
        onToggle={(v) => setC({ ...c, comptes: basculer(c.comptes, v) })} />

      <div className="flex flex-wrap gap-3 pt-1">
        <Select label="Type" valeur={un(c.classifications)} options={classifications}
          onChange={(v) => setC({ ...c, classifications: v ? [v] : [] })} />
        <Select label="Sens" valeur={un(c.directions)} options={directions}
          onChange={(v) => setC({ ...c, directions: v ? [v] : [] })} />
        {symboles.length > 0 && (
          <Select label="Actif" valeur={un(c.symboles)} options={symboles}
            onChange={(v) => setC({ ...c, symboles: v ? [v] : [] })} />
        )}
      </div>
    </section>
  );
}
