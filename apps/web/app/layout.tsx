import "./globals.css";
import { Providers } from "./providers";
import { Nav } from "@/components/Nav";
import { CommandPalette } from "@/components/CommandPalette";
import { ParticlesBg } from "@/components/ParticlesBg";
export const metadata = {
  title: "Quant Terminal",
  description: "Screening & trading multi-actifs",
  appleWebApp: { capable: true, statusBarStyle: "black-translucent", title: "Quant Terminal" },
};

// viewport-fit=cover → on peut gérer les encoches iPhone (safe-area-inset). themeColor = barre Safari.
export const viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover" as const,
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#0a1118" },
    { media: "(prefers-color-scheme: light)", color: "#f4f7f8" },
  ],
};

// Anti-flash : applique le thème mémorisé (sombre par défaut) avant l'hydratation.
const themeInit = `(function(){try{var t=localStorage.getItem('theme');
if(t==='light'){document.documentElement.classList.remove('dark');}
else{document.documentElement.classList.add('dark');}}catch(e){document.documentElement.classList.add('dark');}})();`;

// Purge tout ANCIEN service worker (ex-terminal autonome interactive.html) + ses caches → évite de
// resservir une « ancienne version » figée. Le front Next.js n'enregistre aucun SW.
const swCleanup = `(function(){try{if('serviceWorker' in navigator){
navigator.serviceWorker.getRegistrations().then(function(rs){rs.forEach(function(r){r.unregister();});});}
if(window.caches&&caches.keys){caches.keys().then(function(ks){ks.forEach(function(k){caches.delete(k);});});}}catch(e){}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr" className="dark" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInit }} />
        <script dangerouslySetInnerHTML={{ __html: swCleanup }} />
      </head>
      <body className="text-fg antialiased"><ParticlesBg /><Providers><Nav /><CommandPalette />{children}</Providers></body>
    </html>
  );
}
