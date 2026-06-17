import "./globals.css";
import { Providers } from "./providers";
import { Nav } from "@/components/Nav";
import { CommandPalette } from "@/components/CommandPalette";
import { ParticlesBg } from "@/components/ParticlesBg";
export const metadata = { title: "Quant Terminal", description: "Screening & trading multi-actifs" };

// Anti-flash : applique le thème mémorisé (sombre par défaut) avant l'hydratation.
const themeInit = `(function(){try{var t=localStorage.getItem('theme');
if(t==='light'){document.documentElement.classList.remove('dark');}
else{document.documentElement.classList.add('dark');}}catch(e){document.documentElement.classList.add('dark');}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr" className="dark" suppressHydrationWarning>
      <head><script dangerouslySetInnerHTML={{ __html: themeInit }} /></head>
      <body className="text-fg antialiased"><ParticlesBg /><Providers><Nav /><CommandPalette />{children}</Providers></body>
    </html>
  );
}
