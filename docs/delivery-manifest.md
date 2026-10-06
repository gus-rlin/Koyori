# Manifeste de livraison — étapes 1 à 4

Contrat actualisé le 2026-10-06. La livraison comprend les implémentations locales et les artefacts AWS vérifiables sans compte. Les preuves d'exécution AWS et de qualité du modèle réel demeurent séparées.

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
| Mémoire sourcée et contexte | 2 | Réel par HTTP/DynamoDB Local ; embeddings locaux simulés | Chronologie, clé, journées locales, correction/effacement, sources et droits actuels |
| Recherche Titan/S3 Vectors | 2 | Adaptateurs et infrastructure préparés ; appels externes non qualifiés | 512 dimensions, filtres serveur, relecture canonique, plafond quotidien |
| Google Calendar | 2 | OAuth/sync/push codés ; tests avec fournisseur fictif, compte réel non qualifié | Scopes read-only, sélection, chiffrement, refresh/révocation et sync paginé |
| Commerce, approbations et budgets | 2 | Mécanismes réels ; fournisseur et commandes simulés | Devis exacts, montants entiers, réservation atomique, intention stable, rapprochement et reçus séparés |
| Plans naturels et spécialistes | 3 | Réel par API ; planificateur de recette simulé ; Strands exécuté avec HTTP intercepté | DAG typé/versionné, comptes/dates/révisions validés, 2 lectures parallèles, prix/reçus des connecteurs |
| Coordinateur Nova et quotas | 3 | Adaptateur réel préparé ; qualification distante `NOT_RUN` sans identifiants AWS | 1 réparation, 2 requêtes par proposition, 16 par objectif, 200 par personne/foyer/jour ; aucune autorité au modèle |
| Reprise et changement d'objectif | 3 | Réel en local, intentions et checkpoints persistants | Baux/générations, attentes sans modèle actif, ancienne action rapprochée avant remplacement, même intention commerciale |
| Routines et notifications | 3 | Réel en local ; Scheduler/Step Functions Standard codés et synthétisés | UTC/IANA/DST, occurrence/règle versionnées, réparation de réveils, groupes privés et horaires de calme |
| Apprentissage sourcé | 3 | Réel par API, propositions explicitement acceptées | Révisions source/cible, correction et effacement des projections, procédures déclaratives, aucune expansion des droits |
| Mémoire durable et archives Hermes | 3–4 | Réel par HTTP/MCP/voix et DynamoDB Local ; index lexical indépendant des modèles | `coreItems` distinct du jour civil ; AND 1–8 termes, curseur privé/partagé, relecture canonique, budgets bornés |
| Propositions automatiques | 3–4 | Worker local simulé ; Strands/Nova testé par transport HTTP intercepté, AWS explicite non qualifié | Intentions et baux durables ; 2 requêtes SDK à vie/intention, 20 UTC/personne/jour ; acceptation explicite, aucun achat seul transformé en préférence |
| MCP versionné | 4 | SDK Streamable HTTP réel, OAuth lié à la ressource, runtime préparé | Métadonnées client sans autorité ; neuf outils du domaine ; droits et idempotence réutilisés |
| Transport vocal | 4 | WebSocket réel local ; transcripts de recette simulés ; adaptateur Nova/Polly préparé | Ticket unique, modes, PCM borné, renouvellement, tours persistants, annonces selon reçu |
| Signaux et rattrapage | 4 | Feed et outbox réels ; AppSync/IAM/Lambda préparés | Signal sans contenu privé, abonnement exact, rattrapage avec droits actuels |
| Confidentialité et récupération | 4 | Export/effacement paginés et restauration locale avec ledger | Suppressions plus récentes appliquées, anciennes sessions retirées, cible hors ligne ; historique commercial conservé |
| Livraison complète | 4 | Manifestes et CDK ; AWS/ARM64 distants non qualifiés | Digests immuables, contrats de rollback, preuves locales cumulatives ; aucune intégration native Alexa+ |

## Choix de mise en œuvre

Python 3.12, FastAPI/Pydantic pour les contrats HTTP, boto3 pour les transactions et livraisons, PyJWT/cryptography pour les signatures et Mangum pour Lambda. Les outils de test, d'analyse des dépendances et CDK restent hors de l'image runtime. `uv.lock` fixe les versions et empreintes.

Trois tables suffisent au socle : `Domain`, `Delivery`, `Sessions`. Les lectures d'autorité utilisent les clés de base avec cohérence forte ; les index servent uniquement à découvrir le travail en attente. Le registre des membres actifs, borné à huit identités dans le foyer, est modifié dans la même transaction que les appartenances. Il évite que l'historique des révocations masque les membres actuels.

Un grant d'exécution est attaché à la capacité, au propriétaire et à sa génération d'accès. Réinscrire une personne ne réactive pas ses anciens grants d'exécution ou délégations. Les sorties de modèle, préférences et procédures ne peuvent accorder de droits.

Le TDD propose Step Functions Standard pour les plans et attentes agentiques. L'étape 1 conserve ses workers directs ; l'étape 3 ajoute les adaptateurs et la synthèse Standard, avec une exécution finie par checkpoint et des réveils persistants. Les petits plans (24 Ko maximum) restent dans `Domain` avec promotion atomique. Le comportement distant de Step Functions/Scheduler reste à qualifier. [Contrats détaillés](stage3.md).

## Limites conservées

L'étape 2 ajoute `Connections` pour les enveloppes OAuth et clés de notifications, avec permissions KMS séparées. Les souvenirs et les registres d'actions restent des préfixes typés dans `Domain` ; les index de références et vecteurs sont dérivés. Les rôles `connector` et `projection` réutilisent les intentions de `Delivery`. [Contrats détaillés](stage2.md). Ces choix ne changent pas la portée de la coordination prévue en étape 3.

- Les tests des émulateurs ne démontrent ni les conflits transactionnels distribués de DynamoDB ni la cohérence des index AWS. Une injection contrôlée teste la réautorisation après conflit.
- Aucune preuve de login Cognito, d'IAM exécuté, de restauration AWS, de coût AWS ou de comportement du bus distant n'est obtenue par la synthèse.
- L'export local est hors ligne. Toute restauration se fait dans de nouvelles tables, avec tous les writers arrêtés, y compris les connecteurs/projections. Les tombstones présents sont conservés ; une sauvegarde antérieure à une suppression nécessite une liste d'effacement plus récente avant remise en service. Ne pas réactiver de dispatch externe avant contrôle des actions et réservations. La qualification complète de restauration reste en étape 4.
- L'idempotence du socle est conservée sans nettoyage automatique. La rétention et l'effacement des historiques seront définis avec les données personnelles ; aucun secret fournisseur ni donnée personnelle réelle n'est utilisé dans les recettes.
