// Export statique pour GitHub Pages (parité avec `make start`). En dev local, rien ne change :
// `next dev` ignore `output:'export'`. En CI, on injecte STATIC_EXPORT + NEXT_PUBLIC_BASE_PATH.
const isExport = process.env.STATIC_EXPORT === "1";
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || "";

const nextConfig = {
  ...(isExport ? { output: "export" } : {}),
  basePath: basePath || undefined,
  assetPrefix: basePath || undefined,
  images: { unoptimized: true },        // pas d'optimiseur serveur en statique
  trailingSlash: true,                  // GitHub Pages sert mieux /route/ que /route
  eslint: { ignoreDuringBuilds: true },
  typescript: { ignoreBuildErrors: true },
};
export default nextConfig;
