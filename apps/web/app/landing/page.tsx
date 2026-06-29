// Landing cinématique (hero manifeste + démo, fond 3D R3F). Route isolée → le dashboard
// data-dense reste intact à "/". Le 3D est chargé client-only (compatible export statique).
import type { Metadata } from "next";
import LandingClient from "@/components/landing/LandingClient";

export const metadata: Metadata = {
  title: "Quant Terminal — du risque, maîtrisé",
  description:
    "Screening & trading systématique open-source. DSR≈0 assumé : l'edge prouvé est la "
    + "gestion du risque, pas un alpha. Audité, paper par défaut, 0 €.",
};

export default function LandingPage() {
  return <LandingClient />;
}
