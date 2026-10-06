# Koyori — coordination durable de la maison

Le socle exécute une commande synthétique durable, avec identité signée, autorisations par objet, transactions, reprise après crash et activité persistante. Le même code Python sert l'API HTTP, les workers locaux et les handlers Lambda.

**Périmètre codé : parties 1 à 4, local Docker et préparation AWS.** MCP et WebSocket vocal utilisent les objectifs, la mémoire, les droits et les reçus du même domaine. L'étape 4 ajoute tickets uniques, annonces sourcées, activité avec rattrapage, export/effacement des souvenirs, restauration en quarantaine et manifeste compatible. Planificateur, commerce et transcriptions des recettes restent simulés. Nova/Polly, AgentCore, AppSync, Google Calendar et Titan/S3 Vectors sont codés avec tests de contrat et infrastructure ; leurs accès réels restent à qualifier. Identité locale synthétique, DynamoDB Local et ElasticMQ émulés. Aucun achat réel ni appel distant à un modèle effectué ; aucune intégration native Alexa+.

## Démarrer

Prérequis : Docker avec Compose, et `uv` pour les tests et outils sur l'hôte. Le projet utilise Python 3.12 et `uv.lock`. Les images de base sont fixées par empreinte.

```powershell
docker compose build api
docker compose up -d --no-build
uv sync --frozen --group infra
```

Sous Windows, si le certificat PyPI est refusé, utiliser `uv --system-certs sync --frozen --group infra`. TLS reste vérifié. API : `http://127.0.0.1:8088`, documentation interactive : `/docs`. Le port interne reste 8080. Remplacer `KOYORI_API_PORT` si nécessaire. Le sous-réseau Docker explicite `10.253.42.0/24` peut être changé avec `KOYORI_DOCKER_SUBNET` s'il chevauche un réseau existant.

Le bootstrap volontaire crée deux foyers fictifs. `alex` administre A, `sam` est membre personnel de A et `speaker` représente un appareil partagé. `robin` administre B. Le bootstrap répété ne restaure pas des droits révoqués.

```powershell
$access = docker compose run --rm --no-deps demo python -m koyori.demo token alex
$headers = @{ Authorization = "Bearer $access"; 'Idempotency-Key' = [guid]::NewGuid().ToString() }
$foyers = Invoke-RestMethod 'http://127.0.0.1:8088/v1/households' -Headers $headers
$headers['X-Household-Id'] = $foyers.items[0].id
$body = @{ operation = 'synthetic.checkpoint'; label = 'Première recette' } | ConvertTo-Json
$accepted = Invoke-RestMethod 'http://127.0.0.1:8088/v1/commands' -Method Post -Headers $headers -ContentType 'application/json' -Body $body
Invoke-RestMethod "http://127.0.0.1:8088$($accepted.statusUrl)" -Headers $headers
```

`202` indique l'enregistrement durable. Après traitement, `SUCCEEDED` et le reçu `kind=synthetic` prouvent uniquement les deux checkpoints internes. Les clés privées locales sont dans un volume réservé à l'émetteur ; elles ne sont montées ni dans l'API ni dans les workers. Les tokens expirent après dix minutes. Ne pas enregistrer de tokens, de dumps ou de clés dans Git.

## Vérifier

```powershell
$env:KOYORI_INTEGRATION = '1'
uv run pytest -q --junitxml=artifacts/all-tests.xml
uv run ruff check src tests scripts infrastructure
uv run ruff format --check src tests scripts infrastructure
uv run python scripts/verify_local.py
uv run python scripts/verify_stage2.py
uv run python scripts/verify_stage3.py
uv run python scripts/verify_stage4.py
```

La recette Docker tue un worker vivant après le premier checkpoint, redémarre stockage et API, rejoue la commande et vérifie la fin de la même tâche. Elle arrête temporairement les services de ce projet, puis les redémarre. Sans `KOYORI_INTEGRATION=1`, les tests des émulateurs sont explicitement ignorés. Les assertions AWS exigent d'abord la construction et la synthèse ci-dessous.

## Préparer AWS

```powershell
uv run python scripts/build_lambda.py
uv run python -m infrastructure.app
uv run pytest -q tests/test_infrastructure.py
uv run pip-audit --path artifacts/lambda --format cyclonedx-json --output artifacts/runtime-sbom.json
```

Le bundle contient les roues Linux verrouillées. CDK prépare Cognito, quatre tables DynamoDB, EventBridge, SQS/DLQ, treize Lambda, Standard/Scheduler, KMS, S3 Vectors, API Gateway, deux runtimes AgentCore, AppSync Events, alarmes, PITR et sauvegardes. Aucun déploiement exécuté. Les deux images runtime ARM64 exigent un digest ECR immuable ; construire `Dockerfile.runtime` et qualifier cette architecture avant livraison distante. Callback Cognito, secrets Google et accès modèles doivent être configurés. Planification Nova US : décision de région/consentement requise ; voix Nova configurée en `eu-north-1`. Aucun coût AWS observé ni ressource distante créée. [Livraison et qualification](docs/stage4.md).

La qualification Nova utilise `uv run python scripts/qualify_planner.py --live` sur des fixtures synthétiques uniquement, jusqu'à seize requêtes facturables. Sans accès AWS, le rapport indique `NOT_RUN`. Les [contrats de coordination](docs/stage3.md) détaillent limites, résultats et reprise.

Pour une stack indépendante, définir `COMPOSE_PROJECT_NAME`, `KOYORI_RUNTIME_IMAGE`, `KOYORI_API_PORT`, `KOYORI_VOICE_PORT`, `KOYORI_DDB_PORT`, `KOYORI_SQS_PORT` et `KOYORI_DOCKER_SUBNET`. Voix locale : `ws://127.0.0.1:8099/ws` par défaut, admission par l'API. Tests hôte : `KOYORI_TEST_DDB_ENDPOINT` et `KOYORI_TEST_SQS_ENDPOINT`. Le bundle peut utiliser uv de l'image déjà construite : `uv run python scripts/build_lambda.py --runtime-image NOM_IMAGE`. Les dépendances restent vérifiées par hash et TLS. Générer les preuves avec `record_evidence.py`, puis `prepare_release.py` ; `qualify_channels.py --live` ne remplace pas une recette distante.

## Documents de reprise

- [Manifeste de livraison](docs/delivery-manifest.md)
- [Contrat HTTP et autorisations](docs/api.md)
- [Exploitation, sauvegarde et restauration](docs/operations.md)
- [Contrat d'implémentation](docs/implementation-contract.md)
- [Vérifications de l'étape 1](docs/verification/stage1.md)
- [Contrats et configuration de l'étape 2](docs/stage2.md)
- [Vérifications de l'étape 2](docs/verification/stage2.md)
- [Coordination, routines et apprentissage — étape 3](docs/stage3.md)
- [Vérifications de l'étape 3](docs/verification/stage3.md)
- [Canaux, confidentialité et livraison — étape 4](docs/stage4.md)
- [Vérifications de l'étape 4](docs/verification/stage4.md)
- [Journal du développement](JOURNAL.md)

La licence du dépôt est [Apache 2.0](LICENSE). Le travail local ne constitue pas une publication, une contribution complémentaire Open Source ou une qualification de l'intégration Alexa+.
