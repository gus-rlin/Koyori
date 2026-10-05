# Vérification de l'étape 3

État final au 2026-10-06 : **205 tests passés sans exclusion, trois recettes Docker PASS et revue indépendante PASS à 9,2/10**. Le code couvre les six blocs du [plan](<../../Construire le backend de Koyori en quatre grandes étapes.md>) ; les capacités distantes demeurent séparées du périmètre local et des adaptateurs. Le [rapport de revue](stage3-review.md) conserve les deux verdicts intermédiaires et leurs corrections.

| Comportement observable | Preuve |
| --- | --- |
| Objectif naturel, DAG, reçus, amendement court et annulation | `test_stage3_goals.py`, recette `verify_stage3.py` |
| Baux, crash, wake conservé, limites et rapprochement indépendant | `test_stage3_recovery.py`, `test_stage3_adapters.py` |
| Pause contre dispatch et quota partagé | `test_stage3_integration.py` avec DynamoDB Local réel |
| Deux lectures indépendantes, quotas et activité privée | `test_stage3_bounds.py` |
| Agenda changé avec connexion inchangée ; no-op et sync partielle | `test_stage3_calendar.py` avec HTTP Google fictif |
| DST, occurrence unique, règle remplacée et réparation | `test_stage3_scheduling.py`, `test_stage3_integration.py` |
| Apprentissage sans droits supplémentaires, source effacée, calme et regroupement | `test_stage3_learning.py` |
| Strands/Botocore réels avec transport Converse intercepté | `test_stage3_adapters.py` ; aucun modèle distant appelé |
| Standard fini, logs privés exclus, IAM coordinateur et Scheduler | `test_stage3_infrastructure.py`, template CDK synthétisé |
| Sources découvertes/déclarées, correction/effacement avant réserve/envoi, compte après réadmission et réparation du dernier réveil | 19 cas de `test_stage3_review.py`, [historique de revue](stage3-review.md) |

Les tests se cumulent avec les étapes 1 et 2 de la base `fb5f310`. Les recettes arrêtent/reprennent les services de la stack sélectionnée et conservent les volumes. Le rapport Docker et les XML restent dans `artifacts/`, ignoré et sans jetons ni contenu privé. Les empreintes finales sont dans [artifact-evidence.json](artifact-evidence.json). Le checkout d'origine évolue indépendamment ; ses corrections ultérieures de l'étape 2 seront à comparer/fusionner avant intégration, sans modifier cette base de qualification.

```powershell
$env:COMPOSE_PROJECT_NAME = 'koyori-stage3'
$env:KOYORI_RUNTIME_IMAGE = 'koyori-stage3:local'
$env:KOYORI_API_PORT = '8098'
$env:KOYORI_DDB_PORT = '8890'
$env:KOYORI_SQS_PORT = '9334'
$env:KOYORI_DOCKER_SUBNET = '10.253.43.0/24'
docker compose up -d --build
uv run python scripts/build_lambda.py --runtime-image koyori-stage3:local
uv run python -m infrastructure.app
$env:KOYORI_INTEGRATION = '1'
$env:KOYORI_TEST_DDB_ENDPOINT = 'http://127.0.0.1:8890'
$env:KOYORI_TEST_SQS_ENDPOINT = 'http://127.0.0.1:9334'
uv run pytest -q --junitxml=artifacts/all-tests.xml
uv run ruff check src tests scripts infrastructure
uv run ruff format --check src tests scripts infrastructure
uv run python scripts/verify_local.py
uv run python scripts/verify_stage2.py
uv run python scripts/verify_stage3.py
uv run python -m pip_audit --path artifacts/lambda --format cyclonedx-json --output artifacts/runtime-sbom.json
uv run python scripts/record_evidence.py
```

La recette Docker de l'étape 3 donne `PASS` : processus vivant tué après plan sauvegardé, redémarrage stockage/API, idempotence et confidentialité, attente sans nouveau modèle, pause/reprise, préférence acceptée, modification du même achat pour quatre, annulation avec reçu, occurrence unique après wake répété et flux de notifications. Les recettes étapes 1 et 2 donnent également `PASS`, sur l'image reconstruite après les corrections de revue. L'audit des 52 dépendances runtime Linux ne trouve aucune vulnérabilité connue. Ruff, le format des 74 fichiers Python et le contrôle du diff réussissent ; la synthèse CDK et ses neuf assertions d'infrastructure passent. Les empreintes finales, les trois recettes et les compteurs JUnit sont enregistrés dans [artifact-evidence.json](artifact-evidence.json).

La revue finale rejoue indépendamment 66 tests ciblés et deux courses forcées, sans défaut matériel ouvert. Les 37 modules du bundle correspondent aux sources. Empreinte source qualifiée localement : `e3ee48b93f552dd6500a87ab0b0ffd6b7be980eb8318122bb1548adde4d967d1`, recalculée à la clôture sans changement. Les références locales des documents modifiés sont contrôlées sans lien manquant. Les seuls ajouts après ce verdict consignent les résultats dans la documentation et le journal ; ils ne modifient pas le code ni les artefacts exécutés.

La qualification Nova est [NOT_RUN faute d'identifiants AWS](nova-qualification.json). Aucun score de qualité du modèle réel, coût, IAM exécuté, login Cognito ou comportement distribué AWS n'est déduit des tests locaux. La procédure distante est disponible dans [stage3.md](../stage3.md). Cette limite concerne aussi Google et les composants distants de l'étape 2. Le workflow GitHub est préparé, sans exécution GitHub constatée dans cette session.
