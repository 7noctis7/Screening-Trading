# Politique de sécurité

## Signaler une vulnérabilité
Ouvre une **issue GitHub** avec le label `security` (repo public — ne PAS inclure de détail
exploitable), ou utilise « Report a vulnerability » (onglet Security → Advisories) pour un
signalement privé. Réponse best-effort sous 72 h.

## Périmètre & posture
- **Aucun secret dans ce dépôt** : clés en variables d'environnement (`.env` local, jamais
  commité) ou secrets chiffrés GitHub Actions. Gate : gitleaks en CI + pre-commit.
- **Paper par défaut** : aucun ordre réel sans `--live --yes` ET clés présentes ; le runner
  CI (`paper.yml`) est paper-only par construction (Alpaca forcé paper, crypto neutralisée).
- **Le trading réel n'utilisera JAMAIS la CI publique** (cf. ADR-0033) : clés réelles = local-only,
  permissions broker minimales (jamais de retrait).
- Données : positions réelles courtier **local-only** ; le site public ne contient que des
  données de marché publiques et le portefeuille modèle.
- `pickle` chargé uniquement via `packages/common/safe_pickle` ; CORS API verrouillé localhost ;
  webhook protégé par jeton.

## Dépendances
`pip-audit` en CI (informatif) + Dependabot hebdomadaire (actions, pip, npm).
