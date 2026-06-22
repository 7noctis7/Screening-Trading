// Service worker AUTO-DESTRUCTEUR : tue tout ancien SW (ex-terminal interactive.html) qui réclamait
// /sw.js (→ 404) et resservait une version figée. Le front Next.js n'enregistre aucun SW.
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", async () => {
  try {
    await self.registration.unregister();
    const keys = await caches.keys();
    await Promise.all(keys.map((k) => caches.delete(k)));
    const clients = await self.clients.matchAll();
    clients.forEach((c) => c.navigate(c.url));
  } catch (e) { /* best-effort */ }
});
