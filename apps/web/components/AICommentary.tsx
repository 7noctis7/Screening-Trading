"use client";
import { useEffect, useState } from "react";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Commentaire IA via un LLM LOCAL (LM Studio / Ollama). N'apparaît que si un serveur local répond.
export function AICommentary() {
  const [status, setStatus] = useState<"checking" | "on" | "off">("checking");
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetch(`${BASE}/api/ai/status`).then((r) => r.json())
      .then((d) => setStatus(d.available ? "on" : "off"))
      .catch(() => setStatus("off"));
  }, []);

  const generate = async () => {
    setLoading(true); setText("");
    try {
      const r = await fetch(`${BASE}/api/ai/commentary`);
      const d = await r.json();
      setText(d.available ? d.text : `IA locale indisponible. ${d.reason ?? ""}`);
    } catch (e: any) {
      setText("Erreur de connexion à l'API.");
    } finally { setLoading(false); }
  };

  if (status === "off") {
    return (
      <div className="card p-4 text-sm text-muted">
        🤖 <b className="text-fg">Commentaire IA (local)</b> — aucun serveur LLM détecté.
        Lance <b>LM Studio</b> (onglet « Local Server », port 1234) avec un modèle chargé, puis recharge la page.
        100 % privé, gratuit, hors-ligne.
      </div>
    );
  }
  return (
    <div className="card p-4">
      <div className="flex items-center justify-between">
        <div className="text-sm"><span style={{ color: "var(--accent2)" }}>🤖</span> <b>Commentaire IA (local)</b>
          {status === "on" && <span className="ml-2 text-xs" style={{ color: "#22c55e" }}>● LM Studio connecté</span>}</div>
        <button onClick={generate} disabled={loading || status !== "on"}
          className="text-xs px-3 py-1.5 rounded-lg border border-border hover:bg-surfaceAlt disabled:opacity-50">
          {loading ? "génération…" : "Générer"}
        </button>
      </div>
      {text && <p className="text-sm text-muted mt-3 whitespace-pre-line font-sans leading-relaxed">{text}</p>}
    </div>
  );
}
