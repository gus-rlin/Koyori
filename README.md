# Koyori — première partie du backend

Le socle exécute une commande synthétique durable, avec identité signée, autorisations par objet, transactions, reprise après crash et activité persistante. Le même code Python sert l'API HTTP, les workers locaux et les handlers Lambda.

**Périmètre livré : local Docker et préparation AWS.** L'authentification locale est un émetteur synthétique explicite. DynamoDB Local et ElasticMQ sont des émulateurs ; leurs résultats ne qualifient pas AWS. Mémoire, connecteurs, modèles, coordination agentique, voix et MCP appartiennent aux parties suivantes. Aucun achat ni appel à un modèle n'est effectué.

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
```

La recette Docker tue un worker vivant après le premier checkpoint, redémarre stockage et API, rejoue la commande et vérifie la fin de la même tâche. Elle arrête temporairement les services de ce projet, puis les redémarre. Sans `KOYORI_INTEGRATION=1`, les tests des émulateurs sont explicitement ignorés. Les assertions AWS exigent d'abord la construction et la synthèse ci-dessous.

## Préparer AWS

```powershell
uv run python scripts/build_lambda.py
uv run python -m infrastructure.app
uv run pytest -q tests/test_infrastructure.py
uv run pip-audit --path artifacts/lambda --format cyclonedx-json --output artifacts/runtime-sbom.json
```

Le bundle Lambda contient les roues Linux verrouillées, pas celles de Windows. CDK synthétise Cognito, trois tables DynamoDB, EventBridge, deux files avec DLQ, cinq Lambda, API Gateway, alarmes, PITR et sauvegarde quotidienne. La synthèse ne contacte aucun compte. Le callback OAuth par défaut `example.invalid` doit être remplacé avant un déploiement autorisé ; aucun déploiement n'est exécuté ici. Les coûts AWS observés sont inexistants car aucune ressource n'a été créée.

## Documents de reprise

- [Manifeste de livraison](docs/delivery-manifest.md)
- [Contrat HTTP et autorisations](docs/api.md)
- [Exploitation, sauvegarde et restauration](docs/operations.md)
- [Contrat d'implémentation](docs/implementation-contract.md)
- [Vérifications de l'étape 1](docs/verification/stage1.md)
- [Journal du développement](JOURNAL.md)

La licence du dépôt est [Apache 2.0](LICENSE). Le travail local ne constitue pas une publication, une contribution complémentaire Open Source ou une qualification de l'intégration Alexa+.
