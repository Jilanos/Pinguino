# Pinguino

Atelier local de recherche historique de stratégies sur EURUSD, GBPUSD et USDJPY :
import en lecture seule depuis MetaTrader 5 ou fixtures synthétiques, campagnes bornées,
contrôle de robustesse chronologique et exports auditables. Aucun ordre n'est transmis.

- Installation, lancement et limites : `docs/installation.md`
- Preuves de validation Windows : `docs/windows-validation.md`
- Correspondance des décisions : `docs/decision-register.md`

Lancement rapide sous Windows : `cd backend; uv sync --all-extras`, puis
`cd ..\frontend; npm ci; npx vite build`, puis `cd ..\backend; uv run python -m pinguino`
et ouvrir <http://127.0.0.1:8787/>.

## Workflow Logics

Les documents de suivi du projet se trouvent dans `logics/`.
Les consignes du dépôt sont définies dans `LOGICS.md` et `logics/instructions.md`.

```sh
logics-manager status
logics-manager health
logics-manager lint --require-status
logics-manager audit --group-by-doc
```

Pour ouvrir le navigateur Logics :

```sh
cdx view
```
