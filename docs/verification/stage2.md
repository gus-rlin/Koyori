# Vérification de l'étape 2

Code de mémoire et connecteurs contrôlés, vérifié le **2026-10-06**. **149 tests réussis, aucune exclusion**, dont 14 intégrations DynamoDB Local ; Ruff, format et contrôle du diff réussis. Image Linux, bundle Lambda et template CDK reconstruits après les corrections de la PR #2 ; les deux nouvelles recettes Docker produisent **PASS**. Audit runtime : aucune vulnérabilité connue. [Revue indépendante : 9,4/10](stage2-review.md), aucun constat confirmé restant. [Empreintes et résultats](artifact-evidence.json).

| Garantie | Preuve |
| --- | --- |
| Confidentialité, corrections/effacement, index ancien/concurrent, dates DST et sources | `tests/test_stage2_memory.py`, API et identité du socle |
| PATCH partiel, clé expirée remplaçable, courses de renouvellement et suppression ancienne | `tests/test_stage2_memory.py`, `tests/test_stage2_integration.py` ; les deux ordres de course sur DynamoDB Local |
| Budget concurrent, devis/approbation exacts, rollback | `tests/test_stage2_actions.py`, `tests/test_stage2_integration.py` |
| Réponse perdue après commit, révocation, génération, modification et annulation | Même tests, fournisseur persistant explicitement simulé |
| OAuth, chiffrement, scopes, refresh révoqué, sync et push | `tests/test_stage2_calendar.py`, fournisseur fictif et HTTP MockTransport |
| Titan 512, filtres S3, effets tardifs, réparation après arrêt, quotas et backoff | `tests/test_stage2_semantic_adapters.py`, doubles explicites et client Botocore intercepté |
| Purge à expiration, expiration pendant put, vecteurs legacy et reprise sans quota d'embedding | `tests/test_stage2_memory.py`, `tests/test_stage2_semantic_adapters.py` ; fournisseurs explicitement factices |
| Empreinte source portable LF/CRLF, tri POSIX et rejet d'une preuve devenue périmée | `tests/test_evidence.py`, contrôle `--check-source` exécuté en CI avant les builds |
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
uv run python scripts/record_evidence.py --check-source
```

La recette stage 2 arrête les workers, enregistre une commande simulée, tue un processus vivant après commit fournisseur avant reçu, redémarre stockage/API puis rapproche la même opération avec sa réservation. Elle laisse les services du projet démarrés. Les rapports sous `artifacts/` restent hors Git, sans jetons ni contenu d'agenda.

L'empreinte source concatène, dans l'ordre lexicographique sensible à la casse des chemins relatifs POSIX, chaque chemin UTF-8, un octet NUL et le contenu texte dont CRLF devient LF. Le périmètre est donné par `source_paths()` dans `scripts/record_evidence.py` ; il exclut les preuves elles-mêmes et le journal. Les hashes du bundle binaire portent sur ses octets exacts. `--check-source` compare la preuve publiée au checkout sans la régénérer ; la CI l'exécute avant les builds pour détecter une preuve périmée. La convention précédente et sa correction factuelle sont conservées dans JRN-016.

Google/Titan/S3 Vectors réels restent à qualifier : [configuration et contrôles externes](../stage2.md). Aucun commerce réel, coordinateur, canal vocal ou MCP n'est annoncé. La synthèse ne démontre ni IAM exécuté ni coûts facturés.
