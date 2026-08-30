// Réglages du fournisseur d'IA — côté NAVIGATEUR uniquement.
//
// Éditer un fichier `.env` puis relancer l'API pour changer de fournisseur est un obstacle réel.
// Ces réglages vivent donc dans le navigateur et voyagent par en-tête à chaque requête.
//
// POURQUOI PAS SUR LE SERVEUR : une clé écrite dans un fichier peut être commitée par erreur.
// Ce dépôt est public. Une clé qu'on n'écrit jamais ne peut pas fuir par ce chemin. Elle n'est
// donc ni persistée côté serveur, ni journalisée, ni renvoyée dans une réponse.
//
// CE QUE ÇA N'EST PAS : une protection contre un script malveillant exécuté sur cette page —
// `localStorage` lui serait lisible. Sur une instance auto-hébergée mono-utilisateur, c'est sans
// objet. Sur une instance exposée à des tiers, ce serait à revoir.

export type ReglagesIA = { base: string; cle: string; modele: string };

const CLE_STOCKAGE = "quant.ia.reglages";

/** Fournisseurs connus. `base` préremplie ; l'utilisateur n'a plus qu'à coller sa clé. */
export const FOURNISSEURS: { id: string; nom: string; base: string; modele: string; aide: string }[] = [
  { id: "local", nom: "Modèle local (LM Studio / Ollama)", base: "http://localhost:1234/v1",
    modele: "", aide: "Aucune clé requise. Lancez LM Studio avec un modèle chargé." },
  { id: "gemini", nom: "Gemini (Google)", base: "https://generativelanguage.googleapis.com/v1beta/openai",
    modele: "",
    aide: "Clé Google AI Studio (AIza…). Laissez le modèle vide pour sélectionner automatiquement un modèle texte actuellement disponible dans votre catalogue Google." },
  { id: "openai", nom: "OpenAI", base: "https://api.openai.com/v1", modele: "gpt-4o-mini",
    aide: "Clé sk-… depuis platform.openai.com." },
  { id: "anthropic", nom: "Anthropic (Claude)", base: "https://api.anthropic.com/v1",
    modele: "claude-sonnet-4-5", aide: "Clé sk-ant-… depuis console.anthropic.com." },
  { id: "mistral", nom: "Mistral", base: "https://api.mistral.ai/v1", modele: "mistral-large-latest",
    aide: "Clé depuis console.mistral.ai." },
];

export const REGLAGES_VIDES: ReglagesIA = { base: "", cle: "", modele: "" };

export function lireReglages(): ReglagesIA {
  // Un navigateur peut refuser le stockage (navigation privée, site data bloqué) : on ne doit
  // jamais casser la page pour ça.
  try {
    const brut = localStorage.getItem(CLE_STOCKAGE);
    if (!brut) return REGLAGES_VIDES;
    const o = JSON.parse(brut);
    return { base: String(o?.base ?? ""), cle: String(o?.cle ?? ""), modele: String(o?.modele ?? "") };
  } catch { return REGLAGES_VIDES; }
}

export function ecrireReglages(r: ReglagesIA): boolean {
  try { localStorage.setItem(CLE_STOCKAGE, JSON.stringify(r)); return true; } catch { return false; }
}

export function effacerReglages(): void {
  try { localStorage.removeItem(CLE_STOCKAGE); } catch { /* rien à faire */ }
}

/** En-têtes à joindre aux appels IA. Un champ vide n'est PAS envoyé : le serveur garde son défaut. */
export function enTetesIA(r?: ReglagesIA): Record<string, string> {
  const g = r ?? lireReglages();
  const h: Record<string, string> = {};
  if (g.base.trim()) h["X-LLM-Base"] = g.base.trim();
  if (g.cle.trim()) h["X-LLM-Key"] = g.cle.trim();
  if (g.modele.trim()) h["X-LLM-Model"] = g.modele.trim();
  return h;
}

/** Masque une clé pour l'affichage : on ne réaffiche jamais un secret en clair. */
export function masquer(cle: string): string {
  const c = cle.trim();
  if (!c) return "";
  return c.length <= 8 ? "••••" : `${c.slice(0, 4)}••••${c.slice(-4)}`;
}
