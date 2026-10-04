# Étape 1 — Contrat d'intégration des chantiers

Décisions d'implémentation de l'orchestrateur, 2026-10-05. Ce document complète le plan accepté ; il ne constitue pas une preuve de livraison. Les interfaces Python exportées par le chantier contrats font autorité pour leurs noms exacts.

## Frontières

- Code Python unique sous `src/koyori`, partagé par API, workers locaux et handlers Lambda.
- Environnement `KOYORI_ENV=local|dev|prod` ; `dev` et `prod` préparent AWS. Le domaine de cette étape reste `sandbox` dans tous les environnements.
- Trois tables : `Domain`, `Delivery`, `Sessions`, chacune avec `PK` et `SK`. Index `GSI1PK/GSI1SK` et `GSI2PK/GSI2SK` pour les accès bornés requis.
- Le magasin expose lecture forte, requêtes paginées et transactions conditionnelles. Il traduit les valeurs natives pour boto3 ; les services ne contournent pas ce magasin pour écrire.
- Identité personnelle ou appareil partagé dérivée de l'identité signée et des enregistrements serveur. `X-Household-Id` sélectionne un foyer à autoriser et ne définit jamais l'identité.
- Aucun connecteur, modèle, voix, achat ou accès à des données réelles.

## Surface HTTP minimale

| Routes | Comportement |
| --- | --- |
| `GET/POST /v1/households` | Liste des appartenances du principal ; création avec le créateur comme premier administrateur |
| `GET/POST /v1/households/{id}/members` | Liste et ajout des membres par administrateur autorisé |
| `PATCH/DELETE /v1/households/{id}/members/{principalId}` | Modification et révocation ; contrôle transactionnel du dernier administrateur |
| `POST /v1/commands` | Accepte uniquement `synthetic.checkpoint` et retourne `202` après commit |
| `GET /v1/tasks`, `GET/PATCH /v1/tasks/{id}` | Liste autorisée, lecture et modification ; partage explicite par visibilité |
| `POST /v1/tasks/{id}/pause`, `/resume`, `/cancel` | Contrôle déterministe des tâches avec version attendue |
| `GET/POST /v1/tasks/{id}/delegations` | Liste et création de droits explicites par propriétaire |
| `DELETE /v1/tasks/{id}/delegations/{delegationId}` | Révocation logique avec version attendue |
| `GET /v1/policies`, `PUT /v1/policies/{id}` | Politiques versionnées et bornées à la capacité synthétique |
| `POST /v1/auth/step-up` | Challenge lié au principal, à l'opération et au hash exact de la demande |
| `POST /v1/auth/step-up/{id}/complete` | Preuve d'identité signée, nonce et authentification fraîche vérifiés ; grant à usage unique |
| `GET /v1/activity` | Flux durable paginé avec curseur signé, lié au principal et au foyer |
| `GET /health/live`, `GET /health/ready` | Santé sans secrets ni corps métier |

Mutations : `Idempotency-Key` ; amendements et suppressions : `If-Match`. Expansions de droits : `X-Step-Up-Grant`, consommé dans la transaction de mutation. Une répétition identique déjà enregistrée est relue après réautorisation actuelle sans exiger une seconde consommation du grant. Corps d'écriture inconnus refusés. Les erreurs suivent `application/problem+json` et distinguent conflit sémantique et précondition HTTP.

## Autorisations et preuve fraîche

- Un membre ne lit pas les ressources privées d'un autre, y compris s'il administre le foyer. Un appareil partagé n'utilise que les ressources partagées et n'administre pas les droits.
- Seul le propriétaire partage une tâche ou délègue son accès ; une délégation ne permet pas de créer d'autres délégations. Expiration et révocation sont logiques, indépendantes du nettoyage TTL.
- Les grants d'exécution sont durables et étroits ; aucun access token d'utilisateur n'est enregistré dans une tâche.
- Le challenge step-up conserve nonce, principal, opération, hash et expiration côté serveur. La preuve locale est produite uniquement par l'émetteur synthétique de la CLI ; une preuve AWS doit provenir de l'émetteur Cognito configuré. Un ID token n'est jamais accepté comme bearer de l'API.
- Autorisations relues fortement avant une mutation et versions protégées dans sa transaction. Les rejets, réparations et rejeux suivent les mêmes règles.

## Durabilité

- Commande acceptée = tâche, décision, idempotence et outbox atomiquement enregistrées. Ne pas compter sur les dix minutes du jeton d'idempotence DynamoDB.
- `synthetic.checkpoint` conserve deux marqueurs internes déterministes et un résultat marqué synthétique. Le label décrit la tâche et n'est pas une action externe.
- Les transitions conservent leur outbox. Les entrées pending ne disparaissent pas par TTL.
- Les consommateurs enregistrent inbox et transition avant acquittement. Les messages vieux ou de major incompatible sont traités explicitement ; ils ne régressent jamais l'état canonique.
- Les intentions d'exécution sont durables. Un réveil pendant un run incrémente `wakeSeq` ; la libération ou réparation enregistre le run suivant si nécessaire.
- Une écriture de worker exige révision, `runEpoch` et propriétaire du bail actuels. Une pause, annulation ou reprise concurrente clôt l'autorité du run ancien.
- Les terminalisations décrémentent atomiquement le nombre de tâches actives ; la limite vaut 32 par foyer par défaut. Le dernier administrateur et la limite de huit membres sont protégés par la version du foyer.
- Le flux d'activité contient des identifiants et métadonnées minimales. Sa lecture revalide les objets canoniques et les droits, même après une révocation.

## Exécutables et infrastructures

- API locale : `uvicorn koyori.control.app:create_app --factory --host 0.0.0.0 --port 8080` dans le conteneur ; publication hôte sur loopback.
- Local : `python -m koyori.workers.cli publisher|workflow|repair|activity` ; le service dédié `activity` consomme la file d'activité et produit le flux durable.
- CLI synthétique : `python -m koyori.demo seed|token|step-up`. L'initialisation est volontaire, idempotente et ne remplace pas les droits existants. Clés JWT et curseur dans volume local ignoré, jamais dans l'image ou Git.
- Lambda : `koyori.control.lambda_handler.handler` et `koyori.workers.lambda_handlers.publish|consume|dispatch|reconcile|repair|project_activity`.
- Publicateur local : DynamoDB vers les files ElasticMQ de workflow et d'activité ; AWS : streams/outbox vers EventBridge puis SQS. Base canonique et intentions permettent une reprise même après perte des files locales.
- CDK sans credentials ni lookups ; aucun déploiement. Les tests AWS réels restent une qualification séparée.

## Acceptation et traces

Chaque chantier remet commit, branche, worktree, commandes effectivement exécutées, résultats, limitations et observations utiles au journal. L'orchestrateur est seul rédacteur de `JOURNAL.md`. Les preuves finales sont dans `docs/verification` ; les autres documents restent au chantier documentation.

Tests indépendants après intégration ; revue Sol en lecture seule après ces tests. PASS exige au moins 8/10 sans constat critique ou élevé restant. Une modification substantielle invalide la revue précédente.
