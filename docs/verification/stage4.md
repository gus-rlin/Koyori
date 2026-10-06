# Vérifications de la quatrième partie

Travail du 2026-10-06, isolé sur `gus-rlin/koyori-etape4`, base `f81df40`, worktree `koyori-etape4-complete/Koyori`. Implémentation et corrections réalisées seules par l'agent principal. Le même sous-agent de revue indépendant a évalué deux états : **7,5/10**, puis **9/10** après correction des cinq constats. Ce score porte sur le code, les vérifications locales et la préparation du déploiement ; il n'atteste aucune intégration distante.

Les tests portent sur l'interopérabilité MCP réelle du SDK, portée/audience OAuth, métadonnées hostiles, droits partagés, délégations, ticket unique/expiré et concurrence DynamoDB Local, finalisation atomique et reprise de conversation, framing PCM, interruption, annonces selon reçu, événements natifs Nova interceptés, refresh de credentials, agenda et révocation fournisseur, effacement/révisions pendant lecture, rattrapage d'activité, restauration et paramètres/permissions CDK.

Premier passage cumulatif : 272 réussites et un échec de finalisations simultanées. Cause confirmée : conflit non repris sur `lastActivityAt` avant la transaction métier. Correction : relecture/réautorisation et retry borné, une écriture d'activité par seconde ; le test DynamoDB concurrent passe ensuite. Les chiffres de cette première passe ne sont pas présentés comme une suite finale réussie.

Suite finale après corrections de revue : **297 tests réussis, zéro échec, erreur ou exclusion**, en 101,90 secondes, sur les endpoints de test explicitement isolés 8900/9344. Le reviewer a exécuté indépendamment 75 tests ciblés sur ce dernier état, tous réussis. Ses cinq constats concernaient le démarrage et les permissions IAM des Lambdas, les fences d'effacement lors d'une lecture partagée/export, un ledger créé pendant un effacement inachevé et les annonces erronées d'outils. Configuration commune, permissions limitées aux clés nécessaires, conditions transactionnelles de lecture, refus du ledger incomplet et templates FR/EN corrigent ces cas avec régressions. Aucun constat matériel ouvert dans la seconde revue.

Interopérabilité MCP également vérifiée sur une connexion TCP réelle : le premier essai de recette révélait une transformation de `Content-Length` en chunks invalides, absente du réseau Docker Linux. L'hôte ASGI cadre désormais les réponses MCP ; initialisation, découverte et refus d'authentification passent. La couche extérieure responsable reste inconnue. Le transport MCP officiel est conservé.

```powershell
$env:COMPOSE_PROJECT_NAME = 'koyori-stage4'
$env:KOYORI_RUNTIME_IMAGE = 'koyori-stage4:local'
$env:KOYORI_API_PORT = '8108'
$env:KOYORI_VOICE_PORT = '8109'
$env:KOYORI_DDB_PORT = '8900'
$env:KOYORI_SQS_PORT = '9344'
$env:KOYORI_DOCKER_SUBNET = '10.253.44.0/24'
$env:KOYORI_INTEGRATION = '1'
$env:KOYORI_TEST_DDB_ENDPOINT = 'http://127.0.0.1:8900'
$env:KOYORI_TEST_SQS_ENDPOINT = 'http://127.0.0.1:9344'
uv run --no-sync python -m pytest -q --junitxml=artifacts/all-tests.xml
uv run --no-sync python -m ruff check src tests scripts infrastructure
uv run --no-sync python -m ruff format --check src tests scripts infrastructure
uv run --no-sync python scripts/verify_local.py
uv run --no-sync python scripts/verify_stage2.py
uv run --no-sync python scripts/verify_stage3.py
uv run --no-sync python scripts/verify_stage4.py
uv run --no-sync python -m pip_audit --path artifacts/lambda --format cyclonedx-json --output artifacts/runtime-sbom.json
uv run --no-sync python scripts/record_evidence.py
uv run --no-sync python scripts/prepare_release.py
uv run --no-sync python scripts/qualify_channels.py --live
```

Le launcher pytest Windows est refusé sur ce poste ; l'invocation du module Python fonctionne. Starlette émet un avertissement de dépréciation du TestClient httpx ; il reste visible, sans prétendre qu'une migration est effectuée.

Les quatre recettes Docker sont cumulatives. La quatrième finalise une demande vocale synthétique, ferme le socket immédiatement, consulte le même objectif par MCP/REST, redémarre runtime/stockage/API, reconnecte la conversation, observe la poursuite de la tâche, retrouve des échanges FR/EN, rattrape les signaux perdus et exécute une rafale de quatre lecteurs. Le rapport mesure uniquement les allers-retours MCP et la disponibilité de session synthétique localhost. Les accès Nova/Polly/AppSync réels, Alexa+, qualité audio, IAM exécuté, coût et PITR AWS restent `NOT_RUN`/non qualifiés.

**Les quatre recettes donnent PASS sur l'image finale.** Les 17 observations mixtes MCP/session synthétique donnent p50 58,64 ms et p95 197,11 ms, uniquement localhost. Zéro appel modèle vocal et coût AWS non mesuré. Ruff et format des 100 fichiers Python, synthèse CDK de 13 Lambdas, audit des 72 dépendances Linux sans vulnérabilité connue et contrôle du diff réussis. Les 47 modules du bundle Lambda, du runtime AMD64 et des conteneurs API/voix correspondent aux sources ; imports AMD64 voix/MCP/SDK natif/CRT réussis. L'image ARM64 a été construite et inspectée, sans exécution native sur cet hôte. Le workflow GitHub préparé n'a pas été exécuté dans cette tâche.

Source normalisée qualifiée localement : `6fc13bd4747d25cf439ddb1d6e4e31dc7f676fec992c9507877c71ae88fe0925`. L'image locale est `sha256:039e26853d86954fe604a89cacc3c3a93b972beb7016d139442cb55a2eff5933`. Les 14 services Docker isolés et cinq volumes restent conservés ; aucun service AWS créé. Le checkout original est propre au même HEAD `f81df40`, aucun push ni PR effectué.

Les empreintes sont générées dans [artifact-evidence.json](artifact-evidence.json). Les sorties brutes et JUnit restent ignorés dans `artifacts/`. Le manifeste [deployment-manifest.json](deployment-manifest.json) indique préparation, régions et architecture non qualifiée. [channel-qualification.json](channel-qualification.json) conserve les limites distantes. Le précontrôle `qualify_channels.py --live` ne constitue pas une recette de qualification cloud : il constate ici l'absence de credentials, zéro appel facturable et `NOT_RUN`. Les incidents, corrections, résultats et limites sont conservés dans JRN-021.
