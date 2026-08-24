"use client";
import { useEffect, useState } from "react";
import {
  effacerReglages, ecrireReglages, enTetesIA, FOURNISSEURS, lireReglages, masquer,
  type ReglagesIA as TReglages,
} from "@/lib/ia";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Panneau de connexion du fournisseur d'IA, directement dans le site.
//
// Il remplace l'édition manuelle de `.env` suivie d'un redémarrage de l'API — un obstacle qui
// suffisait à décourager. La clé reste dans le navigateur et voyage par en-tête ; elle n'est
// jamais écrite côté serveur (cf. lib/ia.ts pour le raisonnement complet).
//
// Le bouton « Tester » est le cœur de l'ergonomie : sans lui, une erreur de clé ou d'URL se
// manifeste par un « indisponible » muet, et l'utilisateur ne sait pas lequel des deux corriger.
export function ReglagesIA({ onChange }: { onChange?: () => void }) {
  const [r, setR] = useState<TReglages>({ base: "", cle: "", modele: "" });
  const [ouvert, setOuvert] = useState(false);
  const [test, setTest] = useState<null | { ok: boolean; motif: string; modeles: string[] }>(null);
  const [enCours, setEnCours] = useState(false);
  const [enregistre, setEnregistre] = useState<boolean | null>(null);

  useEffect(() => { setR(lireReglages()); }, []);

  const choisir = (id: string) => {
    const f = FOURNISSEURS.find((x) => x.id === id);
    if (f) { setR((v) => ({ ...v, base: f.base, modele: f.modele })); setTest(null); }
  };

  const tester = async () => {
    setEnCours(true); setTest(null);
    try {
      const rep = await fetch(`${BASE}/api/ai/diagnostic`, { headers: enTetesIA(r) });
      const d = await rep.json();
      setTest({ ok: !!d.ok, motif: d.motif ?? "", modeles: d.modeles ?? [] });
    } catch {
      setTest({ ok: false, motif: "L'API du terminal ne répond pas. Est-elle lancée (make start) ?", modeles: [] });
    } finally { setEnCours(false); }
  };

  const enregistrer = () => {
    const ok = ecrireReglages(r);
    setEnregistre(ok);
    onChange?.();
  };

  const oublier = () => {
    effacerReglages(); setR({ base: "", cle: "", modele: "" }); setTest(null); setEnregistre(null);
    onChange?.();
  };

  const fournisseurActuel = FOURNISSEURS.find((f) => f.base === r.base);

  if (!ouvert) {
    return (
      <button onClick={() => setOuvert(true)}
        className="text-xs px-2 py-0.5 rounded-md border border-border hover:bg-surfaceAlt transition-colors">
        {r.cle || r.base ? `IA : ${fournisseurActuel?.nom ?? "personnalisé"}` : "Connecter mon IA"}
      </button>
    );
  }

  return (
    <section className="card p-4 mt-3">
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-sm uppercase tracking-wide text-muted">Connecter mon IA</h3>
        <button onClick={() => setOuvert(false)} className="text-muted2 hover:text-fg text-lg leading-none"
          aria-label="Fermer">×</button>
      </div>
      <p className="text-muted2 text-xs mt-1">
        Votre clé reste <b>dans ce navigateur</b> et voyage par en-tête à chaque requête. Elle
        n'est jamais écrite sur le serveur ni journalisée — sur une instance auto-hébergée, elle
        ne quitte pas votre machine.
      </p>

      <div className="grid gap-3 md:grid-cols-2 mt-3">
        <label className="text-xs text-muted">Fournisseur
          <select onChange={(e) => choisir(e.target.value)} value={fournisseurActuel?.id ?? ""}
            className="mt-1 w-full rounded-md border border-border px-2 py-1.5 text-sm text-fg"
            style={{ background: "var(--surface)" }}>
            <option value="">— choisir —</option>
            {FOURNISSEURS.map((f) => <option key={f.id} value={f.id}>{f.nom}</option>)}
          </select>
        </label>
        <label className="text-xs text-muted">Modèle
          <input value={r.modele} onChange={(e) => { setR({ ...r, modele: e.target.value }); setTest(null); }}
            placeholder="laisser vide = détection automatique"
            className="mt-1 w-full rounded-md border border-border px-2 py-1.5 text-sm mono text-fg"
            style={{ background: "var(--surface)" }} />
        </label>
        <label className="text-xs text-muted md:col-span-2">Adresse (URL de base)
          <input value={r.base} onChange={(e) => { setR({ ...r, base: e.target.value }); setTest(null); }}
            placeholder="http://localhost:1234/v1"
            className="mt-1 w-full rounded-md border border-border px-2 py-1.5 text-sm mono text-fg"
            style={{ background: "var(--surface)" }} />
        </label>
        <label className="text-xs text-muted md:col-span-2">Clé API
          <input type="password" value={r.cle} autoComplete="off"
            onChange={(e) => { setR({ ...r, cle: e.target.value }); setTest(null); }}
            placeholder="vide pour un modèle local"
            className="mt-1 w-full rounded-md border border-border px-2 py-1.5 text-sm mono text-fg"
            style={{ background: "var(--surface)" }} />
        </label>
      </div>

      {fournisseurActuel?.aide && (
        <p className="text-muted2 text-[11px] mt-2">{fournisseurActuel.aide}</p>
      )}

      <div className="flex flex-wrap items-center gap-2 mt-3">
        <button onClick={tester} disabled={enCours}
          className="text-xs px-2.5 py-1 rounded-md border border-border hover:bg-surfaceAlt transition-colors disabled:opacity-50">
          {enCours ? "Test en cours…" : "Tester la connexion"}
        </button>
        <button onClick={enregistrer}
          className="text-xs px-2.5 py-1 rounded-md border border-border hover:bg-surfaceAlt transition-colors">
          Enregistrer
        </button>
        {(r.cle || r.base) && (
          <button onClick={oublier}
            className="text-xs px-2.5 py-1 rounded-md border border-border hover:bg-surfaceAlt transition-colors"
            style={{ color: "var(--warn)" }}>Oublier ma clé</button>
        )}
        {r.cle && <span className="text-[11px] text-muted2 mono">clé {masquer(r.cle)}</span>}
      </div>

      {enregistre === false && (
        <p className="text-[11px] mt-2" style={{ color: "var(--warn)" }}>
          Ce navigateur refuse le stockage local (navigation privée ?). Les réglages
          fonctionneront pour cette page, mais seront perdus au rechargement.
        </p>
      )}

      {test && (
        <div className="mt-3 text-xs p-2.5 rounded-md border"
          style={{ borderColor: test.ok ? "var(--pos)" : "var(--warn)" }}>
          <b style={{ color: test.ok ? "var(--pos)" : "var(--warn)" }}>
            {test.ok ? "Connexion établie" : "Connexion impossible"}
          </b>
          {test.motif && <span className="text-muted"> — {test.motif}</span>}
          {test.ok && test.modeles.length > 0 && (
            <div className="text-muted2 mt-1">
              Modèles disponibles : <span className="mono">{test.modeles.slice(0, 6).join(", ")}</span>
              {test.modeles.length > 6 && ` … (+${test.modeles.length - 6})`}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
