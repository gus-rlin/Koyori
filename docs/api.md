# API de contrôle — contrats 1.0

Voir `/docs` et `/openapi.json` dans l'environnement local pour les schémas complets. Les champs d'écriture inconnus sont refusés. Les corps et événements sont limités à 32 Kio ; les labels à 200 caractères. Les dates d'expiration sont des secondes UTC ; le foyer conserve un fuseau IANA.

## Identité et droits

Chaque route `/v1` exige un bearer access token RS256. L'émetteur, le client, l'usage `access`, la portée `koyori/control`, les dates et l'audience lorsqu'elle est présente sont vérifiés. Un ID token est réservé à la preuve fraîche et n'est jamais un bearer valide. La production n'accepte ni l'émetteur synthétique ni des endpoints AWS locaux.

`X-Household-Id` sélectionne le foyer des routes tâches, politiques, preuve fraîche et activité. Les routes `/households/{id}` autorisent le foyer de leur chemin. Ni un header, ni un champ du corps ne choisit la personne effective. Le type personnel/partagé provient du profil serveur, pas du token du client.

Un administrateur ne lit pas automatiquement les tâches privées d'un autre membre. Seul le propriétaire partage ou délègue une tâche. Le partage permet la lecture ; le contrôle par un autre membre exige une délégation `read,control`. Les appareils partagés lisent uniquement les tâches partagées et ne mutent pas les tâches ou droits. Les réinscriptions ne rétablissent pas les délégations anciennes.

## Surface

| Méthode et chemin | Corps / réponse | Contrôle |
| --- | --- | --- |
| `GET /v1/households` | Appartenances autorisées | Bearer ; pagination |
| `POST /v1/households` | `name`, `timeZone` ; `201` | Personnel ; clé d'idempotence |
| `GET /v1/households/{id}/members` | Membres actuels et historiques ; pagination | Admin personnel |
| `POST /v1/households/{id}/members` | `principalId`, `role`, `kind`, `expiresAt` ; `201` | Admin, preuve fraîche |
| `PATCH/DELETE /v1/households/{id}/members/{principal}` | Rôle/expiration ou révocation ; `200` | Admin, If-Match ; preuve fraîche pour expansion |
| `POST /v1/commands` | `operation=synthetic.checkpoint`, `label`, `visibility` ; `202` | Personnel ; preuve fraîche si partage initial |
| `GET /v1/tasks`, `GET /v1/tasks/{id}` | Tâches autorisées ; ETag sur l'objet | Propriétaire, partage ou délégation courante |
| `PATCH /v1/tasks/{id}` | `label` et/ou `visibility` ; `202` | Contrôle ; propriétaire pour visibilité ; preuve fraîche pour partage |
| `POST /v1/tasks/{id}/pause`, `/resume`, `/cancel` | Corps vide ; `202` | Contrôle ; If-Match |
| `GET/POST /v1/tasks/{id}/delegations` | Liste paginée / `principalId`, `permissions`, `expiresAt` ; `201` | Propriétaire ; preuve fraîche à la création |
| `DELETE /v1/tasks/{id}/delegations/{principal}` | Révocation ; `200` | Propriétaire, If-Match |
| `GET /v1/policies`, `PUT /v1/policies/synthetic` | Politique / `enabled`, `capability=synthetic.checkpoint` | Admin ; If-Match ; preuve fraîche à l'activation |
| `POST /v1/auth/step-up` | `operation`, `requestHash` ; challenge avec nonce | Personnel |
| `POST /v1/auth/step-up/{id}/complete` | `identityProof` ; grant opaque | Même personne, nonce et authentification fraîche |
| `GET /v1/activity` | Événements minimaux autorisés | Curseur lié à personne, foyer et route ; ACL actuelle |
| `GET /health/live`, `/health/ready` | Santé sans donnée métier | Public ; ready lit DynamoDB |

Les membres partagés ne deviennent pas administrateurs. Un administrateur ne possède pas d'expiration automatique afin de préserver la règle du dernier administrateur. Les délégations durent au maximum trente jours. Le plafond de tâches actives vaut 32 par foyer ; les tâches terminales le libèrent atomiquement.

## Écritures et preuve fraîche

Toutes les mutations exigent une clé `Idempotency-Key` aléatoire, UUID recommandé. Les modifications et révocations exigent `If-Match: "<rev>"`. Le même principal, foyer, route et clé avec le même corps normalisé et la même précondition retrouvent la réponse d'origine après contrôle des droits actuels. Un corps différent produit `409` ; une ancienne révision produit `412`. Les corps normalisés incluent les valeurs par défaut des schémas ; pour un PATCH membre, seuls les champs présents sont inclus.

Pour une expansion, créer le challenge avec l'opération exacte, par exemple `POST /v1/households/<id>/members`. `requestHash` est le SHA-256 de JSON UTF-8 trié et compact `{"body": <corps normalisé>, "version": <révision ou null>}`, calculé par `koyori.security.request_hash`. Le challenge expire après 180 secondes.

En local, la CLI `demo step-up` signe la preuve synthétique avec le nonce du challenge. Pour AWS, la preuve doit être un ID token de Cognito pour le client configuré, obtenu avec `prompt=login` et le nonce retourné. La préparation IaC choisit explicitement le niveau Essentials, managed login v2 et le branding Cognito du client ; la réauthentification reste à qualifier sur AWS. Le serveur vérifie subject, nonce et `auth_time >= createdAt`, puis remet un grant valable 120 secondes. Passer ce grant dans `X-Step-Up-Grant` : la mutation le consomme atomiquement avec ses écritures. Un grant utilisé pour une autre personne, foyer, opération, corps ou version est refusé. Une répétition déjà validée n'exige pas une seconde consommation.

Réduire une expiration ne demande pas de grant. Prolonger l'accès, supprimer son expiration ou réactiver une appartenance expirée exige une preuve fraîche ; la réactivation change la génération d'accès et ne rétablit pas les anciennes délégations.

## Résultats et erreurs

Les états du socle sont `READY`, `RUNNING`, `PAUSED`, `SUCCEEDED`, `FAILED`, `CANCELLED`. Le label est descriptif ; aucun texte n'est interprété comme une action externe. Une commande acceptée ne confirme pas son achèvement. Le succès synthétique possède deux marqueurs persistants et un résultat `kind=synthetic`.

Les erreurs utilisent `application/problem+json`, un code stable, `requestId` et `retryable`. `401` : token invalide ; `403` : opération refusée ; `404` : objet absent ou inaccessible ; `409` : conflit métier ou d'idempotence ; `412` : révision obsolète ; `422` : schéma invalide ; `428` : précondition absente ; `429` : quota ; `503` : dépendance ou contention temporaire. `429/503` fournissent `Retry-After`. Les erreurs, traces et logs ne reproduisent ni corps métier ni token.

Les listes renvoient au maximum cinquante candidats par page. Une page filtrée peut être vide tout en donnant un `nextCursor` ; continuer jusqu'à `null`. Les curseurs signés expirent après une heure et ne sont pas transférables à un autre principal, foyer ou endpoint.

Les curseurs sont aussi chiffrés avec AES-GCM pour ne pas révéler une clé d'objet privé rencontrée lors de la pagination. Le flux d'activité retourne `resumeCursor`, y compris en fin de lecture : le conserver pour lire les prochains événements avec `?cursor=...`. `nextCursor` sert à finir le rattrapage courant ; `resumeCursor` garde le point atteint après celui-ci. Les droits sont revalidés à chaque lecture.
