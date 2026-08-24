"use client";
import { useEffect, useState } from "react";
import { enTetesIA } from "@/lib/ia";
import { ReglagesIA } from "@/components/ReglagesIA";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Commentaire IA. Le fournisseur est CELUI DE L'UTILISATEUR : modèle local par défaut, ou tout
// service compatible connecté depuis le panneau de réglages — sans éditer `.env` ni relancer
// l'API. La clé reste dans le navigateur et voyage par en-tête (cf. lib/ia.ts).
export function AICommentary() {
  const [status, setStatus] = useState<"checking" | "on" | "off">("checking");
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  // Incrémenté à chaque enregistrement de réglages → re-teste la connexion sans recharger la page.
  const [version, setVersion] = useState(0);

  useEffect(() => {
    setStatus("checking");
    fetch(`${BASE}/api/ai/status`, { headers: enTetesIA() }).then((r) => r.json())
      .then((d) => setStatus(d.available ? "on" : "off"))
      .catch(() => setStatus("off"));
  }, [version]);

  const generate = async () => {
    setLoading(true); setText("");
    try {
      const r = await fetch(`${BASE}/api/ai/commentary`, { headers: enTetesIA() });
      const d = await r.json();
      setText(d.available ? d.text : `IA indisponible. ${d.reason ?? ""}`);
    } catch (e: any) {
      setText("Erreur de connexion à l'API.");
    } finally { setLoading(false); }
  };

  if (status === "off") {
    return (
      <div className="card p-4">
        <div className="text-sm text-muted">
          🤖 <b className="text-fg">Commentaire IA</b> — aucun fournisseur ne répond.
          Deux voies : lancer un modèle <b>local</b> (LM Studio, onglet « Local Server »), ou
          connecter <b>votre propre service</b> ci-dessous — Gemini, OpenAI, Anthropic, Mistral.
        </div>
        <div className="mt-2"><ReglagesIA onChange={() => setVersion((v) => v + 1)} /></div>
      </div>
    );
  }
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <div className="text-sm"><span style={{ color: "var(--accent2)" }}>🤖</span> <b>Commentaire IA</b>
          {status === "on" && <span className="ml-2 text-xs" style={{ color: "#22c55e" }}>● connecté</span>}</div>
        <div className="flex items-center gap-2">
          <ReglagesIA onChange={() => setVersion((v) => v + 1)} />
          <button onClick={generate} disabled={loading || status !== "on"}
            className="text-xs px-3 py-1.5 rounded-lg border border-border hover:bg-surfaceAlt disabled:opacity-50">
            {loading ? "génération…" : "Générer"}
          </button>
        </div>
      </div>
      {text && <p className="text-sm text-muted mt-3 whitespace-pre-line font-sans leading-relaxed">{text}</p>}
    </div>
  );
}
