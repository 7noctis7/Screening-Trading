// Le nom de la place crypto vient des DONNÉES, plus du code.
//
// « Bitmart » était écrit en dur dans six pages. Changer de place obligeait à les retrouver
// toutes — avec la certitude d'en oublier une, qui afficherait alors un nom faux à côté de
// chiffres justes. Le back publie désormais la place active (`accounts.crypto.name`) ; le front
// se contente de la lire.

export const VENUE_DEFAUT = "Binance";

/** Nom affichable de la place crypto active. `accounts` = payload `/api/positions`. */
export function nomVenue(accounts?: any): string {
  return accounts?.crypto?.name || accounts?.bitmart?.name || VENUE_DEFAUT;
}

/** Bloc du compte crypto, quelle que soit la place (clé neuve, alias historique). */
export function compteCrypto(accounts?: any): any {
  return accounts?.crypto ?? accounts?.bitmart ?? null;
}

/** Variables d'environnement attendues par la place active, pour les messages d'aide. */
export function envVenue(accounts?: any): string[] {
  const c = compteCrypto(accounts);
  return Array.isArray(c?.env) && c.env.length
    ? c.env : ["BINANCE_API_KEY", "BINANCE_API_SECRET"];
}
