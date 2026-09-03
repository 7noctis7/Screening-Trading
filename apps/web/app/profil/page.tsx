"use client";
import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { PageSkeleton } from "@/components/ui";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const STOCK = "quant.profil";

// PROFIL D'INVESTISSEUR — un questionnaire qui CONTRAINT l'outil, pas qui conseille.
//
// La différence n'est pas rhétorique. Un conseil dit « achetez ceci » ; une contrainte dit
// « vous avez déclaré ne pas supporter plus de 20 % de baisse, l'outil s'y tient ». La seconde
// formulation est aussi la seule qui reste du bon côté de la ligne réglementaire.
//
// Les réponses restent dans CE navigateur. Rien n'est envoyé ni stocké côté serveur : l'API ne
// fait qu'un calcul à partir des paramètres, sans les conserver.

const CLASSES: Record<string, string> = {
  actions_dev: "Actions développées", actions_em: "Actions émergentes",
  obligations: "Obligations", or: "Or", crypto: "Crypto", cash: "Liquidités",
};

type Rep = {
  horizon_annees: number; perte_max_toleree: number; part_du_patrimoine: number;
  besoin_liquidite: number; revenus_stables: boolean; experience_annees: number;
};

const DEFAUT: Rep = {
  horizon_annees: 10, perte_max_toleree: 0.25, part_du_patrimoine: 0.5,
  besoin_liquidite: 0, revenus_stables: true, experience_annees: 2,
};

function Curseur({ label, aide, valeur, min, max, pas, fmt, onChange }: {
  label: string; aide: string; valeur: number; min: number; max: number; pas: number;
  fmt: (v: number) => string; onChange: (v: number) => void;
}) {
  return (
    <div className="card p-4">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-sm font-medium">{label}</span>
        <span className="mono text-sm" style={{ color: "var(--accent)" }}>{fmt(valeur)}</span>
      </div>
      <input type="range" min={min} max={max} step={pas} value={valeur}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full mt-2" aria-label={label} />
      <p className="text-muted2 text-[11px] mt-1">{aide}</p>
    </div>
  );
}

function Barre({ poids }: { poids: Record<string, number> }) {
  const entries = Object.entries(poids).filter(([, v]) => v > 0.001)
    .sort((a, b) => b[1] - a[1]);
  return (
    <div>
      {/* Barre empilée : un écart de 2 pt entre segments les sépare sans grille ni légende
          colorée — l'identité est portée par le libellé, jamais par la couleur seule. */}
      <div className="flex gap-[2px] h-3 rounded overflow-hidden mt-1">
        {entries.map(([k, v], i) => (
          <div key={k} title={`${CLASSES[k] ?? k} ${(v * 100).toFixed(1)} %`}
            style={{ width: `${v * 100}%`, background: "var(--accent)", opacity: 1 - i * 0.13 }} />
        ))}
      </div>
      <table className="w-full text-sm mt-3">
        <tbody className="mono">
          {entries.map(([k, v]) => (
            <tr key={k} className="border-t border-border">
              <td className="py-1 font-sans">{CLASSES[k] ?? k}</td>
              <td className="text-right">{(v * 100).toFixed(1)} %</td>
            </tr>))}
        </tbody>
      </table>
    </div>
  );
}

