// Page d'accueil = INTRO cinématique (fond 3D R3F, client-only → compatible export statique).
// Le dashboard data-dense vit désormais à /dashboard. Les CTA renvoient vers /accueil (terminal)
// et /dashboard (démo).
import type { Metadata } from "next";
import LandingClient from "@/components/landing/LandingClient";

export const metadata: Metadata = {
  title: "Quant Terminal — du risque, maîtrisé",
  description:
    "Screening & trading systématique open-source. DSR≈0 assumé : l'edge prouvé est la "
    + "gestion du risque, pas un alpha. Audité, paper par défaut, 0 €.",
};

export default function HomePage() {
  return <LandingClient />;
}
