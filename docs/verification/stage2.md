# Vérification de l'étape 2

Code de mémoire et connecteurs contrôlés, vérifié le **2026-10-06**. **135 tests réussis, aucune exclusion** ; Ruff, format et contrôle du diff réussis. Image Linux, bundle Lambda et template CDK reconstruits. Les deux recettes de reprise ont produit **PASS**, dont arrêt d'un processus vivant après le commit fournisseur, redémarrage stockage/API et rapprochement de la même opération. Audit runtime : aucune vulnérabilité connue. [Revue indépendante finale : 9,3/10](stage2-review.md), aucun constat confirmé restant. [Empreintes et résultats](artifact-evidence.json).

| Garantie | Preuve |
| --- | --- |
| Confidentialité, corrections/effacement, index ancien/concurrent, dates DST et sources | `tests/test_stage2_memory.py`, API et identité du socle |
| Budget concurrent, devis/approbation exacts, rollback | `tests/test_stage2_actions.py`, `tests/test_stage2_integration.py` |
| Réponse perdue après commit, révocation, génération, modification et annulation | Même tests, fournisseur persistant explicitement simulé |
| OAuth, chiffrement, scopes, refresh révoqué, sync et push | `tests/test_stage2_calendar.py`, fournisseur fictif et HTTP MockTransport |
| Titan 512, filtres S3, effets tardifs, réparation après arrêt, quotas et backoff | `tests/test_stage2_semantic_adapters.py`, doubles explicites et client Botocore intercepté |
| Transactions effectives et reprise du registre | DynamoDB Local avec `KOYORI_INTEGRATION=1` |
| Tables, IAM, KMS, S3 Vectors et rôles préparés | `tests/test_infrastructure.py`, template synthétisé sans compte |

```powershell
docker compose up -d --build
uv run python scripts/build_lambda.py
uv run python -m infrastructure.app
$env:KOYORI_INTEGRATION = '1'
uv run pytest -q --junitxml=artifacts/all-tests.xml
uv run ruff check src tests scripts infrastructure
uv run ruff format --check src tests scripts infrastructure
uv run python scripts/verify_local.py
uv run python scripts/verify_stage2.py
uv run pip-audit --path artifacts/lambda --format cyclonedx-json --output artifacts/runtime-sbom.json
uv run python scripts/record_evidence.py
```

La recette stage 2 arrête les workers, enregistre une commande simulée, tue un processus vivant après commit fournisseur avant reçu, redémarre stockage/API puis rapproche la même opération avec sa réservation. Elle laisse les services du projet démarrés. Les rapports sous `artifacts/` restent hors Git, sans jetons ni contenu d'agenda.

Google/Titan/S3 Vectors réels restent à qualifier : [configuration et contrôles externes](../stage2.md). Aucun commerce réel, coordinateur, canal vocal ou MCP n'est annoncé. La synthèse ne démontre ni IAM exécuté ni coûts facturés.
