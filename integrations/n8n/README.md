# n8n — TradingView → Risk Engine (#9)

Flux **event-driven gratuit** : une alerte TradingView arrive sur n8n (self-host), qui la
re-poste, **signée** (`X-Webhook-Token`), vers l'API `POST /api/tv/webhook`. L'API dépose
l'alerte pour le **veto du risk-engine** (aucun ordre n'est passé — 100 % défensif).

```
TradingView (alerte)  →  n8n (webhook)  →  POST /api/tv/webhook (X-Webhook-Token)  →  risk-engine
```

## Mise en route
1. **API lancée avec un token** (même valeur partout) :
   ```bash
   export QUANT_WEBHOOK_TOKEN="une-chaine-aleatoire-longue"
   make api                              # http://127.0.0.1:8000
   ```
2. **n8n** (avec le même token dans son environnement) :
   ```bash
   QUANT_WEBHOOK_TOKEN="$QUANT_WEBHOOK_TOKEN" npx n8n   # http://localhost:5678
   ```
3. **Importer le workflow** : n8n → Workflows → **Import from File** → `integrations/n8n/tradingview-to-risk.json`.
4. **Activer** le workflow (toggle en haut à droite) → copie l'**URL de Production** du nœud
   *TradingView Alert* (ex. `http://localhost:5678/webhook/tradingview`).
5. **TradingView** → alerte → *Notifications* → **Webhook URL** = l'URL n8n. Message = JSON, ex. :
   ```json
   { "symbol": "{{ticker}}", "action": "{{strategy.order.action}}", "price": {{close}} }
   ```

## Test sans TradingView
```bash
curl -X POST http://localhost:5678/webhook/tradingview \
  -H 'Content-Type: application/json' \
  -d '{"symbol":"AAPL","action":"sell","price":210.5}'
# → doit apparaître côté API (alerte déposée pour le veto)
```

## Notes
- n8n lancé via `npx` (natif) → l'API est sur `127.0.0.1:8000`. En **Docker**, remplacer par
  `http://host.docker.internal:8000` dans le nœud HTTP Request.
- Le webhook API n'exécute **aucun ordre** : il enregistre une alerte (lecture pour le risk-engine).
- Sans `QUANT_WEBHOOK_TOKEN` côté API, l'endpoint n'accepte que localhost (cf. durcissement sécurité).