export default function ProfilPage() {
  const [rep, setRep] = useState<Rep>(DEFAUT);
  const [res, setRes] = useState<any>(null);
  const [err, setErr] = useState("");
  // ON N'ÉCRIT PAS AVANT D'AVOIR LU. Signalé le 03/09 : « je le règle, je navigue, je
  // reviens, et mes réponses sont réinitialisées ». L'effet d'écriture partait au
  // MONTAGE, donc avec les valeurs par DÉFAUT — l'état restauré n'étant pas encore
  // appliqué — et écrasait le stockage avant que la restauration ne s'y réécrive. Entre
  // ces deux instants, quitter la page suffisait à perdre le réglage. Ce drapeau
  // supprime la course : tant que la lecture n'a pas eu lieu, rien n'est écrit.
  const [lu, setLu] = useState(false);

  useEffect(() => {
    try { const b = localStorage.getItem(STOCK); if (b) setRep({ ...DEFAUT, ...JSON.parse(b) }); }
    catch { /* stockage refusé : on garde les valeurs par défaut */ }
    setLu(true);
  }, []);

  const q = useMemo(() => new URLSearchParams({
    horizon_annees: String(rep.horizon_annees),
    perte_max_toleree: String(rep.perte_max_toleree),
    part_du_patrimoine: String(rep.part_du_patrimoine),
    besoin_liquidite: String(rep.besoin_liquidite),
    revenus_stables: String(rep.revenus_stables),
    experience_annees: String(rep.experience_annees),
  }).toString(), [rep]);

  useEffect(() => {
    if (!lu) return;                       // cf. ci-dessus : jamais avant la lecture
    try { localStorage.setItem(STOCK, JSON.stringify(rep)); } catch { /* sans effet */ }
  }, [rep, lu]);

  useEffect(() => {
    let vivant = true;
    fetch(`${BASE}/api/profil?${q}`).then((r) => r.json())
      .then((d) => { if (vivant) { setRes(d); setErr(""); } })
      .catch(() => { if (vivant) setErr("L'API ne répond pas. Est-elle lancée (make start) ?"); });
    return () => { vivant = false; };
  }, [q]);

  const maj = (k: keyof Rep, v: number | boolean) => setRep((r) => ({ ...r, [k]: v }));
  const pct = (x: number) => `${(x * 100).toFixed(0)} %`;

  return (
    <main className="max-w-4xl mx-auto p-6 space-y-5">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Mon profil d'investisseur</h1>
        <p className="text-muted text-xs mt-1">
          Cette page calcule, à partir de ce que vous déclarez accepter, l'<b>allocation de
          politique</b> que votre situation autorise. Elle ne constitue pas une recommandation
          personnalisée. Tout reste dans ce navigateur — rien n'est envoyé ni conservé.
        </p>
        <p className="text-muted2 text-[11px] mt-2">
          <b>Ce que ces réponses ne font PAS encore.</b> Elles ne contraignent aujourd'hui aucun
          autre écran ni la chaîne d'exécution : le screener, le dimensionnement et le
          rebalancement paper ne les lisent pas. C'est un calcul de référence — à comparer
          vous-même à ce que le portefeuille fait réellement. Le câblage est au backlog ;
          d'ici là, écrire l'inverse serait une promesse que le code ne tient pas.
        </p>
      </div>

      <section className="grid gap-3 md:grid-cols-2">
        <Curseur label="Horizon" aide="Dans combien d'années aurez-vous besoin de cet argent ? C'est le paramètre qui pèse le plus : une baisse n'est une perte que si l'on doit vendre avant qu'elle se résorbe."
          valeur={rep.horizon_annees} min={1} max={40} pas={1}
          fmt={(v) => `${v} an${v > 1 ? "s" : ""}`} onChange={(v) => maj("horizon_annees", v)} />
        <Curseur label="Baisse maximale acceptée" aide="Quelle chute temporaire pourriez-vous traverser sans vendre ? Soyez honnête : c'est ce chiffre qui décide de tout le reste."
          valeur={rep.perte_max_toleree} min={0.05} max={0.6} pas={0.01}
          fmt={pct} onChange={(v) => maj("perte_max_toleree", v)} />
        <Curseur label="Part de votre patrimoine" aide="Quelle fraction de ce que vous possédez est investie ici ? Investir l'essentiel réduit votre capacité : il n'y a plus de matelas ailleurs."
          valeur={rep.part_du_patrimoine} min={0.05} max={1} pas={0.05}
          fmt={pct} onChange={(v) => maj("part_du_patrimoine", v)} />
        <Curseur label="Besoin de retirer avant l'horizon" aide="Devrez-vous prélever une partie du capital en cours de route ? Cela raccourcit l'horizon effectif, quelle que soit la date cible."
          valeur={rep.besoin_liquidite} min={0} max={1} pas={0.05}
          fmt={pct} onChange={(v) => maj("besoin_liquidite", v)} />
        <Curseur label="Expérience des marchés" aide="Depuis combien d'années investissez-vous ? Module à la marge, jamais au-delà de ce que vous déclarez accepter."
          valeur={rep.experience_annees} min={0} max={30} pas={1}
          fmt={(v) => `${v} an${v > 1 ? "s" : ""}`} onChange={(v) => maj("experience_annees", v)} />
        <div className="card p-4">
          <span className="text-sm font-medium">Revenus stables</span>
          <div className="flex gap-2 mt-2">
            {[true, false].map((b) => (
              <button key={String(b)} onClick={() => maj("revenus_stables", b)}
                className="text-xs px-3 py-1.5 rounded-md border transition-colors"
                style={{ borderColor: rep.revenus_stables === b ? "var(--accent)" : "var(--border)",
                         color: rep.revenus_stables === b ? "var(--accent)" : "var(--muted)" }}>
                {b ? "Oui" : "Non"}
              </button>))}
          </div>
          <p className="text-muted2 text-[11px] mt-2">
            Sans revenus stables, une baisse peut forcer à vendre au pire moment.
          </p>
        </div>
      </section>

      {err && <p className="card p-4 text-sm" style={{ color: "var(--warn)" }}>{err}</p>}
      {!res && !err && <PageSkeleton />}

      {res?.available && (
        <>
          <section className="card p-5">
            <h2 className="text-sm uppercase tracking-wide text-muted">Ce qui vous lie</h2>
            <p className="text-sm mt-2">{res.risque.explication}</p>
            <div className="grid grid-cols-3 gap-3 mt-3 text-sm">
              <div><div className="text-muted text-[11px]">Ce que vous POUVEZ porter</div>
                <div className="mono text-lg">{(res.risque.capacite * 100).toFixed(0)}</div></div>
              <div><div className="text-muted text-[11px]">Ce que vous DITES accepter</div>
                <div className="mono text-lg">{(res.risque.tolerance * 100).toFixed(0)}</div></div>
              <div><div className="text-muted text-[11px]">Retenu (le plus petit)</div>
                <div className="mono text-lg" style={{ color: "var(--accent)" }}>
                  {(res.risque.niveau * 100).toFixed(0)}</div></div>
            </div>
            <p className="text-muted2 text-[11px] mt-3">
              Capacité et tolérance sont deux choses différentes, et c'est la plus petite qui lie.
              Les fondre en un « score de risque » unique autoriserait un investisseur audacieux à
              deux ans d'horizon à prendre un risque que son horizon ne permet pas.
            </p>
          </section>

          <section className="card p-5">
            <div className="flex items-baseline justify-between flex-wrap gap-2">
              <h2 className="text-sm uppercase tracking-wide text-muted">Allocation de politique</h2>
              <span className="mono text-sm">
                budget de perte {(res.budget_perte * 100).toFixed(0)} %
                <span className="text-muted2"> · estimée {(res.strategique.perte_estimee * 100).toFixed(0)} %</span>
              </span>
            </div>
            <Barre poids={res.strategique.poids} />
            <p className="text-muted text-xs mt-3">{res.strategique.note}</p>
            <p className="text-muted2 text-[11px] mt-1">
              L'allocation est <b>vérifiée</b> contre son propre budget, pas seulement promise :
              une allocation 100 % actions ne peut pas tenir −15 %, les actions développées ont
              fait −55 % en 2008. Si les poids indicatifs dépassaient votre budget, ils ont été
              réduits vers les liquidités.
            </p>
          </section>

          <section className="card p-5">
            <h2 className="text-sm uppercase tracking-wide text-muted">Inclinaison selon le contexte</h2>
            {res.tactique?.applique ? (
              <>
                <p className="text-sm mt-2">{res.tactique.note}</p>
                <div className="flex flex-wrap gap-1.5 mt-3">
                  {Object.entries(res.tactique.inclinaisons as Record<string, number>)
                    .filter(([, v]) => Math.abs(v) > 0.0005)
                    .map(([k, v]) => (
                      <span key={k} className="text-xs px-2 py-0.5 rounded-full border border-border mono">
                        {CLASSES[k] ?? k} {v >= 0 ? "+" : ""}{(v * 100).toFixed(1)} pt
                      </span>))}
                </div>
              </>
            ) : (
              <p className="text-sm mt-2">{res.tactique?.note ?? "Aucune inclinaison."}</p>
            )}
            <p className="text-muted2 text-[11px] mt-3">
              L'amplitude suit la force de la <b>preuve</b>, jamais celle du signal. Ce site publie
              un Sharpe déflaté proche de zéro — aucun alpha directionnel démontré : incliner
              fortement sur cette base contredirait ce qu'il affiche par ailleurs.
              {res.tactique?.preuve?.motif && (
                <> Ici : {res.tactique.preuve.motif}.</>
              )}
            </p>
          </section>

          <p className="text-muted2 text-xs">
            ⚠️ {res.avertissement} <Link href="/methode" className="text-accent">Voir la méthode →</Link>
          </p>
        </>
      )}
    </main>
  );
}
