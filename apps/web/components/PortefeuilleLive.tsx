"use client";
import { useEffect, useState } from "react";
import { usePortefeuille } from "@/lib/api";

// LE PORTEFEUILLE À LA SECONDE, À CÔTÉ DU RESTE DE LA PAGE — et la distinction est dite.
//
// Le bandeau du site annonce « LIVE · il y a 15min ». Ces quinze minutes ne sont pas un
// retard de la donnée : c'est la période de reconstruction du snapshot. Celui-ci mélange
// deux rythmes — un screening sur barres QUOTIDIENNES (sa fenêtre s'arrête à minuit) et un
// portefeuille qui bouge à chaque seconde de séance. Raccourcir le TTL aurait payé un
// recalcul complet du premier pour rafraîchir le second.
//
// Ce bloc lit donc `/api/portefeuille`, qui interroge le courtier directement (deux appels,
// aucun snapshot). Le reste de la page continue de décrire la CIBLE du modèle, qui n'a
// aucune raison de changer en cours de séance. Les deux natures sont étiquetées.

const VERT = "#22c55e";
const AMBRE = "#f59e0b";
const ROUGE = "#ef4444";

const usd = (x?: number | null) =>
  x == null ? "—" : `${x.toLocaleString("fr-FR", { maximumFractionDigits: 2 })} $`;

function libelle(s: number): string {
  return s < 60 ? `il y a ${s}s` : `il y a ${Math.round(s / 60)}min`;
}

export function PortefeuilleLive() {
  const { data, dataUpdatedAt, isFetching } = usePortefeuille();
  const [, tick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => tick((x) => x + 1), 1000);
    return () => clearInterval(id);
  }, []);

  if (!data) return null;
  if (!data.disponible) {
    return (
      <div className="rounded-lg border border-border px-3 py-2 text-xs text-muted">
        Portefeuille courtier indisponible — {(data.incidents ?? []).join(" · ") || "aucun courtier configuré"}.
      </div>
    );
  }

  // Âge au moment de la réponse + temps écoulé depuis : aucune horloge partagée requise
  // (le navigateur n'a pas à croire la sienne, qui dérive).
  const secs = Math.max(
    0,
    Math.round((data.age_s ?? 0) + (dataUpdatedAt ? (Date.now() - dataUpdatedAt) / 1000 : 0)),
  );
  const seuil = (data.fraicheur_s ?? 20) + 45;   // une réponse + un cycle de sondage
  const couleur = !data.complet ? AMBRE : secs > seuil * 2 ? ROUGE : secs > seuil ? AMBRE : VERT;
  const latent = data.latent_total as number | null;

  return (
    <div className="rounded-lg border border-border px-3 py-2.5 flex flex-wrap items-center gap-x-5 gap-y-1.5">
      <span className="inline-flex items-center gap-1.5 text-[11px] text-muted">
        <span className="inline-block w-1.5 h-1.5 rounded-full"
              style={{ background: couleur, boxShadow: `0 0 8px ${couleur}` }} />
        COURTIER <span className="text-muted2">{isFetching ? "maj…" : libelle(secs)}</span>
      </span>
      <span className="text-sm">
        <span className="text-muted text-xs">valeur du compte </span>
        <span className="font-semibold tabular-nums">{usd(data.equity_total)}</span>
      </span>
      <span className="text-sm">
        <span className="text-muted text-xs">latent </span>
        <span className="font-semibold tabular-nums"
              style={{ color: latent == null ? undefined : latent >= 0 ? VERT : ROUGE }}>
          {latent == null ? "—" : `${latent >= 0 ? "+" : "−"}${usd(Math.abs(latent))}`}
        </span>
      </span>
      <span className="text-sm">
        <span className="text-muted text-xs">lignes </span>
        <span className="font-semibold tabular-nums">{data.n_positions}</span>
      </span>
      {/* ABSENT N'EST PAS ZÉRO : un total partiel ne se présente jamais comme un total. */}
      {!data.complet && (
        <span className="text-[11px]" style={{ color: AMBRE }}>
          ⚠ total INCOMPLET — {(data.incidents ?? []).join(" · ")}
        </span>
      )}
      {(data.sans_valeur ?? []).length > 0 && (
        <span className="text-[11px] text-muted">
          {data.sans_valeur.length} ligne(s) non chiffrée(s) par le courtier, exclue(s) du total :{" "}
          {data.sans_valeur.slice(0, 6).join(", ")}
        </span>
      )}
      <span className="text-[11px] text-muted2 basis-full">
        Lu chez le courtier toutes les 30 s. Le reste de la page décrit la CIBLE du modèle,
        recalculée avec le snapshot — elle n'a pas de raison de bouger en cours de séance.
      </span>
    </div>
  );
}
