import "./globals.css";
import { Providers } from "./providers";
import { Nav } from "@/components/Nav";
export const metadata = { title: "Quant Terminal", description: "Screening & trading multi-actifs" };
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr" className="dark">
      <body className="bg-bg text-fg antialiased"><Providers><Nav />{children}</Providers></body>
    </html>
  );
}
