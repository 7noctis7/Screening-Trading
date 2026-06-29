// Page d'accueil = INTRO cinématique (fond 3D R3F, client-only → compatible export statique).
// Le dashboard data-dense vit désormais à /dashboard. Les CTA renvoient vers /accueil (terminal)
// et /dashboard (démo).
import type { Metadata } from "next";
import LandingClient from "@/components/landing/LandingClient";

const TITLE = "Quant Terminal — du risque, maîtrisé";
const DESC =
  "Le seul terminal quant qui publie ses propres limites. Screening multi-actifs, "
  + "risque institutionnel, IA gardée honnête. DSR≈0 assumé, audité, paper par défaut, 0 €.";

export const metadata: Metadata = {
  metadataBase: new URL("https://7noctis7.github.io/Screening-Trading/"),
  title: TITLE,
  description: DESC,
  keywords: ["quant", "trading systématique", "screening", "gestion du risque",
             "backtest", "DSR", "crypto", "open-source"],
  openGraph: {
    title: TITLE, description: DESC, type: "website", locale: "fr_FR",
    siteName: "Quant Terminal",
  },
  twitter: { card: "summary_large_image", title: TITLE, description: DESC },
};

export default function HomePage() {
  return <LandingClient />;
}
