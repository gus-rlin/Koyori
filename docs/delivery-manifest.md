# Manifeste de livraison — étape 1

Contrat daté du 2026-10-05. La livraison acceptée est le backend local complet et les artefacts AWS vérifiables sans compte. Les preuves d'exécution AWS demeurent séparées.

| Capacité | Étape | Réalité et dépendances | Contrat et critère |
| --- | --- | --- | --- |
| Authentification et contexte | 1 | Validation JWT réelle ; émetteur synthétique local ; Cognito préparé | Signature, issuer, client, usage, scope et expiration vérifiés ; identité issue du serveur |
| Foyers, membres et appareils partagés | 1 | Réel par API, données de recette fictives | Dernier admin, huit membres, confidentialité privée/partagée, autorité revalidée par transaction |
| Délégations et preuves fraîches | 1 | Réel par API ; preuve synthétique locale, contrat Cognito préparé | Nonce, personne, opération, corps normalisé et révision ; consommation atomique ; expiration et révocation logiques |
| Politiques | 1 | Réel, limité à `synthetic.checkpoint` | Expansion avec preuve fraîche, règles versionnées, relecture avant chaque checkpoint |
| Commandes et tâches | 1 | Réel dans DynamoDB Local, même adaptateur AWS | Acceptation atomique ; idempotence durable ; révision, pause, reprise et annulation déterministes |
| Travail durable | 1 | Réel ; checkpoints synthétiques | Inbox, baux, générations, intentions persistantes, réveil pendant un run, fencing des anciennes écritures |
| Publication et réparation | 1 | Réel via ElasticMQ local ; EventBridge/SQS préparés | Outbox sans TTL, publication répétable, réparation bornée, DLQ et échecs partiels |
| Activité | 1 | Réel ; compteurs et événements durables par membre | Projection dédupliquée et lecture canonique des droits ; pagination signée et liée au principal |
| Exploitation locale | 1 | Réel via Docker, Python et scripts | Santé, erreurs expurgées, limites, images et dépendances verrouillées, recette de crash et restauration hors ligne |
| Infrastructure AWS | 1 | Code et synthèse réels, exécution distante non qualifiée | Cognito, DynamoDB, EventBridge, SQS, Lambda, HTTP API, alarmes, sauvegardes ; assertions du template |
| Mémoire, agenda et commerce | 2 | Différé ; aucun fournisseur connecté | Provenance, OAuth, budget, rapprochement ; commerce futur explicitement simulé |
| Planification et apprentissage | 3 | Différé ; aucun modèle appelé | Plans bornés et travail durable existant ; procédures sans élévation des droits |
| Voix, MCP et Alexa+ | 4 | Différé ; aucune intégration native | Canaux sur le même domaine, qualification distincte du canal représentant Alexa |

## Choix de mise en œuvre

Python 3.12, FastAPI/Pydantic pour les contrats HTTP, boto3 pour les transactions et livraisons, PyJWT/cryptography pour les signatures et Mangum pour Lambda. Les outils de test, d'analyse des dépendances et CDK restent hors de l'image runtime. `uv.lock` fixe les versions et empreintes.

Trois tables suffisent au socle : `Domain`, `Delivery`, `Sessions`. Les lectures d'autorité utilisent les clés de base avec cohérence forte ; les index servent uniquement à découvrir le travail en attente. Le registre des membres actifs, borné à huit identités dans le foyer, est modifié dans la même transaction que les appartenances. Il évite que l'historique des révocations masque les membres actuels.

Un grant d'exécution est attaché à la capacité synthétique, au propriétaire et à sa génération d'accès. Réinscrire une personne ne réactive pas ses anciens grants d'exécution ou délégations. Les actions d'un modèle et les préférences n'existent pas à cette étape et ne peuvent accorder de droits.

Le TDD propose Step Functions Standard pour les plans et attentes agentiques. L'étape 1 réalise les tentatives finies directement dans les workers avec état canonique, intentions durables et fencing. Step Functions sera qualifié avec la coordination de l'étape 3 ; il n'est pas annoncé comme livré. Ce choix conserve les garanties de reprise de la recette synthétique et évite de prétendre qualifier des workflows de modèles absents.

## Limites conservées

- Les tests des émulateurs ne démontrent ni les conflits transactionnels distribués de DynamoDB ni la cohérence des index AWS. Une injection contrôlée teste la réautorisation après conflit.
- Aucune preuve de login Cognito, d'IAM exécuté, de restauration AWS, de coût AWS ou de comportement du bus distant n'est obtenue par la synthèse.
- L'export local est hors ligne. Toute restauration se fait dans de nouvelles tables, avec writers arrêtés et contrôles avant remise en service. Le traitement des suppressions de mémoire et effets fournisseur appartient aux étapes suivantes.
- L'idempotence du socle est conservée sans nettoyage automatique. La rétention et l'effacement des historiques seront définis avec les données personnelles ; aucun secret fournisseur ni donnée personnelle réelle n'est utilisé dans les recettes.
